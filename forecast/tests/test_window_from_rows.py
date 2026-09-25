"""Raw rows in, the engine's window out (WP16).

Until now a caller had to hand this provider a window that was ALREADY standardized with the bundle's scaler, digest
and all. A person with a CSV could not use the engine at all; a person who standardized it themselves could silently
use the wrong statistics and get a confident number from the wrong scale. `window_from_rows` closes both: it takes the
raw rows, selects the fitted columns BY NAME, standardizes them with the scaler read back out of the bundle's own
files (digest re-checked at call time, not merely at load time), takes the last `window` rows and returns exactly the
object the engine already accepted.

The load-bearing test here is the PARITY one: the shipped `example_request.json` window was written by `export.py`
from the DEV slice's standardized array, and rebuilding it from the ORIGINAL-UNIT rows of that same slice must land on
the same numbers. Everything else is a refusal by name -- a missing column, too few rows, an irregular clock, a value
that is not a number, a scaler whose bytes no longer hash to what the bundle declared. None of them may be answered.
"""

import copy
import csv
import io
import json
import os
from pathlib import Path
import shutil

import numpy as np
import pytest

from prediction_provider_forecast import ForecastProvider
from prediction_provider_forecast.provider import (IRREGULAR_SAMPLING, MISSING_COLUMNS, NON_NUMERIC,
                                                   SCALER_DIGEST_MISMATCH, TOO_FEW_ROWS, RowAdapterRefusal, digest,
                                                   rows_from_csv, window_from_rows)

#: the number the retained household bundle has always answered with (`parity.json`, `docs/VERIFICATION.json`).
RECORDED_HOUSEHOLD_VALUE = 0.5412255525588989

#: the tolerance the work package names for the parity: the rebuilt window must equal the shipped one to 1e-9.
PARITY_TOLERANCE = 1e-9


@pytest.fixture
def bundle_path():
    path = os.environ.get("M5PHET_FORECAST_TEST_BUNDLE")
    if not path:
        pytest.skip("requires an exported real trained DEV bundle; no synthetic fallback")
    return Path(path)


@pytest.fixture
def provider(bundle_path):
    return ForecastProvider(bundle_path)


@pytest.fixture
def bundle(provider):
    return provider._bundles[0]


@pytest.fixture
def shipped(bundle_path):
    return json.loads((bundle_path / "example_request.json").read_text())


def raw_rows_from_window(bundle, window):
    """Original-unit rows recovered from a standardized window, for the refusal fixtures.

    This is NOT the parity fixture -- inverting float32 and standardizing it again would prove only that the arithmetic
    is its own inverse. The parity test below uses the ACTUAL source rows. Here the numbers do not matter at all; what
    matters is that each fixture is a list of ordinary dicts with the bundle's column names, so a refusal is provoked
    by the thing the test names and by nothing else."""
    scaler = bundle.manifest["scaler"]
    mean, sd = np.asarray(scaler["mean"]), np.asarray(scaler["sd"])
    original = np.asarray(window, dtype=np.float64) * sd + mean
    return [{name: float(row[i]) for i, name in enumerate(bundle.manifest["columns"])} for row in original]


@pytest.fixture
def raw(bundle, shipped):
    return raw_rows_from_window(bundle, shipped["data"]["values"])


def source_rows():
    """The DEV slice in ORIGINAL units, as the WP06 export wrote it: one header, one row per minute, 50,400 rows.

    Not committed and not synthesizable: it is the owner's foundation slice. Point `M5PHET_FORECAST_TEST_ROWS` at it
    (or rebuild it from `~/.local/state/crispdm-data-foundation/e1_household_dev_pilot_v1/DATA.json`, reading only the
    declared slice) to run the parity. Skipping is honest; inventing rows would not be."""
    configured = os.environ.get("M5PHET_FORECAST_TEST_ROWS")
    if not configured or not Path(configured).is_file():
        pytest.skip("set M5PHET_FORECAST_TEST_ROWS to the household DEV slice in original units to run the parity")
    return list(csv.DictReader(Path(configured).read_text().splitlines()))


# ---------------------------------------------------------------------------------------------------- the parity

def test_the_shipped_example_window_is_rebuilt_from_its_source_rows(bundle, shipped):
    """The whole point of the adapter, proved against the one window whose standardized form was published.

    `export.py` took `Xs[origin - W + 1 : origin + 1]` of the DEV slice, where `origin` is recorded in the manifest's
    provenance as row 59. So the first 60 rows of the slice, in original units, must standardize to exactly the window
    `example_request.json` ships."""
    rows = source_rows()
    origin = bundle.manifest["provenance"]["origin_row_in_dev_slice"]
    window = bundle.manifest["window"]
    built = window_from_rows(rows[origin - window + 1:origin + 1], bundle)
    assert built["columns"] == shipped["data"]["columns"]
    assert built["scale"] == shipped["data"]["scale"]
    assert built["scaler_digest"] == shipped["data"]["scaler_digest"]
    error = np.max(np.abs(np.asarray(built["values"]) - np.asarray(shipped["data"]["values"])))
    assert error <= PARITY_TOLERANCE, error
    # and the whole object is the one the engine already accepted, bytes and all
    assert digest(built) == digest(shipped["data"])


def test_the_rebuilt_window_answers_the_recorded_number(provider, bundle, shipped):
    """Parity is only worth something if the native graph then answers what it always answered."""
    rows = source_rows()
    origin = bundle.manifest["provenance"]["origin_row_in_dev_slice"]
    built = window_from_rows(rows[:origin + 1], bundle)          # the LAST window rows of everything up to the origin
    config = {"input": "json", "provider": provider.name, "family": bundle.combination["family"],
              "output_kind": bundle.combination["output_kind"], "state": bundle.state_ref,
              "as_of": shipped["as_of"], "parameters": {}}
    request = provider.chat_request(f"forecast {bundle.targets[0]} at {bundle.horizons[0]} steps", built, config)
    answer = provider.infer(request, provider.load(bundle.state_ref))
    value = answer["outputs"][bundle.targets[0]]["payload"]["values"][0][0]
    assert value == RECORDED_HOUSEHOLD_VALUE, value


# ---------------------------------------------------------------------------------------------------- refusals by name

def test_missing_columns_is_refused_and_names_them(bundle, raw):
    dropped = [{k: v for k, v in row.items() if k != "Voltage"} for row in raw]
    with pytest.raises(RowAdapterRefusal) as caught:
        window_from_rows(dropped, bundle)
    assert caught.value.code == MISSING_COLUMNS
    assert "Voltage" in str(caught.value)


def test_too_few_rows_is_refused_and_names_n_against_the_window(bundle, raw):
    window = bundle.manifest["window"]
    with pytest.raises(RowAdapterRefusal) as caught:
        window_from_rows(raw[: window - 1], bundle)
    assert caught.value.code == TOO_FEW_ROWS
    assert str(window - 1) in str(caught.value) and str(window) in str(caught.value)


def test_a_regular_clock_is_accepted_and_an_irregular_one_is_refused(bundle, raw):
    step = bundle.manifest["step_seconds"]
    def stamped(seconds):
        return [dict(row, timestamp=f"2009-08-23T{12 + (i * seconds) // 3600:02d}:"
                                   f"{((i * seconds) // 60) % 60:02d}:{(i * seconds) % 60:02d}+00:00")
                for i, row in enumerate(raw)]
    # the same rows on the bundle's own grid are accepted, so the refusal below is about the step and nothing else
    assert window_from_rows(stamped(step), bundle)["columns"] == bundle.manifest["columns"]
    with pytest.raises(RowAdapterRefusal) as caught:
        window_from_rows(stamped(step * 2), bundle)
    assert caught.value.code == IRREGULAR_SAMPLING
    assert str(step) in str(caught.value) and str(step * 2) in str(caught.value)


def test_non_numeric_is_refused_and_names_the_column_and_the_first_bad_value(bundle, raw):
    spoiled = copy.deepcopy(raw)
    spoiled[3]["Voltage"] = "n/a"
    spoiled[7]["Voltage"] = "also bad"
    with pytest.raises(RowAdapterRefusal) as caught:
        window_from_rows(spoiled, bundle)
    assert caught.value.code == NON_NUMERIC
    assert "Voltage" in str(caught.value) and "n/a" in str(caught.value)
    assert "also bad" not in str(caught.value)                      # the FIRST bad value, not a list of them


def test_a_boolean_is_not_a_number(bundle, raw):
    spoiled = copy.deepcopy(raw)
    spoiled[0]["Sub_metering_1"] = True
    with pytest.raises(RowAdapterRefusal) as caught:
        window_from_rows(spoiled, bundle)
    assert caught.value.code == NON_NUMERIC


def test_a_scaler_whose_bytes_no_longer_hash_to_the_declared_digest_is_refused(tmp_path, bundle_path, raw):
    """The digest is re-read from the bundle's files at call time, not trusted from the load.

    A bundle is validated when the provider is constructed; nothing stopped the manifest from changing afterwards, and
    a changed scaler would standardize the caller's rows with statistics the published digest does not describe. The
    engine would still answer -- with a number from the wrong scale."""
    copied = tmp_path / "household-dev"
    shutil.copytree(bundle_path, copied, symlinks=False)
    provider = ForecastProvider(copied)
    bundle = provider._bundles[0]
    manifest = json.loads((copied / "manifest.json").read_text())
    manifest["scaler"]["mean"] = [float(v) + 1.0 for v in manifest["scaler"]["mean"]]   # digest deliberately untouched
    (copied / "manifest.json").write_text(json.dumps(manifest, indent=2))
    with pytest.raises(RowAdapterRefusal) as caught:
        window_from_rows(raw, bundle)
    assert caught.value.code == SCALER_DIGEST_MISMATCH


# ---------------------------------------------------------------------------------------------------- the existing path

def test_the_standardized_window_path_is_unchanged(provider, bundle, shipped):
    """Byte-identical: the object a caller already sent still reaches the engine exactly as it did."""
    config = {"input": "json", "provider": provider.name, "family": bundle.combination["family"],
              "output_kind": bundle.combination["output_kind"], "state": bundle.state_ref,
              "as_of": shipped["as_of"], "parameters": {"request_id": shipped["request_id"]}}
    request = provider.chat_request(f"forecast {bundle.targets[0]} at {bundle.horizons[0]} steps",
                                    shipped["data"], config)
    assert request == shipped


def test_raw_rows_and_the_standardized_window_build_the_same_request(provider, bundle, shipped):
    rows = source_rows()
    origin = bundle.manifest["provenance"]["origin_row_in_dev_slice"]
    config = {"input": "json", "provider": provider.name, "family": bundle.combination["family"],
              "output_kind": bundle.combination["output_kind"], "state": bundle.state_ref,
              "as_of": shipped["as_of"], "parameters": {"request_id": shipped["request_id"]}}
    from_rows = provider.chat_request(f"forecast {bundle.targets[0]} at {bundle.horizons[0]} steps",
                                      rows[:origin + 1], config)
    assert from_rows == shipped


def test_csv_text_is_accepted_and_agrees_with_the_row_list(provider, bundle, shipped):
    rows = source_rows()
    origin = bundle.manifest["provenance"]["origin_row_in_dev_slice"]
    chunk = rows[:origin + 1]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(chunk[0]))
    writer.writeheader()
    writer.writerows(chunk)
    assert rows_from_csv(buffer.getvalue()) == chunk
    config = {"input": "json", "provider": provider.name, "family": bundle.combination["family"],
              "output_kind": bundle.combination["output_kind"], "state": bundle.state_ref,
              "as_of": shipped["as_of"], "parameters": {"request_id": shipped["request_id"]}}
    assert provider.chat_request(f"forecast {bundle.targets[0]} at {bundle.horizons[0]} steps",
                                 buffer.getvalue(), config) == shipped


def test_only_the_last_window_rows_are_used(bundle, raw):
    """A person attaches a file, not a window: everything before the last `window` rows is history, not input."""
    padded = raw_rows_from_window(bundle, [[0.0] * len(bundle.manifest["columns"])] * 5) + raw
    assert window_from_rows(padded, bundle) == window_from_rows(raw, bundle)


def test_the_question_envelope_answers_from_raw_rows(provider, bundle):
    rows = source_rows()
    origin = bundle.manifest["provenance"]["origin_row_in_dev_slice"]
    answers = provider.answer_questions({"state_ref": bundle.state_ref},
                                        {"q": {"type": "point_forecast", "horizon": bundle.horizons[0]}},
                                        rows[:origin + 1], "2026-09-25T00:00:00+00:00")
    assert answers["q"]["type"] == "point_forecast", answers["q"]
    assert answers["q"]["values"] == [RECORDED_HOUSEHOLD_VALUE], answers["q"]
    assert answers["q"]["execution_authorized"] is False


def test_the_question_envelope_refuses_raw_rows_by_name(provider, bundle, raw):
    answers = provider.answer_questions({"state_ref": bundle.state_ref},
                                        {"q": {"type": "point_forecast", "horizon": bundle.horizons[0]}},
                                        raw[:10], "2026-09-25T00:00:00+00:00")
    assert answers["q"]["status"] == "REFUSED"
    assert TOO_FEW_ROWS in answers["q"]["why"], answers["q"]


def test_the_provider_declares_that_both_shapes_are_accepted(provider):
    requirement = provider.data_requirement()
    assert requirement["required"] is True
    shape = requirement["shape"]
    assert "scaler_digest" in shape and "rows" in shape and requirement["why"]
