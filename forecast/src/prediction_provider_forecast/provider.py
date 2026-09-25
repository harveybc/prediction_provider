"""CPU-only adapter around exported, retained native DEV forecasting graphs."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
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
EXPOSURES = ("DEV_ONLY_NO_TEST_ACCESS", "PREDICTOR_EXAMPLE_NO_EXPOSURE_RECEIPT")

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

#: why an interval or an anomaly risk is refused by every bundle this package serves. The retained graphs are point
#: models: one number per target and horizon, no quantile head, no ensemble, no residual distribution recorded at
#: export. A bound or a probability of crossing a threshold would have to be manufactured from nothing, so both types are
#: DECLARED (the shape is visible and the refusal is typed) and REFUSED with this reason. The day a bundle carries
#: quantiles, that is where an interval gets computed -- not before.
NO_DISTRIBUTION = ("it emits a point estimate and no predictive distribution; an interval would require a quantile or "
                   "ensemble head this bundle does not have")


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
        for key in ("aliases", "horizon_aliases"):
            declared = m.get(key) or {}
            if not isinstance(declared, dict):
                raise ValueError(f"{self.path.name}: {key} must be a mapping")
            known = set(m["targets"]) if key == "aliases" else {str(int(h)) for h in m["horizons"]}
            if set(declared) - known:
                raise ValueError(f"{self.path.name}: {key} names a value this bundle does not have")
            if any(not _text(v) for names in declared.values() for v in names):
                raise ValueError(f"{self.path.name}: {key} entries must be nonempty strings")

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
        return {"operations": ["infer"], "families": families or [COMBINATION["family"]],
                "output_kinds": ["point_forecast"], "uncertainty_methods": ["none"],
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
                width = len(bundle.targets) * len(bundle.horizons)
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
        width = len(bundle.targets) * len(bundle.horizons)
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
        payload = dict(bundle.output_schema(), values=values.reshape(1, len(bundle.horizons)).tolist())
        return {"outputs": {target: {"status": "OK", "uncertainty": "none", "payload": payload}},
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

    def question_types(self):
        """The types a caller may ask this area, with the fields each takes.

        `interval` and `anomaly_risk` are declared on purpose although every configured bundle refuses them: a type the
        area does not declare is refused by the envelope as UNSUPPORTED_QUESTION_TYPE, which says only that the word is
        unknown here. Declaring them lets the refusal say the true thing -- the model exists, it answers the point
        forecast, and it has no distribution to bound -- and it lets the catalog show the shape a future bundle with a
        quantile head would fill."""
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

    def _point_forecast(self, bundle, question, data, as_of):
        """The real engine, on the same path the workbench takes: `chat_request` builds and checks the request, `load`
        verifies the artifact, `infer` runs the native graph. Nothing about the number is computed here."""
        if isinstance(data, list) and len(data) == 1:
            data = data[0]                                 # the workbench attaches a list of one history window
        config = {"input": "json", "provider": self.name, "family": bundle.combination["family"],
                  "output_kind": bundle.combination["output_kind"], "state": bundle.state_ref,
                  "as_of": as_of or datetime.now(timezone.utc).isoformat(), "parameters": {}}
        request = self.chat_request(f"forecast {bundle.targets[0]} at {question['horizon']} steps", data, config,
                                    parameters={"target": bundle.targets[0], "horizon": question["horizon"]})
        result = self.infer(request, self.load(bundle.state_ref))
        payload = result["outputs"][bundle.targets[0]]["payload"]
        at = payload["horizons"].index(question["horizon"])
        return {"type": "point_forecast", "values": [payload["values"][0][at]],
                "unit": payload["unit"], "scale": payload["scale"], "targets": list(payload["targets"]),
                "horizons": [question["horizon"]], "state_ref": bundle.state_ref, "as_of": request["as_of"],
                "uncertainty": "none", "execution_authorized": False}

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
            if kind == "interval":
                answers[name] = _refusal(NOT_ESTIMABLE, f"{bundle.state_ref} cannot: {NO_DISTRIBUTION}", kind)
            elif kind == "anomaly_risk":
                answers[name] = _refusal(NOT_ESTIMABLE, f"{bundle.state_ref} cannot: {NO_DISTRIBUTION}; a probability "
                                                        f"of crossing {question['threshold']!r} is a statement about "
                                                        f"that distribution", kind)
            else:
                try:
                    answers[name] = self._point_forecast(bundle, question, data, as_of)
                except (ValueError, RuntimeError) as exc:
                    answers[name] = _refusal(PROVIDER_ERROR, f"{type(exc).__name__}: {exc}", kind)
                    continue
            if bundle.state_ref not in used:
                used.append(bundle.state_ref)
        # one fitted state answered the envelope, or none can be named for it
        answers["__state_ref__"] = used[0] if len(used) == 1 else None
        return answers
