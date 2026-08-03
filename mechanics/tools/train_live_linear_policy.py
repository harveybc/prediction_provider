#!/usr/bin/env python3
"""Train and materialize a transparent live baseline from JSON config."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from prediction_provider_mechanics.live_linear_policy import (
    FEATURE_NAMES,
    build_closed_bar_features,
)


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _path(value: str) -> Path:
    return Path(os.path.expandvars(value)).expanduser()


def _load(config: dict) -> pd.DataFrame:
    source = _path(config["data"]["input_file"])
    frame = pd.read_csv(source)
    columns = config["data"]["columns"]
    frame = frame.rename(columns={value: key for key, value in columns.items()})
    required = ["time", "open", "high", "low", "close", "volume"]
    missing = [name for name in required if name not in frame]
    if missing:
        raise ValueError(f"input data missing columns: {missing}")
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    frame = frame.sort_values("time").drop_duplicates("time", keep="last")
    return frame[required].dropna().reset_index(drop=True)


def _samples(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    rows, targets, forward_returns = [], [], []
    values = frame.to_dict("records")
    for index in range(50, len(values) - 1):
        window = [
            {**item, "time": item["time"].isoformat(), "complete": True}
            for item in values[index - 50 : index + 1]
        ]
        observation = build_closed_bar_features(window)
        rows.append({"time": values[index]["time"], **observation["features"]})
        forward = math.log(values[index + 1]["close"] / values[index]["close"])
        targets.append(int(forward > 0))
        forward_returns.append(forward)
    samples = pd.DataFrame(rows).set_index("time")
    return samples, pd.Series(targets, index=samples.index), pd.Series(forward_returns, index=samples.index)


def _score(probabilities, returns, threshold, periods_per_week, cost_bps):
    directions = np.where(
        probabilities >= threshold, 1.0,
        np.where(probabilities <= 1.0 - threshold, -1.0, 0.0),
    )
    turnover = np.abs(np.diff(np.r_[0.0, directions]))
    net = directions * returns.to_numpy() - turnover * cost_bps / 10000.0
    weeks = np.arange(len(net)) // periods_per_week
    weekly = pd.Series(net).groupby(weeks).sum().to_numpy()
    weekly_mean = float(np.mean(weekly)) if len(weekly) else 0.0
    weekly_std = float(np.std(weekly)) if len(weekly) else 0.0
    rap = weekly_mean / max(weekly_std, 1e-12)
    return {
        "mean_weekly_return": weekly_mean,
        "annualized_return": weekly_mean * 52.0,
        "weekly_rap": rap,
        "annualized_rap": rap * math.sqrt(52.0),
        "trades": int(np.count_nonzero(turnover)),
        "active_fraction": float(np.mean(directions != 0)),
    }


def train(config_path: Path) -> dict:
    config_bytes = config_path.read_bytes()
    config = json.loads(config_bytes)
    if config.get("schema") != "prediction_provider.live_linear_training.v1":
        raise ValueError("unsupported training config")
    frame = _load(config)
    samples, targets, returns = _samples(frame)
    train_end = pd.Timestamp(config["split"]["train_end"], tz="UTC")
    validation_end = pd.Timestamp(config["split"]["validation_end"], tz="UTC")
    train_mask = samples.index <= train_end
    validation_mask = (samples.index > train_end) & (samples.index <= validation_end)
    if train_mask.sum() < 500 or validation_mask.sum() < 50:
        raise ValueError("insufficient train or validation observations")

    feature_columns = list(FEATURE_NAMES)
    scaler = StandardScaler().fit(samples.loc[train_mask, feature_columns])
    train_x = scaler.transform(samples.loc[train_mask, feature_columns])
    validation_x = scaler.transform(samples.loc[validation_mask, feature_columns])
    candidates = []
    for c_value in config["search"]["c_values"]:
        model = LogisticRegression(C=float(c_value), max_iter=2000, random_state=0)
        model.fit(train_x, targets.loc[train_mask])
        base_probabilities = model.predict_proba(validation_x)[:, 1]
        for orientation in (1, -1):
            probabilities = (
                base_probabilities if orientation == 1 else 1.0 - base_probabilities
            )
            for threshold in config["search"]["probability_thresholds"]:
                metrics = _score(
                    probabilities,
                    returns.loc[validation_mask],
                    float(threshold),
                    int(config["evaluation"]["periods_per_week"]),
                    float(config["evaluation"]["round_trip_cost_bps"]),
                )
                candidates.append({
                    "c": float(c_value), "orientation": orientation,
                    "probability_threshold": float(threshold),
                    "metrics": metrics, "model": model,
                })
    eligible = [
        item for item in candidates
        if item["metrics"]["trades"] >= int(config["evaluation"]["minimum_validation_trades"])
        and item["metrics"]["active_fraction"] >= float(
            config["evaluation"].get("minimum_active_fraction", 0.0)
        )
    ]
    if not eligible:
        raise ValueError("no candidate passed minimum validation trades")
    champion = max(eligible, key=lambda item: (item["metrics"]["weekly_rap"], item["metrics"]["annualized_return"]))
    model = champion.pop("model")
    orientation = int(champion["orientation"])
    artifact = {
        "schema": "prediction_provider.live_linear_policy.v1",
        "model_id": config["model_id"], "asset_id": config["asset_id"],
        "timeframe": config["timeframe"], "feature_names": list(FEATURE_NAMES),
        "means": scaler.mean_.tolist(), "scales": scaler.scale_.tolist(),
        "coefficients": (orientation * model.coef_[0]).tolist(),
        "intercept": float(orientation * model.intercept_[0]),
        "probability_threshold": champion["probability_threshold"],
    }
    output = _path(config["output"]["artifact_file"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(_canonical(artifact) + b"\n")
    artifact_sha = hashlib.sha256(output.read_bytes()).hexdigest()
    manifest = {
        "schema": "prediction_provider.live_linear_manifest.v1",
        "model_id": config["model_id"], "asset_id": config["asset_id"],
        "timeframe": config["timeframe"], "artifact_file": str(output),
        "artifact_sha256": artifact_sha,
        "config_file": str(config_path.resolve()),
        "config_sha256": hashlib.sha256(config_bytes).hexdigest(),
        "data_file": str(_path(config["data"]["input_file"])),
        "data_sha256": hashlib.sha256(
            _path(config["data"]["input_file"]).read_bytes()
        ).hexdigest(),
        "train_observations": int(train_mask.sum()),
        "validation_observations": int(validation_mask.sum()),
        "validation_start": str(samples.index[validation_mask][0]),
        "validation_end": str(samples.index[validation_mask][-1]),
        "selection_metric": "weekly_rap",
        "metric_scale": "weekly_return_and_weekly_rap",
        "champion": champion,
        "candidate_count": len(candidates),
        "research_validated": True,
        "live_inference_eligible": False,
        "live_execution_eligible": False,
        "live_promotion_requirements": [
            "same_source_closed_bar_refresh",
            "runtime_feature_golden_vector",
            "protected_paper_route",
        ],
    }
    manifest_path = _path(config["output"]["manifest_file"])
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_bytes(_canonical(manifest) + b"\n")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(train(args.config), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
