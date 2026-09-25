"""Two fitted bundles for one series: which one answers, and when the question is genuinely ambiguous (WP06/WP07).

The household series now has two fitted engines -- the retained point bundle and the WP07 quantile bundle -- and the
provider used to refuse every sentence that named only the target. That refusal was correct in what it prevented
(answering with whichever bundle was enumerated first) and useless in practice: it asked the caller to type a fitted
state digest to ask for the power.

So the ambiguity is resolved by what the request DECLARES, in this order and no other:

1. the fitted state named by the state (`state_ref`) or by the config (`config["state"]`);
2. the bundle named by the question's `bundle` field -- a state_ref, a state_id, or a head only one candidate has;
3. the kind of answer asked for: an `interval` can only come from a bundle with a quantile head, and a
   `point_forecast` means the bundle WITHOUT one when exactly one has none.

Nothing else. A request that declares none of those is refused with every candidate named and the three ways above
spelled out, which is the only refusal that can be acted on.

Every rule here is settled before a graph loads, so the fixtures are manifests with no weights behind them.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from prediction_provider_forecast import ForecastProvider                                         # noqa: E402
from prediction_provider_forecast.provider import (NOT_ESTIMABLE, REPRESENTATION_NOT_RECORDED,    # noqa: E402
                                                   STATE_REQUIRED)
from test_multi_bundle import metadata_bundle, window_for                                         # noqa: E402

TARGET = "Global_active_power"
QUANTILES = [0.05, 0.5, 0.95]


@pytest.fixture
def household_pair(tmp_path):
    """One point bundle and one quantile bundle, the same series at the same horizon -- the owner's situation."""
    root = tmp_path / "bundles"
    metadata_bundle(root, "household-point", state_id="household-point", target=TARGET, horizons=(60,),
                    family="regression_forecasting", unit="kW", scale="original", readout="identity")
    metadata_bundle(root, "household-quantile", state_id="household-quantile", target=TARGET, horizons=(60,),
                    family="regression_forecasting", unit="kW", scale="original", readout="identity",
                    heads=["quantile"], quantiles=list(QUANTILES))
    return ForecastProvider(root)


def state_of(provider, state_id):
    return next(b.state_ref for b in provider._bundles if b.state_ref.startswith(state_id + ":"))


def ask(provider, questions, state=None):
    data = window_for(provider, provider.known_states()[0])
    return provider.answer_questions(state if state is not None else {"target_variable": TARGET},
                                     questions, data, "2026-09-25T00:00:00Z")


# ------------------------------------------------------------------ the kind of answer is a declaration


def test_an_interval_resolves_to_the_only_bundle_with_a_quantile_head(household_pair):
    answers = ask(household_pair, {"rango": {"type": "interval", "horizon": 60, "confidence_level": 0.9}})
    # it reaches the quantile bundle: the refusal, if any, is about the graph that is not there, never about WHICH
    assert answers["rango"].get("refusal") != STATE_REQUIRED


def test_a_point_forecast_resolves_to_the_only_bundle_without_a_quantile_head(household_pair):
    answers = ask(household_pair, {"p": {"type": "point_forecast", "horizon": 60}})
    assert answers["p"].get("refusal") != STATE_REQUIRED


def test_a_question_may_name_the_bundle_by_head_state_id_or_state_ref(household_pair):
    quantile = state_of(household_pair, "household-quantile")
    for named in ("quantile", "household-quantile", quantile):
        bundle, refusal = household_pair._resolve_question(
            {"target_variable": TARGET}, {"type": "point_forecast", "horizon": 60, "bundle": named})
        assert refusal is None and bundle.state_ref == quantile
    for named in ("point", "household-point"):
        bundle, refusal = household_pair._resolve_question(
            {"target_variable": TARGET}, {"type": "interval", "horizon": 60, "confidence_level": 0.9,
                                          "bundle": named})
        assert refusal is None and bundle.state_ref == state_of(household_pair, "household-point")


def test_a_bundle_name_no_candidate_carries_is_refused_and_says_how_a_bundle_is_named(household_pair):
    _, refusal = household_pair._resolve_question(
        {"target_variable": TARGET}, {"type": "point_forecast", "horizon": 60, "bundle": "lstm"})
    assert refusal["refusal"] == STATE_REQUIRED and "lstm" in refusal["why"] and "state_ref" in refusal["why"]


def test_the_state_and_the_question_must_name_the_same_engine(household_pair):
    _, refusal = household_pair._resolve_question(
        {"state_ref": state_of(household_pair, "household-point")},
        {"type": "point_forecast", "horizon": 60, "bundle": "quantile"})
    assert refusal["refusal"] == STATE_REQUIRED and "one request, one engine" in refusal["why"]


def test_a_question_both_bundles_refuse_is_refused_by_its_own_name_not_by_ambiguity(household_pair):
    """`anomaly_risk`: every candidate refuses it, so which one would have refused changes no answer."""
    answers = ask(household_pair, {"riesgo": {"type": "anomaly_risk", "threshold": "< 0.3"}})
    refusal = answers["riesgo"]
    assert refusal["refusal"] == NOT_ESTIMABLE
    assert all(ref in refusal["why"] for ref in household_pair.known_states())


def test_two_bundles_with_the_same_head_leave_the_kind_deciding_nothing(tmp_path):
    root = tmp_path / "bundles"
    for name in ("q-one", "q-two"):
        metadata_bundle(root, name, state_id=name, target=TARGET, horizons=(60,), family="regression_forecasting",
                        unit="kW", scale="original", readout="identity", heads=["quantile"],
                        quantiles=list(QUANTILES))
    provider = ForecastProvider(root)
    _, refusal = provider._resolve_question({"target_variable": TARGET},
                                            {"type": "interval", "horizon": 60, "confidence_level": 0.9})
    assert refusal["refusal"] == STATE_REQUIRED
    assert all(ref in refusal["why"] for ref in provider.known_states())


# ------------------------------------------------------------------ the slot the words (or Laya) resolve against


def test_the_bundle_slot_declares_every_engine_and_the_words_that_name_one(household_pair):
    slots = {slot["name"]: slot for slot in household_pair.chat_slots()}
    assert slots["bundle"]["allowed"] == household_pair.known_states()
    quantile = state_of(household_pair, "household-quantile")
    point = state_of(household_pair, "household-point")
    assert "quantile" in slots["bundle"]["aliases"][quantile]
    assert "rango" in slots["bundle"]["aliases"][quantile]
    assert "point" in slots["bundle"]["aliases"][point]
    # an alias names ONE bundle: a word both could answer to would settle nothing
    shared = set(slots["bundle"]["aliases"][quantile]) & set(slots["bundle"]["aliases"][point])
    assert shared == set()


def test_one_bundle_declares_no_bundle_slot(tmp_path):
    provider = ForecastProvider(metadata_bundle(tmp_path, "only", state_id="only", target=TARGET, horizons=(60,)))
    assert [slot["name"] for slot in provider.chat_slots()] == ["target", "horizon"]


# ------------------------------------------------------------------ WP06: what produced this bundle


def test_a_bundle_that_records_no_representation_is_served_as_not_recorded(household_pair):
    caps = household_pair.capabilities()
    assert [entry["representation_spec"] for entry in caps["bundles"]] == [REPRESENTATION_NOT_RECORDED] * 2
    assert [entry["heads"] for entry in caps["bundles"]] == [["point"], ["quantile"]]
    # what each engine can bound, declared before anyone asks for a level it never fitted
    assert [entry["fitted_confidence_levels"] for entry in caps["bundles"]] == [[], [0.9]]
    assert [entry["quantiles"] for entry in caps["bundles"]] == [[], QUANTILES]


def test_a_recorded_representation_is_served_verbatim(tmp_path):
    spec = {"schema": "m5phet.representation.v1", "windows": [74], "lags": [1, 74],
            "target": {"column": TARGET, "transform": "level"}, "candidate_id": "seasonal_lag_74"}
    provider = ForecastProvider(metadata_bundle(tmp_path, "designed", state_id="designed", target=TARGET,
                                                horizons=(60,), representation_spec=spec))
    assert provider.capabilities()["bundles"][0]["representation_spec"] == spec
    assert provider._bundles[0].representation_spec == spec


def test_a_representation_that_is_not_a_spec_is_refused_rather_than_served_as_absent(tmp_path):
    path = metadata_bundle(tmp_path, "vague", state_id="vague", target=TARGET, horizons=(60,),
                           representation_spec={"windows": [74]})
    with pytest.raises(ValueError, match="representation_spec"):
        ForecastProvider(path)


# ------------------------------------------------------------------ the window a sibling engine standardized


def scaled_bundle(root, name, *, mean, sd, columns, target=TARGET, **overrides):
    """A metadata fixture whose scaler is declared, so a re-standardisation can be checked by hand."""
    scaler = {"kind": "per_column_zscore", "mean": list(mean), "sd": list(sd), "fitted_on": "a declared fixture"}
    from prediction_provider_forecast.provider import digest as _digest
    return metadata_bundle(root, name, state_id=name, target=target, horizons=(60,),
                           family="regression_forecasting", unit="kW", scale="original",
                           readout="target_scaler_inverse", columns=list(columns), window=2,
                           scaler=scaler, scaler_digest=_digest(scaler), step_seconds=60, **overrides)


@pytest.fixture
def siblings(tmp_path):
    """Two engines of one series whose columns are in a different order and whose scalers differ."""
    root = tmp_path / "bundles"
    scaled_bundle(root, "point-engine", mean=[0.0, 10.0], sd=[1.0, 2.0], columns=[TARGET, "Voltage"])
    scaled_bundle(root, "quantile-engine", mean=[100.0, 1.0], sd=[10.0, 4.0], columns=["Voltage", TARGET],
                  heads=["quantile"], quantiles=list(QUANTILES))
    return ForecastProvider(root)


def test_a_window_a_sibling_standardized_is_re_expressed_in_this_engines_scale(siblings):
    point = next(b for b in siblings._bundles if b.state_ref.startswith("point-engine:"))
    quantile = next(b for b in siblings._bundles if b.state_ref.startswith("quantile-engine:"))
    attached = {"columns": [TARGET, "Voltage"], "values": [[1.0, 0.5], [-1.0, 0.0]],
                "scale": point.input_scale, "scaler_digest": point.manifest["scaler_digest"]}

    converted = siblings._window(attached, quantile)

    # the observations: Global_active_power 1*1+0 = 1 and -1*1+0 = -1; Voltage 0.5*2+10 = 11 and 0*2+10 = 10
    # in the quantile engine's own scale: Voltage (11-100)/10 = -8.9, power (1-1)/4 = 0.0
    assert converted["columns"] == ["Voltage", TARGET]
    assert converted["values"] == [[pytest.approx(-8.9), pytest.approx(0.0)],
                                   [pytest.approx(-9.0), pytest.approx(-0.5)]]
    assert converted["scaler_digest"] == quantile.manifest["scaler_digest"]
    # the window this engine already reads is returned untouched, byte for byte
    assert siblings._window(converted, quantile) is converted


def test_a_window_of_another_series_is_not_converted_and_is_still_refused(tmp_path):
    root = tmp_path / "bundles"
    scaled_bundle(root, "power", mean=[0.0, 10.0], sd=[1.0, 2.0], columns=[TARGET, "Voltage"])
    scaled_bundle(root, "other", mean=[0.0, 0.0], sd=[1.0, 1.0], columns=["price", "volume"], target="price")
    provider = ForecastProvider(root)
    power = next(b for b in provider._bundles if b.state_ref.startswith("power:"))
    other = next(b for b in provider._bundles if b.state_ref.startswith("other:"))
    attached = {"columns": [TARGET, "Voltage"], "values": [[1.0, 0.5], [-1.0, 0.0]],
                "scale": power.input_scale, "scaler_digest": power.manifest["scaler_digest"]}

    # a different column set is a different series: nothing is converted, and the request check refuses it as before
    assert provider._sibling_source(attached, other) is None
    assert provider._window(attached, other) is attached


def test_a_window_no_configured_engine_standardized_is_left_alone(siblings):
    quantile = next(b for b in siblings._bundles if b.state_ref.startswith("quantile-engine:"))
    foreign = {"columns": [TARGET, "Voltage"], "values": [[0.0, 0.0], [0.0, 0.0]],
               "scale": "train_standardized", "scaler_digest": "0" * 64}
    assert siblings._sibling_source(foreign, quantile) is None
    assert siblings._window(foreign, quantile) is foreign
