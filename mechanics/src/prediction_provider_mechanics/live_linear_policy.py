"""Hashable linear live policy with an explicit closed-bar feature contract.

This is the small, auditable bridge model used while feature-complete DOIN
champions remain ineligible for live inference. The artifact is JSON rather
than pickle so another node can inspect and reproduce every coefficient.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


FEATURE_NAMES = (
    "return_1", "return_2", "return_3", "return_5", "return_10",
    "ema_ratio_5_20", "ema_ratio_10_50", "volatility_5", "volatility_20",
    "range_fraction_1", "volume_z20",
)


class LiveLinearPolicyError(RuntimeError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _finite(value: Any, name: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise LiveLinearPolicyError(f"non-finite {name}")
    return number


def _ema(values: Sequence[float], span: int) -> float:
    alpha = 2.0 / (span + 1.0)
    result = values[0]
    for value in values[1:]:
        result = alpha * value + (1.0 - alpha) * result
    return result


def _std(values: Sequence[float]) -> float:
    mean = sum(values) / len(values)
    return math.sqrt(sum((item - mean) ** 2 for item in values) / len(values))


def build_closed_bar_features(bars: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Build one causal feature vector from at least 51 completed bars."""
    if len(bars) < 51:
        raise LiveLinearPolicyError("at least 51 completed bars are required")
    normalized = []
    previous_time: datetime | None = None
    for bar in bars:
        if bar.get("complete") is not True:
            raise LiveLinearPolicyError("incomplete bar cannot enter live inference")
        timestamp = datetime.fromisoformat(str(bar["time"]).replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            raise LiveLinearPolicyError("bar timestamps must be timezone-aware")
        timestamp = timestamp.astimezone(timezone.utc)
        if previous_time is not None and timestamp <= previous_time:
            raise LiveLinearPolicyError("bars must be strictly time ordered")
        previous_time = timestamp
        values = {
            name: _finite(bar[name], name)
            for name in ("open", "high", "low", "close", "volume")
        }
        tolerance = max(abs(values["close"]), 1.0) * 1e-9
        if (
            values["low"] <= 0
            or values["close"] < values["low"] - tolerance
            or values["close"] > values["high"] + tolerance
        ):
            raise LiveLinearPolicyError("invalid OHLC geometry")
        normalized.append({"time": timestamp, **values})

    closes = [item["close"] for item in normalized]
    volumes = [item["volume"] for item in normalized]
    log_returns = [math.log(closes[index] / closes[index - 1]) for index in range(1, len(closes))]
    features = {
        "return_1": log_returns[-1],
        "return_2": sum(log_returns[-2:]),
        "return_3": sum(log_returns[-3:]),
        "return_5": sum(log_returns[-5:]),
        "return_10": sum(log_returns[-10:]),
        "ema_ratio_5_20": _ema(closes[-50:], 5) / _ema(closes[-50:], 20) - 1.0,
        "ema_ratio_10_50": _ema(closes[-50:], 10) / _ema(closes[-50:], 50) - 1.0,
        "volatility_5": _std(log_returns[-5:]),
        "volatility_20": _std(log_returns[-20:]),
        "range_fraction_1": (
            normalized[-1]["high"] - normalized[-1]["low"]
        ) / normalized[-1]["close"],
        "volume_z20": (
            volumes[-1] - sum(volumes[-20:]) / 20.0
        ) / max(_std(volumes[-20:]), 1e-12),
    }
    vector = [_finite(features[name], name) for name in FEATURE_NAMES]
    input_fact = {
        "feature_contract": "prediction_provider.closed_bars.linear.v1",
        "last_closed_bar": normalized[-1]["time"].isoformat(),
        "features": dict(zip(FEATURE_NAMES, vector)),
    }
    return {
        **input_fact,
        "input_sha256": hashlib.sha256(_canonical(input_fact)).hexdigest(),
    }


@dataclass(frozen=True)
class LiveLinearPolicy:
    model_id: str
    asset_id: str
    timeframe: str
    feature_names: tuple[str, ...]
    means: tuple[float, ...]
    scales: tuple[float, ...]
    coefficients: tuple[float, ...]
    intercept: float
    probability_threshold: float
    artifact_sha256: str

    @classmethod
    def load(cls, path: str | Path, expected_sha256: str | None = None) -> "LiveLinearPolicy":
        source = Path(path)
        payload_bytes = source.read_bytes()
        digest = hashlib.sha256(payload_bytes).hexdigest()
        if expected_sha256 is not None and digest != expected_sha256:
            raise LiveLinearPolicyError("linear policy artifact hash mismatch")
        data = json.loads(payload_bytes)
        if data.get("schema") != "prediction_provider.live_linear_policy.v1":
            raise LiveLinearPolicyError("unsupported live linear policy artifact")
        names = tuple(data.get("feature_names", ()))
        if names != FEATURE_NAMES:
            raise LiveLinearPolicyError("artifact feature order does not match runtime contract")
        means = tuple(map(float, data["means"]))
        scales = tuple(map(float, data["scales"]))
        coefficients = tuple(map(float, data["coefficients"]))
        if not len(names) == len(means) == len(scales) == len(coefficients):
            raise LiveLinearPolicyError("artifact vector dimensions disagree")
        if any(not math.isfinite(value) for value in (*means, *scales, *coefficients)):
            raise LiveLinearPolicyError("artifact contains a non-finite coefficient")
        if any(value <= 0 for value in scales):
            raise LiveLinearPolicyError("artifact scales must be positive")
        threshold = float(data.get("probability_threshold", 0.5))
        if not 0.5 <= threshold < 1.0:
            raise LiveLinearPolicyError("probability_threshold must be in [0.5, 1)")
        return cls(
            model_id=str(data["model_id"]), asset_id=str(data["asset_id"]),
            timeframe=str(data["timeframe"]), feature_names=names,
            means=means, scales=scales, coefficients=coefficients,
            intercept=float(data["intercept"]), probability_threshold=threshold,
            artifact_sha256=digest,
        )

    def predict(self, observation: Mapping[str, Any]) -> dict[str, Any]:
        if observation.get("feature_contract") != "prediction_provider.closed_bars.linear.v1":
            raise LiveLinearPolicyError("observation feature contract mismatch")
        features = observation.get("features")
        if not isinstance(features, Mapping) or tuple(features) != self.feature_names:
            raise LiveLinearPolicyError("observation feature order mismatch")
        vector = [_finite(features[name], name) for name in self.feature_names]
        standardized = [
            (value - mean) / scale
            for value, mean, scale in zip(vector, self.means, self.scales)
        ]
        score = self.intercept + sum(
            coefficient * value
            for coefficient, value in zip(self.coefficients, standardized)
        )
        probability_up = 1.0 / (1.0 + math.exp(-max(-60.0, min(60.0, score))))
        if probability_up >= self.probability_threshold:
            action = "long"
        elif probability_up <= 1.0 - self.probability_threshold:
            action = "short"
        else:
            action = "hold"
        output = {
            "schema": "prediction_provider.live_linear_inference.v1",
            "model_id": self.model_id,
            "artifact_sha256": self.artifact_sha256,
            "asset_id": self.asset_id,
            "timeframe": self.timeframe,
            "last_closed_bar": observation["last_closed_bar"],
            "input_sha256": observation["input_sha256"],
            "probability_up": probability_up,
            "action": action,
        }
        output["output_sha256"] = hashlib.sha256(_canonical(output)).hexdigest()
        return output
