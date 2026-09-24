import copy
import importlib.metadata
import json
import os

import numpy as np
import pytest

from prediction_provider_forecast import ForecastProvider
from prediction_provider_forecast.provider import digest


def test_discovery_without_tensorflow_import():
    import subprocess
    import sys
    code = """
import sys
from importlib.metadata import entry_points
ep = next(e for e in entry_points(group='m5phet.providers') if e.name == 'predictor_forecast')
p = ep.load()()
assert p.name == 'predictor_forecast'
assert 'tensorflow' not in sys.modules
assert p.capabilities()['supported'] == [{'operation': 'infer', 'family': 'regression_forecasting', 'output_kind': 'point_forecast'}]
"""
    subprocess.run([sys.executable, "-c", code], check=True)


def test_unconfigured_is_not_fitted(monkeypatch):
    monkeypatch.delenv("M5PHET_FORECAST_BUNDLE", raising=False)
    p = ForecastProvider()
    assert p.known_states() == []
    with pytest.raises(ValueError, match="unknown fitted state"):
        p.load("missing")


@pytest.fixture
def bundle():
    path = os.environ.get("M5PHET_FORECAST_TEST_BUNDLE")
    if not path:
        pytest.skip("requires an exported real trained DEV bundle; no synthetic fallback")
    from pathlib import Path
    return Path(path)


@pytest.fixture
def ready(bundle):
    p = ForecastProvider(bundle)
    request = json.loads((bundle / "example_request.json").read_text())
    return p, request


def test_real_native_parity_and_restart(ready, bundle):
    p, req = ready
    original = copy.deepcopy(req)
    state = p.load(req["fitted_state_ref"])
    result = p.infer(req, copy.deepcopy(state))
    evidence = json.loads((bundle / "parity.json").read_text())
    target = req["output_schema"]["targets"][0]
    payload = result["outputs"][target]["payload"]
    assert payload["targets"] == [target]
    assert payload["horizons"] == [60]
    assert payload["unit"] == "kW"
    assert payload["scale"] == "original"
    np.testing.assert_allclose(payload["values"], evidence["native_values"], rtol=1e-6, atol=1e-6)
    assert req == original
    restarted = ForecastProvider(bundle)
    assert restarted.infer(req, restarted.load(req["fitted_state_ref"])) == result
    assert result["population"] == req["population"]


@pytest.mark.parametrize("path,value", [
    (("operation",), "fit"),
    (("family",), "classification"),
    (("output_kind",), "marginal_quantiles"),
    (("task_id",), "other"),
    (("as_of",), "not-a-time"),
    (("output_schema", "horizons"), [1]),
    (("output_schema", "horizons"), [True]),
    (("output_schema", "targets"), ["Voltage"]),
    (("output_schema", "unit"), "W"),
    (("data", "scale"), "raw"),
    (("data", "scaler_digest"), "wrong"),
    (("data", "values"), [[0.0]]),
    (("data", "columns"), ["wrong"]),
])
def test_refuses_mismatched_request_before_engine_load(ready, path, value):
    p, req = ready
    node = req
    for part in path[:-1]:
        node = node[part]
    node[path[-1]] = value
    with pytest.raises(ValueError):
        p.infer(req, {"digest": "untrusted"})
    assert p._engine is None


@pytest.mark.parametrize("value", [True, "1", None, float("nan"), float("inf")])
def test_numeric_refusals(ready, value):
    p, req = ready
    req["data"]["values"][0][0] = value
    with pytest.raises(ValueError):
        p.infer(req, {})
    assert p._engine is None


def test_no_stale_or_forged_state(ready):
    p, req = ready
    state = p.load(req["fitted_state_ref"])
    state["digest"] = "wrong"
    with pytest.raises(ValueError, match="state"):
        p.infer(req, state)


def test_perturbation_reaches_real_engine(ready):
    p, req = ready
    state = p.load(req["fitted_state_ref"])
    first = p.infer(req, state)
    req["data"]["values"][-1][-1] += 0.5
    req["population"] = {"input_sha256": digest(req["data"])}
    assert p.infer(req, state) != first


def test_tampered_bundle_refused(bundle, tmp_path):
    import shutil
    target = tmp_path / "bundle"
    shutil.copytree(bundle, target)
    p = ForecastProvider(target)
    model_file = target / "saved_model" / "saved_model.pb"
    with model_file.open("ab") as out:
        out.write(b"corrupt")
    with pytest.raises(ValueError, match="hash"):
        p.load(p.known_states()[0])
    assert p._engine is None


def test_chat_is_typed_and_does_not_load_model(ready):
    p, req = ready
    compiled = p.chat_request("forecast Global_active_power at 60 steps", req["data"],
                              chat_config(req))
    assert compiled["schema_version"] == "m5phet.task.draft2"
    assert compiled["output_schema"] == req["output_schema"]
    assert compiled["data"] == req["data"]
    assert p._engine is None


def chat_config(req):
    return {"input": "json", "provider": "predictor_forecast", "family": "regression_forecasting",
            "output_kind": "point_forecast", "state": req["fitted_state_ref"],
            "as_of": req["as_of"], "parameters": {}}


def test_chat_examples_are_ready_for_main_engine(ready):
    p, req = ready
    example = p.chat_examples()[0]
    assert "DEVELOPMENT" in example["title"]
    assert p._engine is None
    compiled = p.chat_request(example["prompt"], example["data"], example["config"])
    assert compiled["output_schema"] == req["output_schema"]
    assert p.infer(compiled, p.load(compiled["fitted_state_ref"]))["outputs"]["Global_active_power"]["status"] == "OK"


@pytest.mark.parametrize("prompt", ["forecast power", "predict tomorrow", "forecast Global_active_power at 1 steps",
                                    "forecast Global_active_power at 60 steps please", "" , "x" * 513])
def test_ambiguous_chat_rejected(ready, prompt):
    p, req = ready
    with pytest.raises(ValueError):
        p.chat_request(prompt, req["data"], chat_config(req))
