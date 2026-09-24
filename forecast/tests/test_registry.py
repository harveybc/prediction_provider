"""Optional integration with the actual M5PHET runtime; never patch its validator."""

import os
import json
from pathlib import Path

import numpy as np
import pytest

from prediction_provider_forecast import ForecastProvider


def test_actual_registry_contract():
    runtime = pytest.importorskip("m5phet.runtime")
    p = ForecastProvider()
    registry = runtime.Registry()
    registry.register(p)
    assert registry.get(p.name) is p
    assert registry.capabilities(p.name)["supported"] == p.capabilities()["supported"]


def test_actual_runtime_and_chat_example():
    runtime = pytest.importorskip("m5phet.runtime")
    bundle = os.environ.get("M5PHET_FORECAST_TEST_BUNDLE")
    if not bundle:
        pytest.skip("requires the real exported DEV bundle")
    p = ForecastProvider(bundle)
    example = p.chat_examples()[0]
    req = p.chat_request(example["prompt"], example["data"], example["config"])
    assert runtime.validate_request(req) == req
    registry = runtime.Registry()
    registry.register(p)
    result = runtime.run(req, registry)
    if "point_forecast" not in runtime.OUTPUT_SCHEMA_REQUIREMENTS:
        assert result["status"] == "UNSUPPORTED_TASK"
        assert p._engine is None
        pytest.skip("M5PHET owner has not installed point_forecast validation yet")
    assert result["status"] == "OK", result
    native = json.loads((Path(bundle) / "parity.json").read_text())["native_values"]
    np.testing.assert_allclose(result["outputs"]["Global_active_power"]["payload"]["values"],
                               native, rtol=1e-6, atol=1e-6)
    assert result["execution_authorized"] is False
