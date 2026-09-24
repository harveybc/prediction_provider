"""The question envelope over the real forecasting provider: a point forecast from the engine, a typed refusal for
everything the engine has no distribution for, and every refusal by name.

The owner's target shape asks one area three questions -- a point forecast, an interval, an anomaly risk -- and wants
each back under its own name. This provider serves point models: a graph that emits one number per target and horizon
and records no quantiles, no ensemble, no residual distribution. So the rule that overrides the shape is that no number
is invented: `point_forecast` is answered by the same `chat_request` -> `load` -> `infer` path the workbench already
takes, and `interval` and `anomaly_risk` are DECLARED so the shape is visible, then REFUSED with `NOT_ESTIMABLE` and a
reason that names the head the bundle does not have.

The point-forecast tests run the real exported bundles on CPU through the operator's native interpreter and check the
recorded parity values, unchanged. The ambiguity test uses metadata fixtures from `test_multi_bundle` -- manifests with
no graph behind them -- because the rule under test is settled before any model is loaded and a fabricated checkpoint
would put untrained weights behind something that looks like a real bundle. `m5phet` itself is not importable from
the native interpreter, so this module runs where the workbench runs and skips, saying so, elsewhere.
"""

import json
import os
from pathlib import Path

import pytest

questions = pytest.importorskip("m5phet.questions", reason="the question envelope lives in m5phet; run this module in "
                                                            "the workbench's interpreter")
from m5phet.questions import (MALFORMED_QUESTION, NOT_ESTIMABLE, STATE_REQUIRED, TASK_SCHEMA,   # noqa: E402
                              UNSUPPORTED_QUESTION_TYPE, catalog, run_task)
from m5phet.runtime import Registry                                                              # noqa: E402

from prediction_provider_forecast import ForecastProvider                                       # noqa: E402
from test_multi_bundle import RECORDED_HOUSEHOLD_VALUE, metadata_bundle                         # noqa: E402

#: the number the retained predictor direction_cnn bundle answered at export; recorded in its `parity.json` too
RECORDED_DIRECTION_PROBABILITY = 0.6035091876983643


@pytest.fixture
def bundles():
    root = os.environ.get("M5PHET_FORECAST_BUNDLE")
    if not root or not os.environ.get("M5PHET_FORECAST_PYTHON"):
        pytest.skip("requires the directory of exported real DEV bundles and the operator's native interpreter; "
                    "no synthetic fallback")
    return Path(root)


@pytest.fixture
def registry(bundles):
    r = Registry()
    r.register(ForecastProvider())
    return r


def history_of(bundles, name):
    """The DEV history export wrote after parity passed: the same object the workbench attaches."""
    return json.loads((bundles / name / "example_request.json").read_text())["data"]


def envelope(state, **named):
    return {"schema": TASK_SCHEMA, "area": "forecasting", "state": state, "questions": named}


# ---------------------------------------------------------------- the point forecast is the engine's own number


def test_a_point_forecast_is_the_recorded_household_value(registry, bundles):
    out = run_task(envelope({"target_variable": "Global_active_power", "frequency": "1min"},
                            prediccion={"type": "point_forecast", "horizon": 60}),
                   registry, data=history_of(bundles, "household-dev"))
    answer = out["answers"]["prediccion"]
    assert answer["status"] == "OK" and answer["type"] == "point_forecast"
    assert answer["values"] == [RECORDED_HOUSEHOLD_VALUE]
    assert answer["unit"] == "kW" and answer["scale"] == "original"
    assert answer["targets"] == ["Global_active_power"] and answer["horizons"] == [60]
    assert answer["execution_authorized"] is False and out["execution_authorized"] is False
    assert out["provider"] == "predictor_forecast"
    assert out["state_ref"] == answer["state_ref"] and out["state_ref"].startswith("e1-household-r0-s1:")
    assert out["answered"] == 1 and out["refused"] == 0


def test_a_point_forecast_is_the_recorded_direction_probability(registry, bundles):
    out = run_task(envelope({"target_variable": "direction_long"},
                            p={"type": "point_forecast", "horizon": 1}),
                   registry, data=[history_of(bundles, "predictor-direction-dev")])     # a list of one, as attached
    answer = out["answers"]["p"]
    assert answer["values"] == [RECORDED_DIRECTION_PROBABILITY]
    assert answer["unit"] == "probability" and answer["scale"] == "probability"
    assert out["state_ref"].startswith("phase-1c-direction-cnn-direction-long:")


def test_the_state_may_name_the_fitted_model_instead_of_the_series(registry, bundles):
    provider = registry.get("predictor_forecast")
    ref = next(r for r in provider.known_states() if r.startswith("e1-household-r0-s1:"))
    out = run_task(envelope({"state_ref": ref}, p={"type": "point_forecast", "horizon": 60}),
                   registry, data=history_of(bundles, "household-dev"))
    assert out["answers"]["p"]["values"] == [RECORDED_HOUSEHOLD_VALUE]


# ---------------------------------------------------------------- declared, refused, explained


@pytest.mark.parametrize("kind, question", [
    ("interval", {"type": "interval", "horizon": 60, "confidence_level": 0.95}),
    ("anomaly_risk", {"type": "anomaly_risk", "threshold": "< 100"}),
])
def test_a_distribution_question_is_refused_with_the_missing_head_named(registry, bundles, kind, question):
    out = run_task(envelope({"target_variable": "Global_active_power"}, q=question), registry,
                   data=history_of(bundles, "household-dev"))
    answer = out["answers"]["q"]
    assert answer["status"] == "REFUSED" and answer["refusal"] == NOT_ESTIMABLE and answer["type"] == kind
    assert "point estimate and no predictive distribution" in answer["why"]
    assert "quantile or ensemble head" in answer["why"]
    assert "e1-household-r0-s1:" in answer["why"]              # the refusal names the model it is about
    assert not any(k in answer for k in ("values", "lower_bounds", "upper_bounds", "probability", "flagged_steps"))


def test_the_types_are_declared_so_the_refusal_is_about_the_model_not_the_word(registry):
    declared = catalog(registry)["forecasting"]
    assert declared["provider"] == "predictor_forecast"
    assert set(declared["question_types"]) == {"point_forecast", "interval", "anomaly_risk"}
    assert declared["question_types"]["interval"]["required"] == ["horizon", "confidence_level"]
    assert declared["question_types"]["anomaly_risk"]["required"] == ["threshold"]


def test_a_mixed_request_gets_its_point_answer_and_its_typed_refusals_together(registry, bundles):
    out = run_task(envelope({"target_variable": "Global_active_power"},
                            prediccion={"type": "point_forecast", "horizon": 60},
                            rango={"type": "interval", "horizon": 60, "confidence_level": 0.95},
                            riesgo={"type": "anomaly_risk", "threshold": "< 100"},
                            otra={"type": "trend_break", "horizon": 60}),
                   registry, data=history_of(bundles, "household-dev"))
    assert list(out["answers"]) == ["prediccion", "rango", "riesgo", "otra"]
    assert out["answers"]["prediccion"]["values"] == [RECORDED_HOUSEHOLD_VALUE]
    assert out["answers"]["rango"]["refusal"] == NOT_ESTIMABLE and out["answers"]["rango"]["type"] == "interval"
    assert out["answers"]["riesgo"]["refusal"] == NOT_ESTIMABLE and out["answers"]["riesgo"]["type"] == "anomaly_risk"
    assert out["answers"]["otra"]["refusal"] == UNSUPPORTED_QUESTION_TYPE      # never reached the provider
    assert out["answered"] == 1 and out["refused"] == 3


# ---------------------------------------------------------------- refused by name, never rounded or guessed


def test_an_unsupported_horizon_is_refused_by_name_not_rounded(registry, bundles):
    out = run_task(envelope({"target_variable": "Global_active_power"},
                            p={"type": "point_forecast", "horizon": 30}),
                   registry, data=history_of(bundles, "household-dev"))
    answer = out["answers"]["p"]
    assert answer["refusal"] == NOT_ESTIMABLE and "values" not in answer
    assert "30" in answer["why"] and "[60]" in answer["why"] and "Global_active_power" in answer["why"]


def test_an_unknown_target_is_refused_with_the_available_ones_named(registry, bundles):
    out = run_task(envelope({"target_variable": "Voltage"}, p={"type": "point_forecast", "horizon": 60}),
                   registry, data=history_of(bundles, "household-dev"))
    answer = out["answers"]["p"]
    assert answer["refusal"] == NOT_ESTIMABLE and "'Voltage'" in answer["why"]
    assert "Global_active_power" in answer["why"] and "direction_long" in answer["why"]


def test_a_state_that_names_nothing_is_refused_before_any_engine(registry):
    out = run_task(envelope({"dataset_id": "household"}, p={"type": "point_forecast", "horizon": 60}), registry)
    assert out["answers"]["p"]["refusal"] == STATE_REQUIRED
    assert registry.get("predictor_forecast")._engine is None


def test_an_unknown_state_ref_is_refused_with_the_known_ones_named(registry):
    out = run_task(envelope({"state_ref": "nobody:0000"}, p={"type": "point_forecast", "horizon": 60}), registry)
    answer = out["answers"]["p"]
    assert answer["refusal"] == STATE_REQUIRED and "nobody:0000" in answer["why"]
    assert "e1-household-r0-s1:" in answer["why"]


def test_a_question_and_a_state_that_disagree_on_the_series_are_refused(registry):
    out = run_task(envelope({"target_variable": "Global_active_power"},
                            p={"type": "point_forecast", "horizon": 1, "target": "direction_long"}), registry)
    assert out["answers"]["p"]["refusal"] == MALFORMED_QUESTION


def test_a_target_two_bundles_hold_is_refused_with_both_named(tmp_path):
    """Fabricated with manifests only: two bundles, no graphs, one shared target. Which one would have answered is
    exactly the thing the refusal exists to not decide."""
    root = tmp_path / "bundles"
    metadata_bundle(root, "cnn", state_id="cnn", target="direction_long", horizons=(1,))
    metadata_bundle(root, "lstm", state_id="lstm", target="direction_long", horizons=(1,))
    provider = ForecastProvider(root)
    r = Registry()
    r.register(provider)
    first, second = provider.known_states()
    out = run_task(envelope({"target_variable": "direction_long"},
                            p={"type": "point_forecast", "horizon": 1},
                            i={"type": "interval", "horizon": 1, "confidence_level": 0.9}), r)
    for name in ("p", "i"):
        answer = out["answers"][name]
        assert answer["refusal"] == STATE_REQUIRED
        assert first in answer["why"] and second in answer["why"] and "state_ref" in answer["why"]
    assert out["state_ref"] is None and provider._engine is None
