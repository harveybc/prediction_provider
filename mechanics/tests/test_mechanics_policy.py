"""Mechanics policy and loader tests, including the R1 golden parity fixture."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from prediction_provider_mechanics import (
    ArtifactVerificationError,
    MechanicsPolicy,
    MechanicsPolicyConfig,
    MechanicsPolicyError,
    verify_artifact,
)
from trading_contracts import canonical_json

BAR = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
GOLDEN = Path(__file__).parent / "fixtures" / "golden_asset_intent.json"


def _config(**overrides):
    base = {
        "cell_id": "fx:USD/CAD@4h:mech:policy",
        "asset_id": "fx:USD/CAD",
        "target_exposure_magnitude": 0.5,
        "stop_fraction": 0.01,
        "take_profit_fraction": 0.02,
        "validity_hours": 4.0,
        "policy_version": "0.1.0",
    }
    base.update(overrides)
    return MechanicsPolicyConfig.from_dict(base)


def _observation(**overrides):
    base = {
        "bar_time": BAR,
        "reference_price": 1.25,
        "quote_hash": "sha256:" + "9" * 64,
    }
    base.update(overrides)
    return base


def test_intent_is_labeled_mechanics_only():
    intent = MechanicsPolicy(_config()).decide(_observation())
    assert "mechanics_only_not_alpha_claim" in intent.reason_codes


def test_intent_carries_config_and_input_hashes():
    policy = MechanicsPolicy(_config())
    intent = policy.decide(_observation())
    assert intent.artifact_hash == policy.config_hash
    assert intent.config_hash == policy.config_hash
    assert any(code.startswith("input:sha256:") for code in intent.reason_codes)


def test_direction_is_deterministic_and_exercises_both_sides():
    policy = MechanicsPolicy(_config())
    directions = {
        policy.direction(datetime(2026, 8, 2, hour, 0, tzinfo=timezone.utc))
        for hour in range(12)
    }
    assert directions == {1, -1}
    assert policy.direction(BAR) == policy.direction(BAR)


def test_protection_geometry_matches_side():
    policy = MechanicsPolicy(_config())
    intent = policy.decide(_observation())
    geometry = intent.risk_geometry
    if intent.target_exposure > 0:
        assert geometry.stop_price < 1.25 < geometry.take_profit_price
    else:
        assert geometry.stop_price > 1.25 > geometry.take_profit_price


def test_identical_input_produces_byte_identical_canonical_output():
    first = MechanicsPolicy(_config()).decide(_observation())
    second = MechanicsPolicy(_config()).decide(_observation())
    assert canonical_json(first.model_dump(mode="json")) == canonical_json(
        second.model_dump(mode="json")
    )


def test_golden_parity_fixture_byte_equivalence():
    """R1 gate 4: the future service endpoint must reproduce these exact
    bytes for this exact input. The fixture is the frozen truth."""
    intent = MechanicsPolicy(_config()).decide(_observation())
    produced = canonical_json(intent.model_dump(mode="json"))
    assert GOLDEN.read_text().strip() == produced


@pytest.mark.parametrize("mutation", [
    {"bar_time": datetime(2026, 8, 2, 12, 0)},           # naive datetime
    {"reference_price": 0.0},
    {"reference_price": -1.0},
    {"reference_price": True},                            # bool is not a price
    {"quote_hash": ""},
])
def test_malformed_observation_fails_closed(mutation):
    with pytest.raises(MechanicsPolicyError):
        MechanicsPolicy(_config()).decide(_observation(**mutation))


def test_config_bounds_fail_closed():
    with pytest.raises(MechanicsPolicyError):
        _config(target_exposure_magnitude=1.5)
    with pytest.raises(MechanicsPolicyError):
        _config(stop_fraction=0.0)
    with pytest.raises(MechanicsPolicyError):
        _config(validity_hours=-1)


# ── hash-verified loading ──

def test_verify_artifact_accepts_exact_hash(tmp_path):
    artifact = tmp_path / "champion.zip"
    artifact.write_bytes(b"frozen-policy-bytes")
    digest = hashlib.sha256(b"frozen-policy-bytes").hexdigest()
    assert verify_artifact(artifact, f"sha256:{digest}") == b"frozen-policy-bytes"
    assert verify_artifact(artifact, digest) == b"frozen-policy-bytes"


def test_verify_artifact_rejects_mismatch(tmp_path):
    artifact = tmp_path / "champion.zip"
    artifact.write_bytes(b"tampered-bytes")
    with pytest.raises(ArtifactVerificationError, match="mismatch"):
        verify_artifact(artifact, "sha256:" + "0" * 64)


def test_verify_artifact_rejects_bad_expected_hash(tmp_path):
    artifact = tmp_path / "champion.zip"
    artifact.write_bytes(b"x")
    with pytest.raises(ArtifactVerificationError, match="sha256 hex"):
        verify_artifact(artifact, "not-a-hash")


def test_verify_artifact_rejects_missing_file(tmp_path):
    with pytest.raises(ArtifactVerificationError, match="unreadable"):
        verify_artifact(tmp_path / "absent.zip", "sha256:" + "0" * 64)
