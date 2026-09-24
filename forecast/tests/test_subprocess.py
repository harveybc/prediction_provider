"""Use a separately installed native interpreter; no model imports in the host."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


def test_real_native_process_without_tensorflow_in_host():
    bundle = os.environ.get("M5PHET_FORECAST_TEST_BUNDLE")
    if not bundle:
        pytest.skip("requires real DEV bundle")
    code = """
import sys
from prediction_provider_forecast import ForecastProvider
p = ForecastProvider()
example = p.chat_examples()[0]
request = p.chat_request(example['prompt'], example['data'], example['config'])
state = p.load(request['fitted_state_ref'])
result = p.infer(request, state)
assert 'tensorflow' not in sys.modules
assert result['outputs']['Global_active_power']['status'] == 'OK'
import json
print(json.dumps(result))
"""
    env = dict(os.environ, M5PHET_FORECAST_BUNDLE=bundle, M5PHET_FORECAST_PYTHON=sys.executable,
               CUDA_VISIBLE_DEVICES="")
    done = subprocess.run([sys.executable, "-c", code], env=env, check=True, capture_output=True,
                          text=True, timeout=90)
    actual = json.loads(done.stdout)["outputs"]["Global_active_power"]["payload"]["values"]
    expected = json.loads((Path(bundle) / "parity.json").read_text())["provider_values"]
    assert actual == expected
