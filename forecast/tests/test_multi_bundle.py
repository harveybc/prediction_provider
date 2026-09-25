"""Several exported models behind one provider, and the refusals that keep them apart.

The area used to serve exactly one bundle, so a request could not name the wrong model: there was no other model to
name. With a directory of bundles that stops being true, and three new ways to answer the wrong question appear --
serving a bundle whose origin nobody recorded, answering a target two bundles share with whichever was enumerated
first, and quietly dropping a bundle that failed to validate so the remaining ones still look like the whole list.
These tests are about those three, and about the single-bundle path still behaving exactly as it did.

Most of them run against METADATA FIXTURES: manifests with no native graph behind them. That is deliberate. Every rule
under test is settled before any model is loaded, and fabricating a checkpoint to test a refusal would put untrained
weights behind something that looks like a real bundle. The one test that needs a real answer uses the real exported
household bundle and checks its recorded value, unchanged, from inside a directory of bundles.
"""

import json
import os
from pathlib import Path
import shutil

import pytest

from prediction_provider_forecast import ForecastProvider
from prediction_provider_forecast.provider import UNMEASURED, digest


#: the number the retained household bundle has always answered with. It is recorded here, in `parity.json` and in
#: `docs/VERIFICATION.json`; if serving several bundles changed it, the widening broke the model it was widening.
RECORDED_HOUSEHOLD_VALUE = 0.5412255525588989

GOOD_PROVENANCE = {"trained_on": "a fixture, on no data at all", "trained_by": "this test file",
                   "trained_at": "2026-09-24T00:00:00+00:00", "quality": UNMEASURED}


def metadata_bundle(root, name, *, state_id, target, horizons=(1,), family="binary_classification", **overrides):
    """A manifest with NO native graph behind it, for the rules that are settled before a graph is ever loaded."""
    columns = [target, "a_feature", "another_feature"]
    scaler = {"kind": "per_column_zscore", "fitted_on": "a fixture population, declared and fictional"}
    manifest = {
        "schema": "prediction_provider.forecast_bundle.v2", "engine": "tensorflow_saved_model",
        "exposure": "PREDICTOR_EXAMPLE_NO_EXPOSURE_RECEIPT", "state_id": state_id,
        "task_id": f"fixture.{state_id}", "title": f"DEVELOPMENT: metadata fixture {state_id}",
        "family": family, "columns": columns, "targets": [target], "horizons": [int(h) for h in horizons],
        "window": 4, "step_seconds": 3600, "unit": "probability", "scale": "probability",
        "readout": "identity", "input_scale": "fixture_scale",
        "horizon_meaning": "a fixture head index; nothing is trained behind it",
        "scaler": scaler, "scaler_digest": digest(scaler),
        "files": {"saved_model/saved_model.pb": "0" * 64},
        "provenance": dict(GOOD_PROVENANCE),
    }
    manifest.update(overrides)
    if "scaler" in overrides:
        manifest["scaler_digest"] = digest(manifest["scaler"])
    path = root / name
    path.mkdir(parents=True)
    (path / "manifest.json").write_text(json.dumps(manifest))
    return path


def window_for(provider, state_ref):
    bundle = provider._bundle(state_ref)
    return {"columns": list(bundle.manifest["columns"]),
            "values": [[0.0] * len(bundle.manifest["columns"]) for _ in range(bundle.manifest["window"])],
            "scale": bundle.input_scale, "scaler_digest": bundle.manifest["scaler_digest"]}


def chat_config(provider, state_ref):
    bundle = provider._bundle(state_ref)
    return {"input": "json", "provider": provider.name, "family": bundle.combination["family"],
            "output_kind": "point_forecast", "state": state_ref,
            "as_of": "2026-09-24T00:00:00Z", "parameters": {}}


@pytest.fixture
def two_bundles(tmp_path):
    """Two bundles that share nothing: one target each, one horizon each."""
    root = tmp_path / "bundles"
    metadata_bundle(root, "alpha", state_id="alpha", target="price_move", horizons=(3,),
                    family="regression_forecasting")
    metadata_bundle(root, "beta", state_id="beta", target="direction_long", horizons=(1,))
    return ForecastProvider(root)


@pytest.fixture
def overlapping_bundles(tmp_path):
    """Two bundles that both answer `direction_long` at horizon 1 -- two architectures, one question."""
    root = tmp_path / "bundles"
    metadata_bundle(root, "cnn", state_id="cnn", target="direction_long", horizons=(1,))
    metadata_bundle(root, "lstm", state_id="lstm", target="direction_long", horizons=(1,))
    return ForecastProvider(root)


@pytest.fixture
def household(tmp_path):
    path = os.environ.get("M5PHET_FORECAST_TEST_BUNDLE")
    if not path:
        pytest.skip("requires an exported real trained DEV bundle; no synthetic fallback")
    return Path(path)


# ---------------------------------------------------------------- 1. a directory of bundles is the whole list


def test_a_directory_enumerates_every_bundle_it_holds(two_bundles):
    p = two_bundles
    assert [ref.split(":")[0] for ref in p.known_states()] == ["alpha", "beta"]
    caps = p.capabilities()
    assert caps["known_states"] == p.known_states()
    assert caps["families"] == ["regression_forecasting", "binary_classification"]
    assert caps["supported"] == [{"operation": "infer", "family": "regression_forecasting",
                                  "output_kind": "point_forecast"},
                                 {"operation": "infer", "family": "binary_classification",
                                  "output_kind": "point_forecast"}]
    # no single output schema can stand for two contracts, so the singular field is empty and each state carries its own
    assert caps["output_schema"] is None
    assert [b["state_ref"] for b in caps["bundles"]] == p.known_states()
    assert [b["targets"] for b in caps["bundles"]] == [["price_move"], ["direction_long"]]


def test_slots_declare_the_union_and_nothing_beyond_it(two_bundles):
    p = two_bundles
    slots = {s["name"]: s for s in p.chat_slots()}
    assert slots["target"]["allowed"] == ["price_move", "direction_long"]
    assert slots["horizon"]["allowed"] == [3, 1]
    for slot in slots.values():
        # an alias for a value no configured bundle has would be a door into an untrained question
        assert set(slot["aliases"]) <= {str(v) for v in slot["allowed"]}
    # a column that is an input everywhere and a target nowhere is named as unsupported, not offered
    assert set(slots["target"]["known_unsupported"]) == {"a_feature", "another_feature"}
    assert "price_move" not in slots["target"]["known_unsupported"]


def test_a_bundle_that_shipped_no_example_contributes_none(two_bundles):
    # the fixtures carry no example_request.json, and nothing is invented to fill the gap
    assert two_bundles.chat_examples() == []


# ---------------------------------------------------------------- 2. one bundle, or a refusal naming the others


def test_a_target_only_one_bundle_has_resolves_to_that_bundle(two_bundles):
    p = two_bundles
    for target, horizon, state_id in [("price_move", 3, "alpha"), ("direction_long", 1, "beta")]:
        state_ref = next(ref for ref in p.known_states() if ref.startswith(state_id + ":"))
        request = p.chat_request("a paraphrase the workbench resolved", window_for(p, state_ref),
                                 chat_config(p, state_ref), parameters={"target": target, "horizon": horizon})
        assert request["fitted_state_ref"] == state_ref
        assert request["task_id"] == f"fixture.{state_id}"
        assert request["output_schema"]["targets"] == [target]
        assert request["output_schema"]["horizons"] == [horizon]
    assert p._engine is None


def test_a_target_two_bundles_share_is_refused_with_both_named(overlapping_bundles):
    p = overlapping_bundles
    first, second = p.known_states()
    with pytest.raises(ValueError) as refusal:
        p.chat_request("which way is it going?", window_for(p, first), chat_config(p, first),
                       parameters={"target": "direction_long", "horizon": 1})
    # both are named: answering with the one that happens to be enumerated first would hide which model replied
    assert first in str(refusal.value) and second in str(refusal.value)
    assert p._engine is None


def test_the_shared_target_is_still_declared_so_the_refusal_is_about_the_question(overlapping_bundles):
    slots = {s["name"]: s for s in overlapping_bundles.chat_slots()}
    assert slots["target"]["allowed"] == ["direction_long"]
    assert slots["horizon"]["allowed"] == [1]


def test_a_horizon_no_bundle_has_is_refused_with_the_vocabulary_named(two_bundles):
    p = two_bundles
    state_ref = p.known_states()[0]
    with pytest.raises(ValueError, match="price_move"):
        p.chat_request("further out, please", window_for(p, state_ref), chat_config(p, state_ref),
                       parameters={"target": "price_move", "horizon": 9})


def test_words_and_config_must_name_the_same_fitted_state(two_bundles):
    """The words resolved to one bundle and the config named the other. Neither silently wins."""
    p = two_bundles
    alpha, beta = p.known_states()
    config = dict(chat_config(p, alpha), state=beta)
    with pytest.raises(ValueError) as refusal:
        p.chat_request("mixed up", window_for(p, alpha), config,
                       parameters={"target": "price_move", "horizon": 3})
    assert alpha in str(refusal.value) and beta in str(refusal.value)


def test_two_bundles_cannot_publish_the_same_fitted_state(tmp_path):
    """The same manifest twice is the same state reference twice, and a request naming it could not say which it meant."""
    root = tmp_path / "bundles"
    metadata_bundle(root, "one", state_id="twin", target="direction_long")
    metadata_bundle(root, "two", state_id="twin", target="direction_long")
    with pytest.raises(ValueError, match="same fitted state"):
        ForecastProvider(root)


# ---------------------------------------------------------------- 3. provenance is a condition of being served


@pytest.mark.parametrize("provenance", [
    None,                                                       # no provenance at all
    {},                                                         # present but empty
    {k: v for k, v in GOOD_PROVENANCE.items() if k != "trained_by"},
    {k: v for k, v in GOOD_PROVENANCE.items() if k != "trained_at"},
    {k: v for k, v in GOOD_PROVENANCE.items() if k != "trained_on"},
    dict(GOOD_PROVENANCE, trained_by="   "),
    dict(GOOD_PROVENANCE, quality="validated"),                 # a claim this package never computed
])
def test_a_bundle_that_cannot_say_where_it_came_from_is_refused(tmp_path, provenance):
    root = tmp_path / "bundles"
    overrides = {} if provenance is None else {"provenance": provenance}
    path = metadata_bundle(root, "orphan", state_id="orphan", target="direction_long", **overrides)
    if provenance is None:
        manifest = json.loads((path / "manifest.json").read_text())
        del manifest["provenance"]
        (path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError) as refusal:
        ForecastProvider(root)
    assert "orphan" in str(refusal.value)


def test_one_unattributable_bundle_refuses_the_whole_directory(tmp_path):
    """A directory is the operator's deliberate list. Serving the rest and dropping the bad one would report a shorter
    list as if it were complete, and the bundle that was meant to be there would be missing without anyone being told."""
    root = tmp_path / "bundles"
    metadata_bundle(root, "good", state_id="good", target="direction_long")
    metadata_bundle(root, "orphan", state_id="orphan", target="price_move", provenance={})
    with pytest.raises(ValueError, match="orphan"):
        ForecastProvider(root)


def test_a_directory_with_no_bundles_is_refused_rather_than_served_empty(tmp_path):
    empty = tmp_path / "nothing"
    empty.mkdir()
    with pytest.raises(ValueError, match="neither an exported bundle nor a directory"):
        ForecastProvider(empty)


# ---------------------------------------------------------------- 4. the single-bundle path, unchanged


def test_a_single_bundle_path_behaves_exactly_as_before(household):
    p = ForecastProvider(household)
    evidence = json.loads((household / "parity.json").read_text())
    assert p.known_states() == ["e1-household-r0-s1:" + evidence["state_digest"]]
    caps = p.capabilities()
    assert caps["supported"] == [{"operation": "infer", "family": "regression_forecasting",
                                 "output_kind": "point_forecast"}]
    assert caps["families"] == ["regression_forecasting"]
    assert caps["input_schema"] == {"kind": "one_history_window", "scale": "train_standardized"}
    assert caps["output_schema"] == {"targets": ["Global_active_power"], "horizons": [60],
                                     "unit": "kW", "scale": "original"}
    assert len(p.chat_examples()) == 1
    assert p._engine is None


def test_the_real_bundle_answers_its_recorded_value_from_inside_a_directory(household, tmp_path):
    """The point of the whole exercise: widening the area must not move the one number it already answers."""
    root = tmp_path / "bundles"
    root.mkdir()
    shutil.copytree(household, root / "household")
    metadata_bundle(root, "sibling", state_id="sibling", target="direction_long")
    p = ForecastProvider(root)
    assert len(p.known_states()) == 2

    examples = p.chat_examples()
    assert len(examples) == 1                       # only the real bundle shipped one
    example = examples[0]
    request = p.chat_request(example["prompt"], example["data"], example["config"])
    result = p.infer(request, p.load(request["fitted_state_ref"]))
    payload = result["outputs"]["Global_active_power"]["payload"]
    evidence = json.loads((household / "parity.json").read_text())
    assert payload["values"] == [[RECORDED_HOUSEHOLD_VALUE]]
    assert payload["values"] == evidence["native_values"] == evidence["provider_values"]
    assert payload["unit"] == "kW" and payload["scale"] == "original"
    # the sibling is configured and enumerated, and it did not touch this answer
    assert any(ref.startswith("sibling:") for ref in p.known_states())

