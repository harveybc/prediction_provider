"""CPU-only adapter around exported, retained native DEV forecasting graphs."""

from __future__ import annotations

import copy
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import subprocess
import threading

import numpy as np


#: the combination the retained household bundle was exported and tested under. A v2 bundle names its own family, so this
#: is the DEFAULT for a bundle that does not declare one -- never a claim about every bundle a directory may hold.
COMBINATION = {"operation": "infer", "family": "regression_forecasting", "output_kind": "point_forecast"}

SCHEMA_V1 = "prediction_provider.forecast_bundle.v1"
SCHEMA_V2 = "prediction_provider.forecast_bundle.v2"

#: v1 predates per-bundle identity, and its manifest BYTES are load-bearing: the retained state reference, `parity.json`
#: and `example_request.json` all quote the digest of exactly those bytes, and the recorded native value replays only
#: against that reference. So a v1 manifest is never given a `state_id` field and never revalidated against a widened
#: contract; it keeps the exact identity and the exact checks it was published with. Everything new is v2.
LEGACY_V1_STATE_ID = "e1-household-r0-s1"
LEGACY_V1_TASK_ID = "e1.household.W60_h60"
LEGACY_V1_COLUMNS = ["Global_reactive_power", "Voltage", "Global_intensity", "Sub_metering_1",
                     "Sub_metering_2", "Sub_metering_3", "Global_active_power"]
LEGACY_V1_TITLE = "DEVELOPMENT: retained household-power model, 60-minute forecast"

#: how a bundle turns the graph's raw output into the number it publishes. `target_scaler_inverse` undoes the train-only
#: standardisation of the target channel (the household regression bundle); `identity` publishes the graph's own output
#: unchanged, which is the only correct readout for a bounded quantity such as a probability -- rescaling one would
#: silently publish a number outside its own unit.
READOUTS = ("target_scaler_inverse", "identity")

#: the only quality this package can honestly publish. Export never scores a model against held-out data, so a bundle
#: arriving with any other value is refused rather than allowed to carry a number this package did not compute.
UNMEASURED = "UNMEASURED"

#: what a bundle is allowed to say about held-out exposure. `DEV_ONLY_NO_TEST_ACCESS` is a RECEIPT: a governed run wrote
#: it and the exporter checked it. predictor's committed example checkpoints have no such receipt, so they say so instead
#: of borrowing the stronger wording -- a bundle that claims a receipt nobody wrote is worse than one that claims none.
#: `DEV_FIT_HOLDOUT_SEALED_BEFORE_SCORING` is the third, and it is the weakest of the three on purpose: it says a fit
#: was made on TRAIN rows only against a holdout whose rows and labels were sealed BEFORE any weight moved, and nothing
#: more. It is not the governed run's receipt, and the quality measured on that holdout lives in the evaluation report
#: that measured it, never in this manifest -- this package still publishes `quality: UNMEASURED`, because it scored
#: nothing itself.
EXPOSURES = ("DEV_ONLY_NO_TEST_ACCESS", "PREDICTOR_EXAMPLE_NO_EXPOSURE_RECEIPT",
             "DEV_FIT_HOLDOUT_SEALED_BEFORE_SCORING")

#: what a v2 bundle may declare its graph emits. `point` is the default and the only thing every bundle before WP07 had:
#: one number per target and horizon. `quantile` says the graph emits one number per target, horizon AND declared
#: quantile, which is what makes an interval readable instead of manufactured.
HEADS = ("point", "quantile")

#: what a v2 bundle must say about where its weights came from. A bundle that cannot say what it was trained on, by whom
#: and when is refused at construction: serving it would put an unattributable model behind a confident answer.
REQUIRED_PROVENANCE = ("trained_on", "trained_by", "trained_at", "quality")

#: refusal codes of the question envelope (`m5phet.questions`), spelled here because the native interpreter that runs
#: this package does not carry `m5phet`. A refusal is a statement about the engine or the request, never about the
#: answer, and it carries no number.
NOT_ESTIMABLE = "NOT_ESTIMABLE"
STATE_REQUIRED = "STATE_REQUIRED"
MALFORMED_QUESTION = "MALFORMED_QUESTION"
PROVIDER_ERROR = "PROVIDER_ERROR"

#: the confidence level asked for has no pair of FITTED quantiles. A 0.95 interval is not obtained by widening a 0.90
#: one, and the two bounds of an interval are two quantiles somebody fitted or they are two numbers somebody invented.
#: So the level is refused by name, with the levels the bundle does hold.
CONFIDENCE_LEVEL_NOT_FITTED = "CONFIDENCE_LEVEL_NOT_FITTED"

#: why an interval or an anomaly risk is refused by every bundle this package serves. The retained graphs are point
#: models: one number per target and horizon, no quantile head, no ensemble, no residual distribution recorded at
#: export. A bound or a probability of crossing a threshold would have to be manufactured from nothing, so both types are
#: DECLARED (the shape is visible and the refusal is typed) and REFUSED with this reason. The day a bundle carries
#: quantiles, that is where an interval gets computed -- not before.
NO_DISTRIBUTION = ("it emits a point estimate and no predictive distribution; an interval would require a quantile or "
                   "ensemble head this bundle does not have")

#: why an anomaly risk stays refused even for a bundle that DOES carry quantiles. A handful of fitted quantiles is not a
#: distribution: the probability of crossing a threshold between two of them would have to come from an interpolation
#: nobody fitted, and outside them from a tail nobody fitted at all.
QUANTILES_ARE_NOT_A_CDF = ("it carries {count} fitted quantiles {quantiles}, which are {count} points of a predictive "
                           "distribution and not the distribution: the probability of crossing a threshold would have "
                           "to be interpolated between them, or extrapolated beyond them, and neither was fitted")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def file_digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def cpu_tensorflow():
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    os.environ.setdefault("TF_NUM_INTRAOP_THREADS", "1")
    os.environ.setdefault("TF_NUM_INTEROP_THREADS", "1")
    import tensorflow as tf
    # An already initialised GPU runtime cannot safely be repurposed by this provider.
    try:
        tf.config.set_visible_devices([], "GPU")
    except RuntimeError as exc:
        if tf.config.get_visible_devices("GPU"):
            raise RuntimeError("forecast provider requires a separate CPU-only process") from exc
    return tf


def _aware_time(value):
    if not isinstance(value, str):
        raise ValueError("as_of must be an aware ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("as_of must be an aware ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("as_of must be an aware ISO timestamp")
    return parsed


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _dedup(names):
    """Order-preserving deduplication. Two bundles may legitimately declare the same alias for the same value; the slot
    must still list it once, or the workbench would be offered the same word twice as if it meant two things."""
    out = []
    for name in names:
        if name not in out:
            out.append(name)
    return out


class _Bundle:
    """One exported native graph plus the manifest that says what it is. Nothing here loads TensorFlow."""

    def __init__(self, path):
        self.path = Path(path).resolve()
        manifest_path = self.path / "manifest.json"
        self.manifest = json.loads(manifest_path.read_text())
        self.manifest_hash = file_digest(manifest_path)
        self.engine = None
        self.lock = threading.RLock()
        self._validate()
        self.digest = digest(self.manifest)
        state_id = LEGACY_V1_STATE_ID if self.schema == SCHEMA_V1 else self.manifest["state_id"]
        self.state_ref = f"{state_id}:{self.digest}"

    # ------------------------------------------------------------------ identity and declaration

    @property
    def schema(self):
        return self.manifest.get("schema")

    @property
    def targets(self):
        return list(self.manifest["targets"])

    @property
    def horizons(self):
        return [int(h) for h in self.manifest["horizons"]]

    @property
    def combination(self):
        if self.schema == SCHEMA_V1:
            return dict(COMBINATION)
        return dict(COMBINATION, family=self.manifest["family"])

    @property
    def readout(self):
        return "target_scaler_inverse" if self.schema == SCHEMA_V1 else self.manifest["readout"]

    @property
    def heads(self):
        """What the graph emits. A manifest that declares nothing emits a point, which is what every bundle before WP07
        was; the field is never inferred from the output width, because a wider graph could be many things."""
        return [str(h) for h in (self.manifest.get("heads") or ["point"])]

    @property
    def quantiles(self):
        """The fitted quantiles, ascending, or an empty list for a point bundle. These are the ONLY levels this bundle
        can bound: a quantile it did not fit does not become available by arithmetic on the ones it did."""
        if "quantile" not in self.heads:
            return []
        return [float(q) for q in self.manifest["quantiles"]]

    @property
    def median_index(self):
        return self.quantiles.index(0.5) if self.quantiles else None

    @property
    def width(self):
        """How many numbers the graph emits per window: one per target, horizon and -- with a quantile head -- quantile."""
        return len(self.targets) * len(self.horizons) * (len(self.quantiles) or 1)

    def fitted_levels(self):
        """`{confidence level: (low quantile, high quantile)}` for the SYMMETRIC pairs this bundle actually fitted.

        Symmetric because that is what a two-sided confidence level means: the pair (q, 1-q) leaves the same mass on
        each side and covers 1-2q. An asymmetric pair covers an interval too, but not one any `confidence_level` names,
        so it is not offered under a number that would suggest it does."""
        levels = {}
        for low in self.quantiles:
            high = round(1.0 - low, 9)
            if low < 0.5 and high in [round(q, 9) for q in self.quantiles]:
                levels[round(high - low, 9)] = (low, high)
        return levels

    @property
    def input_scale(self):
        return "train_standardized" if self.schema == SCHEMA_V1 else self.manifest["input_scale"]

    @property
    def title(self):
        return LEGACY_V1_TITLE if self.schema == SCHEMA_V1 else self.manifest["title"]

    def output_schema(self):
        return {k: copy.deepcopy(self.manifest[k]) for k in ("targets", "horizons", "unit", "scale")}

    def state(self):
        return {"state_ref": self.state_ref, "digest": self.digest,
                "model_sha256": digest(self.manifest["files"]),
                "task_id": self.manifest["task_id"], "exposure": self.manifest["exposure"]}

    def target_aliases(self):
        """Every ordinary word that may reach THIS bundle's target, and no word that may not.

        The base spelling is derived from the column name; the rest is declared by the bundle itself (hard-coded for v1,
        whose manifest cannot gain an `aliases` field without changing its published digest). An alias for a value the
        bundle does not have would be a door into an untrained question."""
        aliases = {t: _dedup([t.replace("_", " "), t.replace("_", " ").lower()]) for t in self.targets}
        if self.schema == SCHEMA_V1:
            if "Global_active_power" in aliases:
                aliases["Global_active_power"] += ["household power", "active power", "power consumption",
                                                   "consumption", "potencia", "consumo"]
            return aliases
        for target, names in (self.manifest.get("aliases") or {}).items():
            aliases[target] = _dedup(aliases.get(target, []) + list(names))
        return aliases

    def horizon_aliases(self):
        """Step counts spoken in ordinary units. `minutes` is only correct because the step IS a minute, so it is emitted
        only for a one-minute grid; a four-hour bundle that inherited it would accept `60 minutes` for 60 four-hour bars."""
        step = self.manifest["step_seconds"]
        out = {}
        for h in self.horizons:
            names = [f"{h} steps"] + ([f"{h} minutes"] if step == 60 else []) + \
                    [f"{h} pasos"] + ([f"{h} minutos"] if step == 60 else [])
            if self.schema == SCHEMA_V1 and h == 60:
                names += ["one hour", "an hour", "next hour", "una hora", "la proxima hora", "próxima hora"]
            if self.schema != SCHEMA_V1:
                names += list((self.manifest.get("horizon_aliases") or {}).get(str(h), ()))
            out[str(h)] = _dedup(names)
        return out

    # ------------------------------------------------------------------ validation

    def _validate(self):
        m = self.manifest
        if m.get("schema") not in (SCHEMA_V1, SCHEMA_V2):
            raise ValueError(f"{self.path.name}: unsupported bundle schema {m.get('schema')!r}")
        if m.get("engine") != "tensorflow_saved_model" or m.get("exposure") not in EXPOSURES:
            raise ValueError(f"{self.path.name}: unsupported native DEV bundle contract")
        self._validate_provenance()
        self._validate_files()
        if m.get("schema") == SCHEMA_V1:
            self._validate_v1()
        else:
            self._validate_v2()
        self._validate_shape_and_scaler()

    def _validate_provenance(self):
        prov = self.manifest.get("provenance")
        if not isinstance(prov, dict) or not prov:
            raise ValueError(f"{self.path.name}: a bundle without provenance is refused, never served")
        if self.schema == SCHEMA_V1:
            # The v1 manifest predates the named provenance fields and cannot gain them without changing its digest, so
            # the rule it can carry is the one above: provenance exists and is not empty.
            return
        missing = [k for k in REQUIRED_PROVENANCE if not _text(prov.get(k))]
        if missing:
            raise ValueError(f"{self.path.name}: provenance is missing {', '.join(missing)}; "
                             f"a model nobody can attribute is not served")
        if prov["quality"] != UNMEASURED:
            raise ValueError(f"{self.path.name}: provenance quality must be {UNMEASURED!r}; this package never scores a "
                             f"model, so it cannot publish a quality claim it did not compute")

    def _validate_v1(self):
        m = self.manifest
        if (m.get("exposure") != "DEV_ONLY_NO_TEST_ACCESS"
                or m.get("targets") != ["Global_active_power"] or m.get("horizons") != [60] or m.get("window") != 60
                or m.get("step_seconds") != 60 or m.get("unit") != "kW" or m.get("scale") != "original"):
            raise ValueError("unsupported native DEV bundle contract")
        if m.get("columns") != LEGACY_V1_COLUMNS:
            raise ValueError("bundle input columns do not match native graph")
        if m.get("task_id") != LEGACY_V1_TASK_ID:
            raise ValueError("bundle task identity is unsupported")

    def _validate_v2(self):
        m = self.manifest
        # `horizon_meaning` is required because a step is not self-explanatory outside a fixed-grid regression: a
        # classifier's head index says nothing about how far ahead its label looks, and a bundle that stayed silent
        # would let a reader assume `step_seconds` answered that question.
        for key in ("state_id", "task_id", "unit", "scale", "family", "title", "input_scale", "horizon_meaning"):
            if not _text(m.get(key)):
                raise ValueError(f"{self.path.name}: a v2 bundle must declare a nonempty {key}")
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,80}", m["state_id"]):
            raise ValueError(f"{self.path.name}: state_id must be a short lowercase identifier")
        if m.get("readout") not in READOUTS:
            raise ValueError(f"{self.path.name}: readout must be one of {READOUTS}")
        self._validate_heads()
        for key in ("aliases", "horizon_aliases"):
            declared = m.get(key) or {}
            if not isinstance(declared, dict):
                raise ValueError(f"{self.path.name}: {key} must be a mapping")
            known = set(m["targets"]) if key == "aliases" else {str(int(h)) for h in m["horizons"]}
            if set(declared) - known:
                raise ValueError(f"{self.path.name}: {key} names a value this bundle does not have")
            if any(not _text(v) for names in declared.values() for v in names):
                raise ValueError(f"{self.path.name}: {key} entries must be nonempty strings")

    def _validate_heads(self):
        """A head this package cannot serve, or a quantile set that is not one, is refused at construction.

        The median is required of a quantile bundle because the bundle still has to publish a POINT forecast, and the
        point of a quantile head is its median -- picking the nearest quantile instead, or averaging two of them, would
        publish a number the graph was never fitted to produce."""
        m = self.manifest
        heads = m.get("heads")
        if heads is None:
            if "quantiles" in m:
                raise ValueError(f"{self.path.name}: quantiles are declared but no quantile head is; a bundle says what "
                                 f"its graph emits")
            return
        if (not isinstance(heads, list) or not heads or len(set(heads)) != len(heads)
                or any(h not in HEADS for h in heads)):
            raise ValueError(f"{self.path.name}: heads must be a list of distinct names out of {list(HEADS)}")
        if "quantile" not in heads:
            if "quantiles" in m:
                raise ValueError(f"{self.path.name}: quantiles are declared without a quantile head")
            return
        quantiles = m.get("quantiles")
        if (not isinstance(quantiles, list) or len(quantiles) < 2
                or any(type(q) not in (int, float) or not math.isfinite(q) or not 0 < q < 1 for q in quantiles)):
            raise ValueError(f"{self.path.name}: a quantile head declares at least two quantiles, each strictly "
                             f"inside (0, 1)")
        if any(b <= a for a, b in zip(quantiles, quantiles[1:])):
            raise ValueError(f"{self.path.name}: quantiles must be strictly ascending; a set given out of order would "
                             f"pair the wrong columns into an interval")
        if 0.5 not in quantiles:
            raise ValueError(f"{self.path.name}: a quantile head must fit the median, which is the point forecast this "
                             f"bundle publishes; without it there is no point this graph was fitted to produce")

    def _validate_shape_and_scaler(self):
        m = self.manifest
        cols, targets, horizons = m.get("columns"), m.get("targets"), m.get("horizons")
        if (not isinstance(cols, list) or not cols or len(set(cols)) != len(cols)
                or any(not _text(c) for c in cols)):
            raise ValueError(f"{self.path.name}: columns must be distinct nonempty names")
        if not isinstance(targets, list) or len(targets) != 1 or not _text(targets[0]):
            # A multi-target payload layout has never been exported or tested here; refusing beats guessing which row of
            # `values` belongs to which output id.
            raise ValueError(f"{self.path.name}: exactly one target is supported")
        if (not isinstance(horizons, list) or not horizons
                or any(type(h) is not int or h <= 0 for h in horizons) or len(set(horizons)) != len(horizons)):
            raise ValueError(f"{self.path.name}: horizons must be distinct positive integer steps")
        if type(m.get("window")) is not int or m["window"] <= 0:
            raise ValueError(f"{self.path.name}: window must be a positive number of history rows")
        if type(m.get("step_seconds")) is not int or m["step_seconds"] <= 0:
            raise ValueError(f"{self.path.name}: step_seconds must be a positive number of seconds")
        if not _text(m.get("unit")) or not _text(m.get("scale")) or not _text(self.input_scale):
            raise ValueError(f"{self.path.name}: unit, scale and input_scale are required")
        scaler = m.get("scaler")
        if not isinstance(scaler, dict) or not scaler or not _text(scaler.get("fitted_on")):
            raise ValueError(f"{self.path.name}: a bundle must say what its input scaler was fitted on")
        if m.get("scaler_digest") != digest(scaler):
            raise ValueError(f"{self.path.name}: scaler hash mismatch")
        if self.schema == SCHEMA_V1 and scaler.get("fitted_on") != "train windows only":
            raise ValueError("invalid train-only scaler")
        if self.readout == "target_scaler_inverse":
            # This readout multiplies by the target channel's own standard deviation, so the arrays must exist, be
            # finite, be per-column and have a positive spread. Without that check a zero sd would publish the mean.
            for key in ("mean", "sd"):
                values = scaler.get(key)
                if (not isinstance(values, list) or len(values) != len(cols)
                        or any(type(v) not in (int, float) or not math.isfinite(v) for v in values)):
                    raise ValueError("invalid train-only scaler")
            if any(s <= 0 for s in scaler["sd"]):
                raise ValueError("invalid train-only scaler")
            if targets[0] not in cols:
                raise ValueError(f"{self.path.name}: the target channel is not among the input columns, so its "
                                 f"standardisation cannot be undone")

    def _validate_files(self):
        files = self.manifest.get("files")
        if not isinstance(files, dict) or not files or "saved_model/saved_model.pb" not in files:
            raise ValueError("missing native graph file hashes")
        for name, sha in files.items():
            path = Path(name)
            if (not name.startswith("saved_model/") or path.is_absolute() or ".." in path.parts
                    or not re.fullmatch(r"[0-9a-f]{64}", str(sha))):
                raise ValueError("invalid artifact path or hash")

    def verify(self):
        if file_digest(self.path / "manifest.json") != self.manifest_hash:
            raise ValueError("manifest hash changed; instantiate a new provider for a new state")
        actual = {p.relative_to(self.path).as_posix()
                  for p in (self.path / "saved_model").rglob("*") if p.is_file()}
        if actual != set(self.manifest["files"]):
            raise ValueError("native artifact file set/hash mismatch")
        for name, sha in self.manifest["files"].items():
            path = self.path / name
            if not path.resolve().is_relative_to(self.path) or path.is_symlink():
                raise ValueError("artifact path escapes the bundle")
            if file_digest(path) != sha:
                raise ValueError(f"native artifact hash mismatch: {name}")


#: how a refusal of the RAW-ROW adapter is named. These are not envelope refusal codes: they are statements about the
#: rows a person attached, and each one says the single thing that is wrong with them. A caller used to have to
#: standardize its own window with the bundle's statistics -- which meant a person with a CSV could not use the engine at
#: all, and a person who standardized it with the WRONG statistics got a confident number from the wrong scale with no
#: way to tell. The adapter below removes both, and every way it can fail is named here rather than described in prose.
MISSING_COLUMNS = "MISSING_COLUMNS"
TOO_FEW_ROWS = "TOO_FEW_ROWS"
IRREGULAR_SAMPLING = "IRREGULAR_SAMPLING"
NON_NUMERIC = "NON_NUMERIC"
MALFORMED_ROWS = "MALFORMED_ROWS"
#: the bundle's scaler bytes no longer hash to the digest the bundle declares. Checked when the rows are adapted, not
#: only when the provider was constructed: a manifest can change on disk afterwards, and standardising with statistics
#: the published digest does not describe would still produce an answer -- in the wrong scale, with nothing to show it.
SCALER_DIGEST_MISMATCH = "SCALER_DIGEST_MISMATCH"
#: the bundle declares a scaler but not the per-column statistics needed to standardise raw rows. Such a bundle can
#: still serve an already-standardized window; it simply cannot be handed a CSV, and says so instead of guessing.
SCALER_NOT_EXPORTED = "SCALER_NOT_EXPORTED"

#: the exact key set of an already-standardized history window, as `_check_request` has always required it.
WINDOW_KEYS = {"columns", "values", "scale", "scaler_digest"}

#: a column that is not one of the fitted inputs but whose name says it carries the clock. Only used to CHECK the
#: sampling step; it is never an input and never reaches the graph.
TIMESTAMP_HINTS = ("time", "date", "stamp", "fecha", "hora")

#: the spellings of an instant this adapter can read. A timestamp it cannot parse is not treated as irregular -- an
#: unreadable clock is not evidence of a broken one -- so the step check is simply not made, and the rows are adapted
#: on the caller's word that they are consecutive.
TIMESTAMP_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S",
                     "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%m/%d/%Y %H:%M:%S",
                     "%d-%m-%Y %H:%M:%S", "%d.%m.%Y %H:%M:%S")


class RowAdapterRefusal(ValueError):
    """A refusal of the raw rows, by name. A `ValueError`, so every caller that already treats a bad window as a
    `ValueError` keeps behaving exactly as it did; `code` is there for the ones that want the name."""

    def __init__(self, code, why):
        super().__init__(f"{code}: {why}")
        self.code = code
        self.why = why


def rows_from_csv(text):
    """CSV text to a list of row objects, on the same rules the workbench's own reader uses."""
    if not isinstance(text, str) or not text.strip():
        raise RowAdapterRefusal(MALFORMED_ROWS, "the attached CSV is empty")
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    fields = reader.fieldnames
    if not fields or len(fields) != len(set(fields)) or any(not f.strip() for f in fields):
        raise RowAdapterRefusal(MALFORMED_ROWS, "a CSV needs unique, nonempty column names")
    rows = list(reader)
    if not rows:
        raise RowAdapterRefusal(MALFORMED_ROWS, "the attached CSV has a header and no rows")
    if any(None in row or None in row.values() for row in rows):
        raise RowAdapterRefusal(MALFORMED_ROWS, "a CSV row is wider or narrower than its header")
    return rows


def _as_bundle(bundle):
    if isinstance(bundle, _Bundle):
        return bundle
    if isinstance(bundle, (str, Path)):
        return _Bundle(bundle)
    raise ValueError("window_from_rows needs an exported bundle or the path of one")


def _scaler_statistics(bundle):
    """The bundle's OWN per-column mean and standard deviation, read back out of its files and digest-checked.

    Two exported shapes exist and both are honoured: the v1 household manifest carries `mean`/`sd` as lists aligned with
    `columns`; a v2 manifest exported from predictor carries `columns: {name: {mean, std}}`. Nothing else is accepted --
    a scaler this package cannot read is refused, never approximated."""
    path = bundle.path / "manifest.json"
    try:
        manifest = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise RowAdapterRefusal(SCALER_DIGEST_MISMATCH,
                                f"the bundle's manifest could not be read back from disk: {exc}") from exc
    scaler, declared = manifest.get("scaler"), manifest.get("scaler_digest")
    if not isinstance(scaler, dict) or declared != bundle.manifest["scaler_digest"]:
        raise RowAdapterRefusal(SCALER_DIGEST_MISMATCH,
                                f"{bundle.path.name} no longer declares the scaler digest this provider loaded "
                                f"({bundle.manifest['scaler_digest']}); instantiate a new provider for a new state")
    try:
        actual = digest(scaler)
    except (TypeError, ValueError) as exc:
        raise RowAdapterRefusal(SCALER_DIGEST_MISMATCH, f"the scaler cannot be hashed: {exc}") from exc
    if actual != declared:
        raise RowAdapterRefusal(SCALER_DIGEST_MISMATCH,
                                f"the scaler in {bundle.path.name} hashes to {actual}, not to the declared {declared}; "
                                f"rows will not be standardised with statistics the bundle does not vouch for")
    columns = list(bundle.manifest["columns"])
    if isinstance(scaler.get("mean"), list) and isinstance(scaler.get("sd"), list):
        mean, sd = list(scaler["mean"]), list(scaler["sd"])
    elif isinstance(scaler.get("columns"), dict):
        per = scaler["columns"]
        absent = [c for c in columns if not isinstance(per.get(c), dict)]
        if absent:
            raise RowAdapterRefusal(SCALER_NOT_EXPORTED,
                                    f"the bundle's scaler has no statistics for {', '.join(absent)}, so raw rows "
                                    f"cannot be standardised; attach an already-standardized window instead")
        mean = [per[c].get("mean") for c in columns]
        sd = [per[c].get("std", per[c].get("sd")) for c in columns]
    else:
        raise RowAdapterRefusal(SCALER_NOT_EXPORTED,
                                f"{bundle.path.name} declares a scaler digest but not the per-column statistics raw "
                                f"rows would be standardised with; attach an already-standardized window instead")
    if len(mean) != len(columns) or len(sd) != len(columns):
        raise RowAdapterRefusal(SCALER_NOT_EXPORTED,
                                f"the bundle's scaler describes {len(mean)} channels and the graph takes "
                                f"{len(columns)}; raw rows cannot be standardised against it")
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in list(mean) + list(sd)) or any(s <= 0 for s in sd):
        raise RowAdapterRefusal(SCALER_NOT_EXPORTED,
                                "the bundle's scaler statistics are not finite per-column numbers with a positive "
                                "spread; raw rows cannot be standardised against it")
    return np.asarray(mean, dtype=np.float64), np.asarray(sd, dtype=np.float64), declared


def _instant(value):
    """Epoch seconds for one timestamp cell, or None when this adapter cannot read it."""
    if type(value) in (int, float) and math.isfinite(value):
        return float(value)
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        parsed = None
        for shape in TIMESTAMP_FORMATS:
            try:
                parsed = datetime.strptime(text, shape)
                break
            except ValueError:
                continue
    if parsed is None:
        try:
            return float(text)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _check_sampling(rows, bundle):
    """If the rows carry a clock, it must be the bundle's own grid. A model trained on one-minute bars answers a
    one-minute question; handed hourly rows it would answer confidently about a window it never saw."""
    fitted = set(bundle.manifest["columns"])
    named = next((key for key in rows[0] if key not in fitted
                  and any(hint in str(key).lower() for hint in TIMESTAMP_HINTS)), None)
    if named is None:
        return
    instants = [_instant(row.get(named)) for row in rows]
    if any(t is None for t in instants):
        return
    step = int(bundle.manifest["step_seconds"])
    for i in range(1, len(instants)):
        observed = instants[i] - instants[i - 1]
        if observed != step:
            raise RowAdapterRefusal(IRREGULAR_SAMPLING,
                                    f"column {named!r} steps by {observed:g} s between rows {i - 1} and {i} of the "
                                    f"window, and this bundle is fitted on a grid of {step} s")


def _number(value, column, row_index):
    if type(value) in (int, float) and math.isfinite(value):
        return float(value)
    if isinstance(value, str):
        try:
            parsed = float(value.strip())
        except ValueError:
            parsed = None
        if parsed is not None and math.isfinite(parsed):
            return parsed
    raise RowAdapterRefusal(NON_NUMERIC, f"column {column!r} carries {value!r} at row {row_index} of the window; "
                                         f"every fitted input must be a finite number")


def window_from_rows(rows, bundle):
    """Raw rows in, the engine's window out: exactly the object `_check_request` already accepts.

    `rows` is CSV text or a list of row objects in chronological order, in ORIGINAL units, with whatever extra columns
    the file happens to have. The fitted inputs are selected BY NAME (a file's column order is its own business), the
    last `window` of them are taken, and they are standardised with the bundle's own digest-checked statistics in
    float64 before being narrowed to the float32 the graph consumes -- which is the arithmetic `export.py` used, so the
    window this rebuilds from the source rows is the window the bundle ships.

    Every way this can fail is refused by name and none of them is answered."""
    bundle = _as_bundle(bundle)
    if isinstance(rows, str):
        rows = rows_from_csv(rows)
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list) or not rows or any(not isinstance(row, dict) for row in rows):
        raise RowAdapterRefusal(MALFORMED_ROWS, "raw history must be CSV text or a nonempty list of row objects")
    mean, sd, scaler_digest = _scaler_statistics(bundle)
    columns = list(bundle.manifest["columns"])
    missing = [c for c in columns if any(c not in row for row in rows)]
    if missing:
        raise RowAdapterRefusal(MISSING_COLUMNS,
                                f"the rows do not carry {', '.join(missing)}; this bundle is fitted on "
                                f"{', '.join(columns)}")
    window = int(bundle.manifest["window"])
    if len(rows) < window:
        raise RowAdapterRefusal(TOO_FEW_ROWS,
                                f"{len(rows)} rows were given and this bundle needs {window}: a window of {window} "
                                f"consecutive rows ending at the origin")
    tail = rows[-window:]
    _check_sampling(tail, bundle)
    raw = np.asarray([[_number(row[name], name, i) for name in columns] for i, row in enumerate(tail)],
                     dtype=np.float64)
    values = ((raw - mean) / sd).astype(np.float32).tolist()
    return {"columns": columns, "values": values, "scale": bundle.input_scale, "scaler_digest": scaler_digest}


def _standardized_window(value):
    return isinstance(value, dict) and set(value) == WINDOW_KEYS


def _refusal(kind, why, question_type):
    """The envelope's refusal shape, byte for byte what `m5phet.questions.refusal` builds."""
    return {"status": "REFUSED", "refusal": kind, "why": why, "type": question_type}


class ForecastProvider:
    name = "predictor_forecast"
    #: the one area of the question envelope this provider takes part in
    area = "forecasting"

    def __init__(self, bundle=None):
        configured = bundle or os.environ.get("M5PHET_FORECAST_BUNDLE")
        self._root = Path(configured).resolve() if configured else None
        self._worker_python = os.environ.get("M5PHET_FORECAST_PYTHON")
        if self._worker_python and (not Path(self._worker_python).is_absolute()
                                    or not Path(self._worker_python).is_file()):
            raise ValueError("M5PHET_FORECAST_PYTHON must be an operator-configured absolute Python executable")
        self._bundles = []
        if self._root is not None:
            for path in self._discover(self._root):
                loaded = _Bundle(path)
                if any(b.state_ref == loaded.state_ref for b in self._bundles):
                    raise ValueError(f"two configured bundles publish the same fitted state {loaded.state_ref}; "
                                     f"a request could not name which one it meant")
                self._bundles.append(loaded)

    @staticmethod
    def _discover(root):
        """One bundle, or a directory of them. A directory is the operator's deliberate list, so a member that refuses to
        validate refuses the whole provider: quietly serving the rest would hide the one that was meant to be there."""
        if (root / "manifest.json").is_file():
            return [root]
        children = sorted(p for p in root.iterdir() if p.is_dir() and (p / "manifest.json").is_file())
        if not children:
            raise ValueError(f"{root} is neither an exported bundle nor a directory containing exported bundles")
        return children

    @property
    def _engine(self):
        """`is None` still means 'no native graph has been built in this process'. Callers and tests assert exactly that
        before a load, so it must stay true when several bundles are configured and none of them has been loaded."""
        for bundle in self._bundles:
            if bundle.engine is not None:
                return bundle.engine
        return None

    def _bundle(self, state_ref):
        for bundle in self._bundles:
            if bundle.state_ref == state_ref:
                return bundle
        raise ValueError("unknown fitted state; configure an exported trained DEV bundle")

    def known_states(self):
        return [b.state_ref for b in self._bundles]

    def capabilities(self):
        supported, families = [], []
        for bundle in self._bundles:
            entry = bundle.combination
            if entry not in supported:
                supported.append(entry)
            if entry["family"] not in families:
                families.append(entry["family"])
        # Each bundle says which standardisation its history rows must already be in. One value stays a plain string, as
        # it always was; several are listed, because a caller told a single scale would standardise for the wrong bundle.
        scales = _dedup([b.input_scale for b in self._bundles]) or ["train_standardized"]
        # a quantile bundle answers one more kind of question and carries one more kind of uncertainty; both are listed
        # only when a configured bundle actually has the head, never as a shape the area might one day fill
        quantile = any("quantile" in b.heads for b in self._bundles)
        return {"operations": ["infer"], "families": families or [COMBINATION["family"]],
                "output_kinds": ["point_forecast"] + (["interval"] if quantile else []),
                "uncertainty_methods": (["none"] + ["fitted_quantiles"]) if quantile else ["none"],
                "supported": supported or [dict(COMBINATION)], "known_states": self.known_states(),
                "backend": "tensorflow_saved_model_cpu_subprocess" if self._worker_python else "tensorflow_saved_model_cpu",
                "input_schema": {"kind": "one_history_window",
                                 "scale": scales[0] if len(scales) == 1 else scales},
                # With several bundles there is no single output schema; each fitted state declares its own, and a caller
                # that reads only the singular field must see nothing rather than one bundle's contract standing in for all.
                "output_schema": self._bundles[0].output_schema() if len(self._bundles) == 1 else None,
                "bundles": [dict(bundle.output_schema(), state_ref=bundle.state_ref,
                                 task_id=bundle.manifest["task_id"], family=bundle.combination["family"],
                                 window=bundle.manifest["window"], step_seconds=bundle.manifest["step_seconds"])
                            for bundle in self._bundles]}

    def load(self, state_ref):
        bundle = self._bundle(state_ref)
        with bundle.lock:
            bundle.verify()
            if bundle.engine is None:
                if self._worker_python:
                    loaded = self._native_process(bundle, "load", state_ref=state_ref)
                    if loaded != bundle.state():
                        raise ValueError("native process loaded a different state")
                    bundle.engine = "operator_native_process"
                    return loaded
                tf = cpu_tensorflow()
                with tf.device("/CPU:0"):
                    loaded = tf.saved_model.load(str(bundle.path / "saved_model"))
                engine = loaded.signatures["serving_default"]
                args, kwargs = engine.structured_input_signature
                outputs = engine.structured_outputs
                shape = (1, bundle.manifest["window"], len(bundle.manifest["columns"]))
                width = bundle.width
                if (args or set(kwargs) != {"x"} or kwargs["x"].shape != shape
                        or kwargs["x"].dtype != tf.float32 or set(outputs) != {"forecast"}
                        or outputs["forecast"].shape != (1, width) or outputs["forecast"].dtype != tf.float32):
                    raise ValueError("native graph signature does not match the declared forecast contract")
                bundle.engine = engine
            return bundle.state()

    def _native_process(self, bundle, command, *, state_ref=None, request=None):
        # Only the operator supplies this executable and bundle path, never chat config. The worker is always handed ONE
        # resolved bundle, so the isolated process never has to repeat the resolution the host already made.
        argv = [self._worker_python, "-m", "prediction_provider_forecast.cli", command,
                "--bundle", str(bundle.path)]
        if command == "load":
            argv += ["--state", state_ref]
        else:
            argv += ["--request", "-"]
        env = dict(os.environ, CUDA_VISIBLE_DEVICES="", OMP_NUM_THREADS="1")
        env.pop("M5PHET_FORECAST_PYTHON", None)
        # Avoid importing the web environment's packages into the isolated native interpreter.
        env.pop("PYTHONPATH", None)
        try:
            done = subprocess.run(argv, input=json.dumps(request, allow_nan=False) if request else None,
                                  text=True, capture_output=True, check=False, timeout=60, env=env)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("native CPU forecast process exceeded 60 seconds") from exc
        if done.returncode:
            raise RuntimeError(f"native CPU forecast process refused: {done.stderr[-2000:]}")
        return json.loads(done.stdout)

    def _check_request(self, request):
        return self._checked(request)[1]

    def _checked(self, request):
        if not self._bundles:
            raise ValueError("no trained DEV bundle configured")
        if not isinstance(request, dict) or request.get("schema_version") != "m5phet.task.draft2":
            raise ValueError("expected m5phet.task.draft2 request")
        bundle = self._bundle(request.get("fitted_state_ref"))
        expected = dict(bundle.combination, provider_ref=self.name, task_id=bundle.manifest["task_id"],
                        fitted_state_ref=bundle.state_ref)
        if any(request.get(k) != v for k, v in expected.items()):
            raise ValueError("unsupported request task, provider, operation or fitted state")
        if not isinstance(request.get("request_id"), str) or not request["request_id"].strip():
            raise ValueError("request_id must be nonempty")
        _aware_time(request.get("as_of"))
        schema = request.get("output_schema")
        if (schema != bundle.output_schema() or not isinstance(schema.get("horizons"), list)
                or any(type(h) is not int for h in schema["horizons"])):
            raise ValueError("output schema must match trained targets, horizons, unit and scale")
        data = request.get("data")
        if not isinstance(data, dict) or set(data) != {"columns", "values", "scale", "scaler_digest"}:
            raise ValueError("data must contain exactly columns, values, scale and scaler_digest")
        if (data["columns"] != bundle.manifest["columns"] or data["scale"] != bundle.input_scale
                or data["scaler_digest"] != bundle.manifest["scaler_digest"]):
            raise ValueError("input columns, scale or scaler_digest mismatch")
        values = data["values"]
        window = bundle.manifest["window"]
        if not isinstance(values, list) or len(values) != window:
            raise ValueError(f"expected exactly {window} chronological history rows, ending at the origin")
        for row in values:
            if not isinstance(row, list) or len(row) != len(bundle.manifest["columns"]):
                raise ValueError("input feature count mismatch")
            if any(type(v) not in (int, float) or abs(v) > float(np.finfo(np.float32).max) or not math.isfinite(v) for v in row):
                raise ValueError("history values must be finite float32-representable numbers, not bools")
        if request.get("population") != {"input_sha256": digest(data)}:
            raise ValueError("population must bind this exact input window")
        return bundle, np.asarray(values, dtype=np.float32)[None, :, :]

    def infer(self, request, state):
        bundle, x = self._checked(request)
        if state != bundle.state():
            raise ValueError("loaded state identity mismatch")
        with bundle.lock:
            bundle.verify()
            if bundle.engine is None:
                raise ValueError("load the fitted state before infer")
            if self._worker_python:
                return self._native_process(bundle, "infer", request=request)
            tf = cpu_tensorflow()
            with tf.device("/CPU:0"):
                result = bundle.engine(x=tf.convert_to_tensor(x))["forecast"].numpy()
        width = bundle.width
        if result.shape != (1, width) or not np.isfinite(result).all():
            raise ValueError("native engine returned invalid forecast shape or non-finite values")
        # Preserve native float32 arithmetic, including its original-scale readout.
        if bundle.readout == "target_scaler_inverse":
            j = bundle.manifest["columns"].index(bundle.targets[0])
            scaler = bundle.manifest["scaler"]
            values = result * float(scaler["sd"][j]) + float(scaler["mean"][j])
        else:
            values = result
        if not np.isfinite(values).all():
            raise ValueError("native output scaling produced a non-finite forecast")
        target = bundle.targets[0]
        quantiles = bundle.quantiles
        if quantiles:
            # the graph emits the quantiles of one horizon together, horizon-major: [(h1,q1)...(h1,qK),(h2,q1)...]
            grid = values.reshape(len(bundle.horizons), len(quantiles))
            point = grid[:, bundle.median_index]
            if (np.diff(grid, axis=1) < 0).any():
                # the head is built so this cannot happen; if it ever does, the pair is not an interval and no number
                # is published rather than one whose bounds are the wrong way round
                raise ValueError("native engine returned crossing quantiles; the bounds of an interval cannot cross")
            payload = dict(bundle.output_schema(), values=point.reshape(1, len(bundle.horizons)).tolist(),
                           quantiles=list(quantiles), quantile_values=grid.reshape(
                               1, len(bundle.horizons), len(quantiles)).tolist())
            uncertainty = "fitted_quantiles"
        else:
            payload = dict(bundle.output_schema(), values=values.reshape(1, len(bundle.horizons)).tolist())
            uncertainty = "none"
        return {"outputs": {target: {"status": "OK", "uncertainty": uncertainty, "payload": payload}},
                "population": copy.deepcopy(request["population"])}

    def chat_combinations(self):
        """The pairs that are actually fitted, one per bundle target and horizon.

        The slots above are a UNION, and a union lets a router pair a target with a horizon that belongs to the other
        bundle -- `Global_active_power` at 1, say, when 1 is the direction model's horizon. Each value is admissible and the
        pair is nobody's. This is the list a router must match a question against before anyone presses run."""
        return [{"target": target, "horizon": int(horizon)}
                for bundle in self._bundles for target in bundle.targets for horizon in bundle.horizons]

    def chat_slots(self):
        """What these engines need, and the only values they have. The workbench resolves ordinary phrasing against exactly
        this, so a paraphrase can reach a model and an unsupported target or horizon cannot.

        With several bundles configured the declaration is their UNION: every target and horizon that some bundle can
        answer. Which bundle answers is settled afterwards, in `chat_request`, where a value two bundles share is refused
        rather than assigned to whichever was enumerated first."""
        if not self._bundles:
            return []
        targets, aliases, horizons, horizon_aliases = [], {}, [], {}
        for bundle in self._bundles:
            declared = bundle.target_aliases()
            for target in bundle.targets:
                if target not in targets:
                    targets.append(target)
                aliases[target] = _dedup(aliases.get(target, []) + declared.get(target, []))
            spoken = bundle.horizon_aliases()
            for horizon in bundle.horizons:
                if horizon not in horizons:
                    horizons.append(horizon)
                horizon_aliases[str(horizon)] = _dedup(horizon_aliases.get(str(horizon), []) + spoken[str(horizon)])
        # What these bundles have and do NOT have. Naming a column one of them holds as input but no bundle forecasts is
        # refused before any interpreter is consulted; otherwise a model asked to choose among the allowed values chooses
        # one that exists and answers confidently about a different series.
        untrained = []
        for bundle in self._bundles:
            for column in bundle.manifest.get("columns") or []:
                if column not in targets and column not in untrained:
                    untrained.append(column)
        return [{"name": "target", "allowed": targets, "aliases": aliases,
                 "known_unsupported": untrained},
                {"name": "horizon", "allowed": horizons, "type": "integer",
                 "aliases": horizon_aliases,
                 "number_hints": ["step", "horizon", "minute", "hour", "ahead", "paso", "minuto", "hora", "adelante"]}]

    def _available(self):
        return "; ".join(f"{b.targets[0]} at {b.horizons} ({b.state_ref})" for b in self._bundles)

    def _resolve(self, target, horizon):
        """Exactly one bundle, or a refusal that names the alternatives.

        Two configured bundles may honestly serve the same target at the same horizon -- two architectures, two regimes,
        two training windows. Answering with whichever one was enumerated first would put a model nobody chose behind a
        confident number, and the caller would have no way to tell which. So the refusal names both and asks for the
        fitted state instead."""
        matches = [b for b in self._bundles if target in b.targets and horizon in b.horizons]
        if len(matches) > 1:
            named = " and ".join(b.state_ref for b in matches)
            raise ValueError(f"{target!r} at horizon {horizon!r} is served by more than one configured bundle "
                             f"({named}); name the fitted state instead of letting this pick one")
        if not matches:
            raise ValueError(f"no configured bundle forecasts {target!r} at horizon {horizon!r}; available: "
                             f"{self._available()}")
        return matches[0]

    @staticmethod
    def _window(data, bundle):
        """The standardized window this request will carry, from whatever the caller attached.

        An already-standardized window (or a list holding exactly one, which is how the workbench attaches a JSON file)
        is returned UNCHANGED -- not rebuilt, not re-hashed -- so a caller that was working keeps working byte for byte.
        Raw rows go through `window_from_rows`. Anything else is handed on untouched, to be refused by the request check
        that has always refused it, with the message it has always used."""
        if _standardized_window(data):
            return data
        if isinstance(data, list) and len(data) == 1 and _standardized_window(data[0]):
            return data[0]
        if isinstance(data, str) or (isinstance(data, list) and data and all(isinstance(r, dict) for r in data)):
            return window_from_rows(data, bundle)
        return data

    def window_from_rows(self, rows, state_ref=None):
        """The standardized window one configured bundle would consume, from raw rows. No graph is loaded.

        With several bundles configured the caller names which one: the fitted columns, the window length and the
        statistics are that bundle's, and standardising rows against the wrong bundle would produce a window that looks
        perfectly valid and means nothing."""
        if not self._bundles:
            raise ValueError("no trained DEV bundle configured")
        if state_ref is None:
            if len(self._bundles) != 1:
                raise ValueError("name the fitted state: " + ", ".join(self.known_states()))
            bundle = self._bundles[0]
        else:
            bundle = self._bundle(state_ref)
        return window_from_rows(rows, bundle)

    def chat_request(self, prompt, data, config, parameters=None):
        if not self._bundles:
            raise ValueError("no trained DEV bundle configured")
        if not isinstance(prompt, str) or len(prompt) > 512:
            raise ValueError("prompt must be a string of at most 512 characters")
        if parameters:
            # Resolved against the configured bundles' own declared values, so neither a target nor a horizon can arrive
            # from outside what was actually trained. The canonical phrasing below remains accepted as it always was.
            target = parameters.get("target")
            try:
                horizon = int(parameters.get("horizon"))
            except (TypeError, ValueError):
                horizon = None
        else:
            match = re.fullmatch(r"forecast ([A-Za-z][A-Za-z0-9_]*) at ([1-9][0-9]{0,4}) steps", prompt)
            if not match:
                raise ValueError("expected one of: "
                                 + "; ".join(f"forecast {b.targets[0]} at {h} steps"
                                             for b in self._bundles for h in b.horizons))
            target, horizon = match[1], int(match[2])
        bundle = self._resolve(target, horizon)
        return self._request_for(bundle, prompt, data, config, target=target, horizon=horizon)

    def _request_for(self, bundle, prompt, data, config, *, target=None, horizon=None):
        """Build and check the request for a bundle ALREADY resolved, with every check `chat_request` makes after it.

        The envelope path resolves its bundle in `_resolve_question` -- which honours a `state_ref` the caller named and
        refuses a target two bundles share with STATE_REQUIRED -- and then has to build a request for exactly that
        bundle. Routing it back through `chat_request` would resolve it a SECOND time, by target and horizon alone, and
        the two rules disagree the moment a target has two bundles: the caller names the fitted state, `chat_request`
        refuses the ambiguity anyway, and the refusal's own instruction ("name the fitted state") cannot be followed.
        So the resolution happens once, here it is only used. `chat_request` keeps its own rule unchanged for the
        callers that arrive with words instead of a state."""
        required = {"provider", "family", "output_kind", "state", "as_of", "parameters"}
        # Shared workbench fields are not forecasting model parameters.
        transport = {"input", "presentation", "context", "asset", "language", "max_age_seconds", "options"}
        if (not isinstance(config, dict) or not required <= set(config)
                or set(config) - required - transport):
            raise ValueError("config requires provider, family, output_kind, state, as_of, parameters; input is optional")
        if (config["provider"] != self.name or config["family"] != bundle.combination["family"]
                or config["output_kind"] != bundle.combination["output_kind"] or config.get("input", "json") != "json"):
            raise ValueError("chat config must select this point-forecast provider with JSON input")
        if config["state"] != bundle.state_ref:
            # The words chose one fitted state and the config named another. Neither silently wins: a request answered by
            # a model the caller did not name is exactly what the ambiguity rule above exists to prevent.
            raise ValueError(f"the request names fitted state {config['state']!r}, but {target!r} at horizon "
                             f"{horizon!r} belongs to {bundle.state_ref!r}")
        parameters = config["parameters"]
        if not isinstance(parameters, dict) or set(parameters) - {"request_id"}:
            raise ValueError("parameters only supports optional request_id; no implicit model settings")
        # WP16: raw rows (CSV text, or the row objects the workbench's CSV reader produces) are standardised HERE, with
        # the bundle this request already resolved. An already-standardized window is passed through untouched, so the
        # path that existed before this adapter is byte for byte the path it was.
        data = self._window(data, bundle)
        request_id = parameters.get("request_id", "forecast:" + digest({"prompt": prompt, "data": data, "config": config}))
        request = {"schema_version": "m5phet.task.draft2", "request_id": request_id,
                   "as_of": config["as_of"], "fitted_state_ref": config["state"],
                   **bundle.combination, "task_id": bundle.manifest["task_id"], "provider_ref": self.name,
                   "output_schema": bundle.output_schema(), "data": copy.deepcopy(data),
                   "population": {"input_sha256": digest(data)},
                   "execution_constraints": {"partial_results": False}}
        self._check_request(request)
        return request

    def chat_examples(self):
        """Actual DEV history from explicit export; no model load, training or synthetic fallback. One entry per bundle.

        A bundle that shipped no `example_request.json` contributes no example. The examples are history that export
        WROTE after its parity passed; this provider has no data of its own and will not manufacture a window to fill
        the gap, because a made-up example would look exactly like a real one in the workbench.
        """
        examples = []
        for bundle in self._bundles:
            source = bundle.path / "example_request.json"
            if not source.is_file():
                continue
            request = json.loads(source.read_text())
            self._check_request(request)
            # `output_kind` is the runtime's contract word (the shape of the payload); `unit` is what the number IS.
            # The direction bundle answers a point_forecast whose unit is a probability, and the example must say
            # both apart, or "forecast" reads as a level when it is a chance (Retsu, 2026-09-24, §8.5).
            unit, family = bundle.manifest["unit"], bundle.combination["family"]
            prompt = (f"what is the {bundle.targets[0]} probability at horizon {bundle.horizons[0]}?"
                      if unit == "probability" else f"forecast {bundle.targets[0]} at {bundle.horizons[0]} steps")
            examples.append({"title": bundle.title,
                             "prompt": prompt,
                             "reading": (f"{family}: the answer is a {unit}, not a level; output_kind "
                                         f"{bundle.combination['output_kind']} names the payload shape only")
                             if unit == "probability" else
                             f"{family}: the answer is a level in {unit} ({bundle.manifest['scale']} scale)",
                             "unit": unit,
                             "family": family,
                             "data": request["data"],
                             "config": {"input": "json", "provider": self.name,
                                        "family": bundle.combination["family"],
                                        "output_kind": bundle.combination["output_kind"],
                                        "state": bundle.state_ref, "as_of": request["as_of"], "parameters": {}}})
        return examples

    # ------------------------------------------------------------------ the question envelope

    def data_requirement(self):
        """This engine cannot answer without the caller's window, and it says so before anything runs.

        A person who typed a sentence and attached nothing used to wait for the engine to start and come back with
        `PROVIDER_ERROR: data must contain exactly columns, values, scale and scaler_digest` (2026-09-24). The
        framework asks this first and refuses the envelope by name, saying what to attach."""
        return {"required": True,
                "why": "a forecast is made from the caller's own window of observations; this provider holds none",
                "shape": "either raw rows in the series' own units -- a CSV or a list of row objects carrying the "
                         "fitted input columns by name, at the bundle's own sampling step, at least `window` of them "
                         "(the last ones are used and the bundle's own scaler is applied here) -- or an "
                         "already-standardized window: a JSON object with exactly columns, values, scale and "
                         "scaler_digest (the catalog example carries one that runs)"}

    def question_types(self):
        """The types a caller may ask this area, with the fields each takes.

        `interval` is answered by a bundle whose manifest declares a `quantile` head, from the fitted pair that covers
        the confidence level asked for, and refused by every other bundle -- by `NOT_ESTIMABLE` when the bundle has no
        distribution at all, and by `CONFIDENCE_LEVEL_NOT_FITTED` when it has quantiles but not that pair.
        `anomaly_risk` stays refused by every bundle, quantile head or not: a few fitted quantiles are points of a
        distribution, not the distribution. Both types are DECLARED so the refusal can say the true thing -- a type the
        area does not declare is refused by the envelope as UNSUPPORTED_QUESTION_TYPE, which says only that the word is
        unknown here."""
        return {"point_forecast": {"required": ["horizon"], "optional": ["target"]},
                "interval": {"required": ["horizon", "confidence_level"], "optional": ["target"]},
                "anomaly_risk": {"required": ["threshold"], "optional": ["horizon", "target"]}}

    def _resolve_question(self, state, question):
        """The one bundle a question is about, or a refusal naming why there is not exactly one.

        The state names a bundle by `state_ref` or by `target_variable`; the question may name its own `target`. A
        horizon must be one the bundle has -- an unsupported horizon is refused by name, never rounded to the nearest one
        that exists. A target two bundles hold is an ambiguity refused with both named, exactly as `chat_request` does."""
        kind = question["type"]
        target = question.get("target", state.get("target_variable"))
        if "target" in question and "target_variable" in state and question["target"] != state["target_variable"]:
            return None, _refusal(MALFORMED_QUESTION, f"the question names target {question['target']!r} and the state "
                                                     f"names target_variable {state['target_variable']!r}; one series, "
                                                     f"one name", kind)
        state_ref = state.get("state_ref")
        if state_ref is None and target is None:
            return None, _refusal(STATE_REQUIRED, "the state must name a fitted model by `state_ref` or a series by "
                                                  f"`target_variable`; this provider holds {self.known_states()}", kind)
        if state_ref is not None:
            bundle = next((b for b in self._bundles if b.state_ref == state_ref), None)
            if bundle is None:
                return None, _refusal(STATE_REQUIRED, f"state_ref {state_ref!r} is not a state this provider holds; it "
                                                      f"holds {self.known_states()}", kind)
            if target is not None and target not in bundle.targets:
                return None, _refusal(NOT_ESTIMABLE, f"fitted state {state_ref!r} forecasts {bundle.targets[0]!r}, "
                                                     f"not {target!r}", kind)
        else:
            holders = [b for b in self._bundles if target in b.targets]
            if not holders:
                return None, _refusal(NOT_ESTIMABLE, f"no configured bundle forecasts {target!r}; available: "
                                                     f"{self._available()}", kind)
            if len(holders) > 1:
                named = " and ".join(b.state_ref for b in holders)
                return None, _refusal(STATE_REQUIRED, f"{target!r} is served by more than one configured bundle "
                                                      f"({named}); name the fitted state by `state_ref` instead of "
                                                      f"letting this pick one", kind)
            bundle = holders[0]
        horizon = question.get("horizon")
        if horizon is not None:
            if type(horizon) is not int or horizon <= 0:
                return None, _refusal(MALFORMED_QUESTION, f"horizon must be a positive integer number of steps, not "
                                                         f"{horizon!r}", kind)
            if horizon not in bundle.horizons:
                return None, _refusal(NOT_ESTIMABLE, f"{bundle.targets[0]!r} ({bundle.state_ref}) is trained for "
                                                     f"horizons {bundle.horizons}, not {horizon}; a horizon this "
                                                     f"model was not trained for is refused, not rounded", kind)
        return bundle, None

    def _answer_payload(self, bundle, question, data, as_of):
        """The real engine, on the same path the workbench takes: `chat_request` builds and checks the request, `load`
        verifies the artifact, `infer` runs the native graph. Nothing about the numbers is computed here."""
        if isinstance(data, list) and len(data) == 1 and _standardized_window(data[0]):
            data = data[0]                                 # the workbench attaches a list of one history window
        config = {"input": "json", "provider": self.name, "family": bundle.combination["family"],
                  "output_kind": bundle.combination["output_kind"], "state": bundle.state_ref,
                  "as_of": as_of or datetime.now(timezone.utc).isoformat(), "parameters": {}}
        request = self._request_for(bundle, f"forecast {bundle.targets[0]} at {question['horizon']} steps",
                                     data, config, target=bundle.targets[0], horizon=question["horizon"])
        result = self.infer(request, self.load(bundle.state_ref))
        answer = result["outputs"][bundle.targets[0]]
        return answer["payload"], request, answer["uncertainty"]

    def _point_forecast(self, bundle, question, data, as_of):
        payload, request, uncertainty = self._answer_payload(bundle, question, data, as_of)
        at = payload["horizons"].index(question["horizon"])
        return {"type": "point_forecast", "values": [payload["values"][0][at]],
                "unit": payload["unit"], "scale": payload["scale"], "targets": list(payload["targets"]),
                "horizons": [question["horizon"]], "state_ref": bundle.state_ref, "as_of": request["as_of"],
                "uncertainty": uncertainty, "execution_authorized": False}

    def _interval(self, bundle, question, data, as_of):
        """The interval of ONE fitted quantile pair, or a refusal that names what is fitted.

        Three refusals, and none of them is a near miss answered anyway: a bundle with no quantile head has no
        distribution to bound; a confidence level that is not a number is malformed; and a level no fitted pair covers
        is refused by name with the levels that exist, because the bounds of an interval are two quantiles somebody
        fitted or they are two numbers somebody invented."""
        kind = question["type"]
        if "quantile" not in bundle.heads:
            return _refusal(NOT_ESTIMABLE, f"{bundle.state_ref} cannot: {NO_DISTRIBUTION}", kind)
        level = question.get("confidence_level")
        if type(level) not in (int, float) or isinstance(level, bool) or not math.isfinite(level) or not 0 < level < 1:
            return _refusal(MALFORMED_QUESTION, f"confidence_level must be a number strictly inside (0, 1), not "
                                                f"{level!r}", kind)
        fitted = bundle.fitted_levels()
        pair = fitted.get(round(float(level), 9))
        if pair is None:
            return _refusal(CONFIDENCE_LEVEL_NOT_FITTED,
                            f"{bundle.state_ref} fitted the quantiles {bundle.quantiles}, whose symmetric pairs cover "
                            f"{sorted(fitted)}; {level} is not one of them. A level this model was not fitted for is "
                            f"refused, not widened or narrowed from one that was", kind)
        payload, request, uncertainty = self._answer_payload(bundle, question, data, as_of)
        at = payload["horizons"].index(question["horizon"])
        low = payload["quantiles"].index(pair[0])
        high = payload["quantiles"].index(pair[1])
        bounds = payload["quantile_values"][0][at]
        return {"type": "interval", "values": [[bounds[low], bounds[high]]],
                "confidence_level": float(level), "quantiles": [pair[0], pair[1]],
                "point": payload["values"][0][at],
                "unit": payload["unit"], "scale": payload["scale"], "targets": list(payload["targets"]),
                "horizons": [question["horizon"]], "state_ref": bundle.state_ref, "as_of": request["as_of"],
                "uncertainty": uncertainty, "execution_authorized": False}

    def answer_questions(self, state, questions, data, as_of):
        """Every question on its own: a point forecast from the graph that has one, a typed refusal for a distribution
        no graph has. A question that fails is refused by name; it never takes the others down with it."""
        answers, used = {}, []
        for name, question in questions.items():
            kind = question["type"]
            bundle, refused = self._resolve_question(state, question)
            if refused is not None:
                answers[name] = refused
                continue
            if kind == "anomaly_risk":
                why = (QUANTILES_ARE_NOT_A_CDF.format(count=len(bundle.quantiles), quantiles=bundle.quantiles)
                       if bundle.quantiles else NO_DISTRIBUTION)
                answers[name] = _refusal(NOT_ESTIMABLE, f"{bundle.state_ref} cannot: {why}; a probability "
                                                        f"of crossing {question['threshold']!r} is a statement about "
                                                        f"that distribution", kind)
            else:
                try:
                    answers[name] = (self._interval(bundle, question, data, as_of) if kind == "interval"
                                     else self._point_forecast(bundle, question, data, as_of))
                except RowAdapterRefusal as exc:
                    # the rows themselves are what is wrong, and the refusal already says which way: keep that name
                    # rather than burying it under the exception class the envelope does not know about
                    answers[name] = _refusal(PROVIDER_ERROR, str(exc), kind)
                    continue
                except (ValueError, RuntimeError) as exc:
                    answers[name] = _refusal(PROVIDER_ERROR, f"{type(exc).__name__}: {exc}", kind)
                    continue
            if bundle.state_ref not in used:
                used.append(bundle.state_ref)
        # one fitted state answered the envelope, or none can be named for it
        answers["__state_ref__"] = used[0] if len(used) == 1 else None
        return answers
