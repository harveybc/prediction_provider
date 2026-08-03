import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest

from prediction_provider_mechanics.live_linear_policy import (
    FEATURE_NAMES,
    LiveLinearPolicy,
    LiveLinearPolicyError,
    build_closed_bar_features,
)


def _bars(count=60):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        {
            "time": (start + timedelta(days=index)).isoformat(),
            "open": 100 + index, "high": 102 + index, "low": 99 + index,
            "close": 101 + index, "volume": 1000 + index * 10,
            "complete": True,
        }
        for index in range(count)
    ]


def _artifact(path):
    payload = {
        "schema": "prediction_provider.live_linear_policy.v1",
        "model_id": "test-v1", "asset_id": "equity:SPY", "timeframe": "1d",
        "feature_names": list(FEATURE_NAMES),
        "means": [0.0] * len(FEATURE_NAMES),
        "scales": [1.0] * len(FEATURE_NAMES),
        "coefficients": [1.0] * len(FEATURE_NAMES),
        "intercept": 0.0, "probability_threshold": 0.5,
    }
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_closed_bar_features_are_deterministic_and_causal():
    first = build_closed_bar_features(_bars())
    second = build_closed_bar_features(_bars())
    assert first == second
    assert tuple(first["features"]) == FEATURE_NAMES
    with pytest.raises(LiveLinearPolicyError, match="incomplete"):
        bars = _bars()
        bars[-1]["complete"] = False
        build_closed_bar_features(bars)


def test_policy_hash_and_feature_contract_are_enforced(tmp_path):
    path = tmp_path / "model.json"
    digest = _artifact(path)
    policy = LiveLinearPolicy.load(path, digest)
    result = policy.predict(build_closed_bar_features(_bars()))
    assert result["model_id"] == "test-v1"
    assert result["action"] in {"long", "short", "hold"}
    with pytest.raises(LiveLinearPolicyError, match="hash mismatch"):
        LiveLinearPolicy.load(path, "0" * 64)


def test_policy_rejects_feature_order_drift(tmp_path):
    path = tmp_path / "model.json"
    _artifact(path)
    policy = LiveLinearPolicy.load(path)
    observation = build_closed_bar_features(_bars())
    observation["features"] = dict(reversed(list(observation["features"].items())))
    with pytest.raises(LiveLinearPolicyError, match="feature order"):
        policy.predict(observation)
