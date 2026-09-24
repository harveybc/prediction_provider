"""Ordinary words reaching this exact fitted model, and nothing else reaching it at all.

The workbench turns a person's phrasing into parameters with `m5phet.interpret`, which may only CHOOSE among the values a
provider declares. That makes `chat_slots()` the whole of the provider's vocabulary: whatever it lists can be said in
ordinary English or Spanish and still arrive at the trained graph, and whatever it omits cannot arrive at all. So these
tests read the bundle's own manifest as the source of truth, exercise every alias the provider declares, and check that an
unsupported horizon or an untrained target is refused BY NAME rather than rounded to the one value that happens to exist.

Everything here runs against the real exported DEV bundle on CPU. Nothing trains, exports or touches held-out data; the one
execution is the same recorded forward pass the parity evidence already covers.
"""

import copy
import importlib.util
import json
import os
from pathlib import Path
import sys

import pytest

from prediction_provider_forecast import ForecastProvider


def _interpret_module():
    """The workbench's interpreter, unmodified and imported for real.

    The native forecast interpreter is deliberately minimal -- it carries TensorFlow and this provider, not the chat
    application -- so `import m5phet.interpret` usually fails there. Rather than settle for testing the declaration alone
    and leaving resolution to the workbench's own suite, we load the installed module from a sibling environment by file
    path: `interpret` imports nothing but the standard library, so loading it drags no other package in. If no copy is
    reachable the resolution tests skip, saying so, and the declaration tests below still run exhaustively."""
    try:
        import m5phet.interpret as installed
        return installed
    except ImportError:
        pass
    named = os.environ.get("M5PHET_INTERPRET_MODULE")
    candidates = [Path(named)] if named else []
    candidates += sorted(Path(sys.prefix).parent.glob("*/lib/python3*/site-packages/m5phet/interpret.py"))
    for path in candidates:
        if not path.is_file():
            continue
        spec = importlib.util.spec_from_file_location("m5phet_interpret_under_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    return None


INTERPRET = _interpret_module()
resolves = pytest.mark.skipif(INTERPRET is None,
                              reason="m5phet.interpret is not reachable from this interpreter; the slot declaration is "
                                     "still tested exhaustively and resolution belongs to the workbench's own suite")


def offline_interpret(prompt, slots):
    """Resolve with no language model configured, so every pass below is settled by the declared vocabulary alone."""
    return INTERPRET.interpret(prompt, slots, interpreter=INTERPRET.Interpreter(environ={}))


@pytest.fixture
def bundle():
    path = os.environ.get("M5PHET_FORECAST_TEST_BUNDLE")
    if not path:
        pytest.skip("requires an exported real trained DEV bundle; no synthetic fallback")
    return Path(path)


@pytest.fixture
def manifest(bundle):
    return json.loads((bundle / "manifest.json").read_text())


@pytest.fixture
def ready(bundle):
    p = ForecastProvider(bundle)
    request = json.loads((bundle / "example_request.json").read_text())
    return p, request


def chat_config(req):
    return {"input": "json", "provider": "predictor_forecast", "family": "regression_forecasting",
            "output_kind": "point_forecast", "state": req["fitted_state_ref"],
            "as_of": req["as_of"], "parameters": {}}


def slot(slots, name):
    return next(s for s in slots if s["name"] == name)


# ---------------------------------------------------------------- 1. the declaration is exactly the bundle's own


def test_slots_enumerate_the_bundle_and_nothing_else(ready, manifest):
    p, _ = ready
    slots = p.chat_slots()
    assert [s["name"] for s in slots] == ["target", "horizon"]
    assert slot(slots, "target")["allowed"] == manifest["targets"]
    assert slot(slots, "horizon")["allowed"] == [int(h) for h in manifest["horizons"]]
    assert all(type(h) is int for h in slot(slots, "horizon")["allowed"])
    for s in slots:
        # an alias for a value the bundle does not have would be a door into an untrained question
        assert set(s.get("aliases") or {}) <= {str(v) for v in s["allowed"]}
        assert all(alias.strip() for names in (s.get("aliases") or {}).values() for alias in names)


def test_input_columns_are_not_offered_as_targets(ready, manifest):
    p, _ = ready
    declared = slot(p.chat_slots(), "target")
    spoken = {a.lower() for names in declared["aliases"].values() for a in names} | {v.lower() for v in declared["allowed"]}
    for column in manifest["columns"]:
        if column not in manifest["targets"]:
            assert column.lower() not in spoken
            assert column.replace("_", " ").lower() not in spoken


def test_unconfigured_provider_declares_no_vocabulary(monkeypatch):
    monkeypatch.delenv("M5PHET_FORECAST_BUNDLE", raising=False)
    assert ForecastProvider().chat_slots() == []


@resolves
def test_every_declared_alias_resolves_to_its_own_value(ready, manifest):
    p, _ = ready
    slots = p.chat_slots()
    target_names = ["Global_active_power"] + list(slot(slots, "target")["aliases"]["Global_active_power"])
    horizon_names = ["60 steps"] + list(slot(slots, "horizon")["aliases"]["60"])
    for spoken in target_names:
        report = offline_interpret(f"forecast {spoken} at 60 steps", slots)
        assert report["status"] == INTERPRET.STATUS_OK, (spoken, report["why"] if "why" in report else report)
        assert report["parameters"] == {"target": manifest["targets"][0], "horizon": 60}
    for spoken in horizon_names:
        report = offline_interpret(f"forecast Global_active_power {spoken} ahead", slots)
        assert report["status"] == INTERPRET.STATUS_OK, (spoken, report.get("why"))
        assert report["parameters"]["horizon"] == int(manifest["horizons"][0])


# ---------------------------------------------------------------- 2. paraphrases that must reach the model


@resolves
@pytest.mark.parametrize("prompt", [
    "forecast Global_active_power at 60 steps",              # what the engine itself says
    "what will household power be an hour ahead?",           # what a person says
    "¿cuál será el consumo de potencia dentro de una hora?",  # what a person says in Spanish
])
def test_paraphrases_reach_the_declared_parameters(ready, manifest, prompt):
    p, _ = ready
    report = offline_interpret(prompt, p.chat_slots())
    assert report["status"] == INTERPRET.STATUS_OK, report.get("why")
    assert report["parameters"] == {"target": manifest["targets"][0], "horizon": int(manifest["horizons"][0])}
    # the words alone settled it: no language model was consulted, so no model chose anything here
    assert report["interpreter"] is None
    assert set(report["sources"].values()) == {"QUESTION_TEXT"}


# ---------------------------------------------------------------- 3. refusals that must not reach the model


@resolves
def test_unsupported_horizon_is_refused_by_name_never_rounded(ready):
    p, _ = ready
    report = offline_interpret("forecast household power 90 steps ahead", p.chat_slots())
    assert report["status"] == INTERPRET.STATUS_UNSUPPORTED
    assert "90" in report["why"] and "60" in report["why"]
    # the one trained horizon is NOT quietly substituted for the one that was asked for
    assert "horizon" not in report["parameters"]


@resolves
def test_untrained_target_is_refused_with_the_vocabulary_named(ready, manifest):
    p, _ = ready
    report = offline_interpret("forecast the Voltage at 60 steps", p.chat_slots())
    # Two refusals are correct here and the workbench owns which one it gives: MISSING_PARAMETER when no target was
    # recognised at all, and UNSUPPORTED_VALUE once the interpreter matches the name against the `known_unsupported`
    # vocabulary this provider declares. What this test pins is the part that belongs to the provider -- Voltage never
    # becomes a parameter, and the refusal names the target it does have -- not which of the two labels came back.
    assert report["status"] in (INTERPRET.STATUS_MISSING, INTERPRET.STATUS_UNSUPPORTED)
    assert "target" in report["why"] and manifest["targets"][0] in report["why"]
    assert "target" not in report["parameters"]


@resolves
def test_naming_a_supported_and_an_unsupported_horizon_refuses_both(ready):
    p, _ = ready
    report = offline_interpret("forecast household power at 60 steps and at 90 steps", p.chat_slots())
    assert report["status"] == INTERPRET.STATUS_UNSUPPORTED
    assert "90" in report["why"]
    # answering the supported half of a two-part question would answer a question nobody asked
    assert report["parameters"] == {}


@pytest.mark.parametrize("parameters", [
    {"target": "Voltage", "horizon": 60},
    {"target": "Global_active_power", "horizon": 90},
    {"target": "Global_active_power", "horizon": 30},
    {"target": "Global_active_power"},
    {"horizon": 60},
])
def test_provider_refuses_parameters_outside_its_bundle(ready, parameters):
    """Defence in depth: even if something reached the provider with values the interpreter would never produce."""
    p, req = ready
    with pytest.raises(ValueError, match="Global_active_power"):
        p.chat_request("forecast household power an hour ahead", req["data"], chat_config(req), parameters=parameters)
    assert p._engine is None


# ---------------------------------------------------------------- 4. ambiguity, on a declaration this bundle does not have


@resolves
def test_two_targets_named_at_once_refuse_rather_than_choose():
    """This bundle declares one target, so the two-target case is built from a FABRICATED DECLARATION -- never from a
    fabricated bundle, which would put an untrained model behind a real answer. What is under test is the rule that a
    question naming two admissible values is refused with both named, not silently resolved to the first."""
    slots = [{"name": "target", "allowed": ["Global_active_power", "Global_reactive_power"],
              "aliases": {"Global_active_power": ["active power"], "Global_reactive_power": ["reactive power"]}},
             {"name": "horizon", "allowed": [60], "type": "integer", "aliases": {"60": ["one hour"]}},
             ]
    report = offline_interpret("forecast active power and reactive power one hour ahead", slots)
    assert report["status"] == INTERPRET.STATUS_AMBIGUOUS
    assert "Global_active_power" in report["why"] and "Global_reactive_power" in report["why"]
    assert "target" not in report["parameters"]
    # each one asked for on its own still resolves, so the refusal is about the question, not the declaration
    for spoken, expected in [("active power", "Global_active_power"), ("reactive power", "Global_reactive_power")]:
        alone = offline_interpret(f"forecast {spoken} one hour ahead", slots)
        assert alone["status"] == INTERPRET.STATUS_OK
        assert alone["parameters"]["target"] == expected


# ---------------------------------------------------------------- 5. the paraphrase reaches the recorded native value


RECORDED_NATIVE_VALUE = 0.5412255525588989


@resolves
def test_paraphrase_and_canonical_compile_to_one_request_and_the_recorded_value(ready, bundle):
    p, req = ready
    slots = p.chat_slots()
    spoken = "how much household power will we be using an hour from now?"
    report = offline_interpret(spoken, slots)
    assert report["status"] == INTERPRET.STATUS_OK, report.get("why")

    from_words = p.chat_request(spoken, req["data"], chat_config(req), parameters=report["parameters"])
    canonical = p.chat_request("forecast Global_active_power at 60 steps", req["data"], chat_config(req))
    assert from_words["request_id"] != canonical["request_id"]
    assert {k: v for k, v in from_words.items() if k != "request_id"} == \
           {k: v for k, v in canonical.items() if k != "request_id"}
    assert p._engine is None

    original = copy.deepcopy(from_words)
    state = p.load(from_words["fitted_state_ref"])
    result = p.infer(from_words, copy.deepcopy(state))
    payload = result["outputs"]["Global_active_power"]["payload"]
    evidence = json.loads((bundle / "parity.json").read_text())
    assert payload["values"] == [[RECORDED_NATIVE_VALUE]]
    assert payload["values"] == evidence["native_values"] == evidence["provider_values"]
    assert payload["targets"] == ["Global_active_power"] and payload["horizons"] == [60]
    assert payload["unit"] == "kW" and payload["scale"] == "original"
    assert from_words == original
    # the words changed; the question the model was asked did not
    assert p.infer(canonical, copy.deepcopy(state))["outputs"] == result["outputs"]
