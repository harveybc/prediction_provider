"""The first bundle here with a predictive distribution, and the three ways an interval is still refused.

Until WP07 every bundle this package served was a point model, so `interval` was declared and refused by all of them
with one reason. A quantile bundle changes exactly one thing: the pair of quantiles it FITTED can be published as an
interval. Everything around that stays a refusal, and these tests are mostly about the refusals, because that is where a
number would otherwise be invented:

* a bundle with no quantile head still refuses `interval` with `NOT_ESTIMABLE` -- the point bundle's behaviour must not
  change because another bundle gained a head;
* a confidence level with no fitted pair is refused by name (`CONFIDENCE_LEVEL_NOT_FITTED`) with the levels that exist.
  `[0.05, 0.5, 0.95]` fits ONE two-sided level, 0.90. A 0.95 interval is not 0.90 widened, and the harness's 0.95
  question is refused by this bundle too -- with a different code, which is the whole point;
* `anomaly_risk` stays refused even with quantiles: three points of a distribution are not the distribution.

The rules above are settled before any graph loads, so they are tested against METADATA FIXTURES -- manifests with no
weights behind them. The one test that needs real numbers uses the bundle exported from predictor's WP07 fit, named by
`M5PHET_FORECAST_QUANTILE_BUNDLE`, and skips rather than fabricating one.
"""

import json
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from prediction_provider_forecast import ForecastProvider                                        # noqa: E402
from prediction_provider_forecast.provider import (CONFIDENCE_LEVEL_NOT_FITTED, MALFORMED_QUESTION,  # noqa: E402
                                                   NOT_ESTIMABLE, UNMEASURED, digest)
from test_multi_bundle import metadata_bundle                                                    # noqa: E402

QUANTILES = [0.05, 0.5, 0.95]


def quantile_metadata_bundle(root, name, **overrides):
    """A v2 metadata fixture that declares a quantile head. No graph: every rule below is settled before one loads."""
    declared = {"heads": ["quantile"], "quantiles": list(QUANTILES), "unit": "kW", "scale": "original",
                "readout": "identity", "horizons": [60]}
    declared.update(overrides)
    return metadata_bundle(root, name, state_id=name, target="Global_active_power", **declared)


# ------------------------------------------------------------------ what a bundle is allowed to declare


def test_a_quantile_bundle_declares_its_head_its_quantiles_and_their_pairs(tmp_path):
    provider = ForecastProvider(quantile_metadata_bundle(tmp_path, "q-bundle"))
    bundle = provider._bundles[0]
    assert bundle.heads == ["quantile"] and bundle.quantiles == QUANTILES
    assert bundle.median_index == 1
    # one target, one horizon, three quantiles: the graph emits three numbers, not one
    assert bundle.width == 3
    # 0.05 and 0.95 are symmetric, so they cover 0.90 -- and nothing else is claimed
    assert bundle.fitted_levels() == {0.9: (0.05, 0.95)}


def test_a_point_bundle_declares_no_quantiles_and_keeps_its_width(tmp_path):
    provider = ForecastProvider(metadata_bundle(tmp_path, "p-bundle", state_id="p-bundle", target="x"))
    bundle = provider._bundles[0]
    assert bundle.heads == ["point"] and bundle.quantiles == [] and bundle.width == 1
    assert bundle.fitted_levels() == {}


@pytest.mark.parametrize("broken, why", [
    ({"quantiles": [0.05, 0.95]}, "must fit the median"),
    ({"quantiles": [0.5]}, "at least two quantiles"),
    ({"quantiles": [0.95, 0.5, 0.05]}, "strictly ascending"),
    ({"quantiles": [0.0, 0.5, 0.95]}, "strictly inside"),
    ({"quantiles": [0.05, 0.5, 1.5]}, "strictly inside"),
    ({"heads": ["ensemble"], "quantiles": QUANTILES}, "distinct names"),
])
def test_a_quantile_set_that_is_not_one_is_refused_at_construction(tmp_path, broken, why):
    path = quantile_metadata_bundle(tmp_path, "broken", **broken)
    with pytest.raises(ValueError, match=why):
        ForecastProvider(path)


def test_quantiles_without_a_head_are_refused(tmp_path):
    path = metadata_bundle(tmp_path, "sneaky", state_id="sneaky", target="x", quantiles=QUANTILES)
    with pytest.raises(ValueError, match="no quantile head"):
        ForecastProvider(path)


def test_capabilities_name_the_interval_only_when_a_bundle_has_the_head(tmp_path):
    point = ForecastProvider(metadata_bundle(tmp_path / "a", "p", state_id="p", target="x")).capabilities()
    assert point["output_kinds"] == ["point_forecast"] and point["uncertainty_methods"] == ["none"]
    quantile = ForecastProvider(quantile_metadata_bundle(tmp_path / "b", "q")).capabilities()
    assert quantile["output_kinds"] == ["point_forecast", "interval"]
    assert quantile["uncertainty_methods"] == ["none", "fitted_quantiles"]


# ------------------------------------------------------------------ the refusals, before a graph is ever loaded


def ask(provider, state, question):
    return provider.answer_questions(state, {"q": question}, None, "2026-09-25T00:00:00+00:00")["q"]


def test_a_level_with_no_fitted_pair_is_refused_by_name_with_the_levels_that_exist(tmp_path):
    provider = ForecastProvider(quantile_metadata_bundle(tmp_path, "q-bundle"))
    answer = ask(provider, {"state_ref": provider.known_states()[0]},
                 {"type": "interval", "horizon": 60, "confidence_level": 0.95})
    assert answer["status"] == "REFUSED" and answer["refusal"] == CONFIDENCE_LEVEL_NOT_FITTED
    assert answer["type"] == "interval"
    assert "[0.9]" in answer["why"] and "not widened or narrowed" in answer["why"]
    assert not any(key in answer for key in ("values", "point"))


@pytest.mark.parametrize("level", [None, "0.9", 0, 1, 1.5, True])
def test_a_confidence_level_that_is_not_a_level_is_malformed(tmp_path, level):
    provider = ForecastProvider(quantile_metadata_bundle(tmp_path, "q-bundle"))
    answer = ask(provider, {"state_ref": provider.known_states()[0]},
                 {"type": "interval", "horizon": 60, "confidence_level": level})
    assert answer["refusal"] == MALFORMED_QUESTION and answer["type"] == "interval"


def test_a_point_bundle_still_refuses_the_interval_with_the_missing_head_named(tmp_path):
    provider = ForecastProvider(metadata_bundle(tmp_path, "p-bundle", state_id="p-bundle",
                                                target="Global_active_power", horizons=[60]))
    answer = ask(provider, {"state_ref": provider.known_states()[0]},
                 {"type": "interval", "horizon": 60, "confidence_level": 0.9})
    assert answer["refusal"] == NOT_ESTIMABLE
    assert "point estimate and no predictive distribution" in answer["why"]


def test_anomaly_risk_stays_refused_for_a_quantile_bundle_and_says_why(tmp_path):
    provider = ForecastProvider(quantile_metadata_bundle(tmp_path, "q-bundle"))
    answer = ask(provider, {"state_ref": provider.known_states()[0]},
                 {"type": "anomaly_risk", "threshold": "< 0.3"})
    assert answer["refusal"] == NOT_ESTIMABLE and answer["type"] == "anomaly_risk"
    assert "fitted quantiles" in answer["why"] and "interpolated" in answer["why"]


# ------------------------------------------------------------------ the real bundle: an interval with real numbers


@pytest.fixture
def quantile_bundle():
    root = os.environ.get("M5PHET_FORECAST_QUANTILE_BUNDLE")
    if not root or not (Path(root) / "manifest.json").is_file():
        pytest.skip("requires the exported WP07 quantile bundle named by M5PHET_FORECAST_QUANTILE_BUNDLE; "
                    "no synthetic fallback")
    return Path(root)


def real_provider(path):
    provider = ForecastProvider(path)
    return provider, provider.known_states()[0], json.loads((path / "example_request.json").read_text())["data"]


def test_the_real_quantile_bundle_answers_its_fitted_interval(quantile_bundle):
    provider, state_ref, data = real_provider(quantile_bundle)
    answers = provider.answer_questions(
        {"state_ref": state_ref},
        {"p": {"type": "point_forecast", "horizon": 60},
         "i": {"type": "interval", "horizon": 60, "confidence_level": 0.9},
         "n": {"type": "interval", "horizon": 60, "confidence_level": 0.95}},
        data, "2026-09-25T00:00:00+00:00")
    point, interval, refused = answers["p"], answers["i"], answers["n"]
    assert interval["type"] == "interval" and interval["confidence_level"] == 0.9
    assert interval["quantiles"] == [0.05, 0.95]
    low, high = interval["values"][0]
    # the head is built so the quantiles cannot cross, and the median it publishes as the point lies between them
    assert low < high and low <= interval["point"] <= high
    assert interval["point"] == point["values"][0]
    assert interval["unit"] == "kW" and interval["scale"] == "original"
    assert interval["uncertainty"] == "fitted_quantiles"
    assert interval["execution_authorized"] is False
    assert refused["refusal"] == CONFIDENCE_LEVEL_NOT_FITTED


def test_the_real_quantile_bundle_publishes_no_quality_of_its_own(quantile_bundle):
    manifest = json.loads((quantile_bundle / "manifest.json").read_text())
    provenance = manifest["provenance"]
    # the numbers measured on the sealed holdout belong to the evaluation report that measured them; the bundle names
    # that report and its seal, and claims nothing itself
    assert provenance["quality"] == UNMEASURED
    assert provenance["evaluation"]["corpus_seal"] and provenance["evaluation"]["protocol_digest"]
    assert manifest["exposure"] == "DEV_FIT_HOLDOUT_SEALED_BEFORE_SCORING"
    assert manifest["heads"] == ["quantile"] and manifest["quantiles"] == QUANTILES
    assert manifest["scaler_digest"] == digest(manifest["scaler"])


def test_the_real_quantile_bundle_takes_raw_rows_like_every_other_bundle(quantile_bundle):
    provider, state_ref, _ = real_provider(quantile_bundle)
    bundle = provider._bundle(state_ref)
    columns, window = bundle.manifest["columns"], bundle.manifest["window"]
    rows = [{name: float(i + position) for position, name in enumerate(columns)} for i in range(window)]
    answer = provider.answer_questions({"state_ref": state_ref},
                                       {"i": {"type": "interval", "horizon": 60, "confidence_level": 0.9}},
                                       rows, "2026-09-25T00:00:00+00:00")["i"]
    assert answer["type"] == "interval" and answer["values"][0][0] < answer["values"][0][1]
