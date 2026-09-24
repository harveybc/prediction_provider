"""Artifact-free refusal tests. Metadata fixtures are NOT trained checkpoints."""

import copy
import json

import pytest

from prediction_provider_forecast import ForecastProvider
from prediction_provider_forecast.export import export_dev
from prediction_provider_forecast.provider import digest


@pytest.fixture
def contract(tmp_path):
    scaler = {"mean": [0.0] * 7, "sd": [1.0] * 7, "fitted_on": "train windows only"}
    manifest = {
        "schema": "prediction_provider.forecast_bundle.v1", "engine": "tensorflow_saved_model",
        "exposure": "DEV_ONLY_NO_TEST_ACCESS", "task_id": "e1.household.W60_h60",
        "columns": ["Global_reactive_power", "Voltage", "Global_intensity", "Sub_metering_1",
                    "Sub_metering_2", "Sub_metering_3", "Global_active_power"],
        "targets": ["Global_active_power"], "horizons": [60], "window": 60, "step_seconds": 60,
        "unit": "kW", "scale": "original", "scaler": scaler, "scaler_digest": digest(scaler),
        "files": {"saved_model/saved_model.pb": "0" * 64},
        "provenance": {"test_fixture": "METADATA ONLY; deliberately no native graph exists"},
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    provider = ForecastProvider(tmp_path)
    data = {"columns": manifest["columns"], "values": [[0.0] * 7 for _ in range(60)],
            "scale": "train_standardized", "scaler_digest": digest(scaler)}
    config = {"input": "json", "provider": provider.name, "family": "regression_forecasting",
              "output_kind": "point_forecast", "state": provider.known_states()[0],
              "as_of": "2026-09-24T00:00:00Z", "parameters": {}}
    return provider, data, config


def test_compiler_with_full_web_config(contract):
    p, data, config = contract
    config.update(presentation="structured", context="", asset="EURUSD", language="en",
                  max_age_seconds=900, options=[["yes", "Yes"], ["no", "No"]])
    original = copy.deepcopy((data, config))
    request = p.chat_request("forecast Global_active_power at 60 steps", data, config)
    assert request["schema_version"] == "m5phet.task.draft2"
    assert request["population"] == {"input_sha256": digest(data)}
    assert request["execution_constraints"] == {"partial_results": False}
    assert p._engine is None
    assert (data, config) == original
    assert p.chat_request("forecast Global_active_power at 60 steps", data, config) == request


@pytest.mark.parametrize("field,value", [("provider", "other"), ("family", "classification"),
    ("output_kind", "marginal_quantiles"), ("state", "unknown"), ("input", "text"),
    ("as_of", "2026-09-24"), ("parameters", {"train": True}), ("parameters", {"request_id": ""})])
def test_config_refusal_without_native_engine(contract, field, value):
    p, data, config = contract
    config[field] = value
    with pytest.raises(ValueError):
        p.chat_request("forecast Global_active_power at 60 steps", data, config)
    assert p._engine is None


@pytest.mark.parametrize("value", [True, "1", None, float("inf"), float("nan"), 10 ** 400])
def test_number_refusal_without_native_engine(contract, value):
    p, data, config = contract
    request = p.chat_request("forecast Global_active_power at 60 steps", data, config)
    request["data"]["values"][0][0] = value
    with pytest.raises(ValueError):
        p._check_request(request)


def test_missing_checkpoint_is_not_fitted(contract):
    p, _, _ = contract
    with pytest.raises(ValueError, match="file set/hash"):
        p.load(p.known_states()[0])
    assert p._engine is None


def test_export_missing_artifacts_leaves_no_bundle(tmp_path):
    out = tmp_path / "out"
    with pytest.raises(FileNotFoundError, match="missing retained DEV artifact"):
        export_dev(tmp_path / "no-source", tmp_path / "no-run", out)
    assert not out.exists()
    assert not list(tmp_path.glob(".forecast-export-*"))


def test_export_does_not_overwrite(tmp_path):
    with pytest.raises(ValueError, match="already exists"):
        export_dev(tmp_path, tmp_path, tmp_path)


def test_no_future_labels_or_extra_rows(contract):
    p, data, config = contract
    data["labels"] = [2.0]
    with pytest.raises(ValueError, match="exactly"):
        p.chat_request("forecast Global_active_power at 60 steps", data, config)
    del data["labels"]
    data["values"].append([0.0] * 7)
    with pytest.raises(ValueError, match="60 chronological"):
        p.chat_request("forecast Global_active_power at 60 steps", data, config)
