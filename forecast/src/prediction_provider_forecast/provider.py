"""CPU-only adapter around an exported, retained native DEV forecasting graph."""

from __future__ import annotations

import copy
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import threading

import numpy as np


COMBINATION = {"operation": "infer", "family": "regression_forecasting", "output_kind": "point_forecast"}


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


class ForecastProvider:
    name = "predictor_forecast"

    def __init__(self, bundle=None):
        configured = bundle or os.environ.get("M5PHET_FORECAST_BUNDLE")
        self._bundle = Path(configured).resolve() if configured else None
        self._engine = None
        self._worker_python = os.environ.get("M5PHET_FORECAST_PYTHON")
        if self._worker_python and (not Path(self._worker_python).is_absolute()
                                    or not Path(self._worker_python).is_file()):
            raise ValueError("M5PHET_FORECAST_PYTHON must be an operator-configured absolute Python executable")
        self._lock = threading.RLock()
        self._manifest = None
        if self._bundle is not None:
            path = self._bundle / "manifest.json"
            self._manifest = json.loads(path.read_text())
            self._manifest_hash = file_digest(path)
            self._validate_manifest()
            self._digest = digest(self._manifest)
            self._state_ref = "e1-household-r0-s1:" + self._digest

    def _validate_manifest(self):
        m = self._manifest
        if (m.get("schema") != "prediction_provider.forecast_bundle.v1"
                or m.get("engine") != "tensorflow_saved_model"
                or m.get("exposure") != "DEV_ONLY_NO_TEST_ACCESS"
                or m.get("targets") != ["Global_active_power"]
                or m.get("horizons") != [60]
                or m.get("window") != 60
                or m.get("step_seconds") != 60
                or m.get("unit") != "kW" or m.get("scale") != "original"):
            raise ValueError("unsupported native DEV bundle contract")
        cols = m.get("columns")
        expected = ["Global_reactive_power", "Voltage", "Global_intensity", "Sub_metering_1",
                    "Sub_metering_2", "Sub_metering_3", "Global_active_power"]
        if cols != expected:
            raise ValueError("bundle input columns do not match native graph")
        if m.get("task_id") != "e1.household.W60_h60":
            raise ValueError("bundle task identity is unsupported")
        scaler = m.get("scaler", {})
        for key in ("mean", "sd"):
            values = scaler.get(key)
            if (not isinstance(values, list) or len(values) != len(cols)
                    or any(type(v) not in (int, float) or not math.isfinite(v) for v in values)):
                raise ValueError("invalid train-only scaler")
        if any(s <= 0 for s in scaler["sd"]) or scaler.get("fitted_on") != "train windows only":
            raise ValueError("invalid train-only scaler")
        if m.get("scaler_digest") != digest(scaler):
            raise ValueError("scaler hash mismatch")
        files = m.get("files")
        if not isinstance(files, dict) or not files or "saved_model/saved_model.pb" not in files:
            raise ValueError("missing native graph file hashes")
        for name, sha in files.items():
            path = Path(name)
            if (not name.startswith("saved_model/") or path.is_absolute() or ".." in path.parts
                    or not re.fullmatch(r"[0-9a-f]{64}", str(sha))):
                raise ValueError("invalid artifact path or hash")

    def known_states(self):
        return [self._state_ref] if self._manifest is not None else []

    def capabilities(self):
        return {"operations": ["infer"], "families": ["regression_forecasting"],
                "output_kinds": ["point_forecast"], "uncertainty_methods": ["none"],
                "supported": [dict(COMBINATION)], "known_states": self.known_states(),
                "backend": "tensorflow_saved_model_cpu_subprocess" if self._worker_python else "tensorflow_saved_model_cpu",
                "input_schema": {"kind": "one_history_window", "scale": "train_standardized"},
                "output_schema": self._output_schema() if self._manifest else None}

    def _output_schema(self):
        return {k: copy.deepcopy(self._manifest[k]) for k in ("targets", "horizons", "unit", "scale")}

    def _verify(self):
        if file_digest(self._bundle / "manifest.json") != self._manifest_hash:
            raise ValueError("manifest hash changed; instantiate a new provider for a new state")
        actual = {p.relative_to(self._bundle).as_posix()
                  for p in (self._bundle / "saved_model").rglob("*") if p.is_file()}
        if actual != set(self._manifest["files"]):
            raise ValueError("native artifact file set/hash mismatch")
        for name, sha in self._manifest["files"].items():
            path = self._bundle / name
            if not path.resolve().is_relative_to(self._bundle) or path.is_symlink():
                raise ValueError("artifact path escapes the bundle")
            if file_digest(path) != sha:
                raise ValueError(f"native artifact hash mismatch: {name}")

    def _state(self):
        return {"state_ref": self._state_ref, "digest": self._digest,
                "model_sha256": digest(self._manifest["files"]),
                "task_id": self._manifest["task_id"], "exposure": self._manifest["exposure"]}

    def load(self, state_ref):
        if state_ref not in self.known_states():
            raise ValueError("unknown fitted state; configure an exported trained DEV bundle")
        with self._lock:
            self._verify()
            if self._engine is None:
                if self._worker_python:
                    loaded = self._native_process("load", state_ref=state_ref)
                    if loaded != self._state():
                        raise ValueError("native process loaded a different state")
                    self._engine = "operator_native_process"
                    return loaded
                tf = cpu_tensorflow()
                with tf.device("/CPU:0"):
                    loaded = tf.saved_model.load(str(self._bundle / "saved_model"))
                engine = loaded.signatures["serving_default"]
                args, kwargs = engine.structured_input_signature
                outputs = engine.structured_outputs
                if (args or set(kwargs) != {"x"} or kwargs["x"].shape != (1, 60, 7)
                        or kwargs["x"].dtype != tf.float32 or set(outputs) != {"forecast"}
                        or outputs["forecast"].shape != (1, 1) or outputs["forecast"].dtype != tf.float32):
                    raise ValueError("native graph signature does not match the declared forecast contract")
                self._engine = engine
            return self._state()

    def _native_process(self, command, *, state_ref=None, request=None):
        # Only the operator supplies this executable and bundle path, never chat config.
        argv = [self._worker_python, "-m", "prediction_provider_forecast.cli", command,
                "--bundle", str(self._bundle)]
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
        if self._manifest is None:
            raise ValueError("no trained DEV bundle configured")
        if not isinstance(request, dict) or request.get("schema_version") != "m5phet.task.draft2":
            raise ValueError("expected m5phet.task.draft2 request")
        expected = dict(COMBINATION, provider_ref=self.name, task_id=self._manifest["task_id"],
                        fitted_state_ref=self._state_ref)
        if any(request.get(k) != v for k, v in expected.items()):
            raise ValueError("unsupported request task, provider, operation or fitted state")
        if not isinstance(request.get("request_id"), str) or not request["request_id"].strip():
            raise ValueError("request_id must be nonempty")
        _aware_time(request.get("as_of"))
        schema = request.get("output_schema")
        if (schema != self._output_schema() or not isinstance(schema.get("horizons"), list)
                or any(type(h) is not int for h in schema["horizons"])):
            raise ValueError("output schema must match trained targets, horizons, unit and scale")
        data = request.get("data")
        if not isinstance(data, dict) or set(data) != {"columns", "values", "scale", "scaler_digest"}:
            raise ValueError("data must contain exactly columns, values, scale and scaler_digest")
        if (data["columns"] != self._manifest["columns"] or data["scale"] != "train_standardized"
                or data["scaler_digest"] != self._manifest["scaler_digest"]):
            raise ValueError("input columns, scale or scaler_digest mismatch")
        values = data["values"]
        if not isinstance(values, list) or len(values) != self._manifest["window"]:
            raise ValueError("expected exactly 60 chronological history rows, ending at the origin")
        for row in values:
            if not isinstance(row, list) or len(row) != len(self._manifest["columns"]):
                raise ValueError("input feature count mismatch")
            if any(type(v) not in (int, float) or abs(v) > float(np.finfo(np.float32).max) or not math.isfinite(v) for v in row):
                raise ValueError("history values must be finite float32-representable numbers, not bools")
        if request.get("population") != {"input_sha256": digest(data)}:
            raise ValueError("population must bind this exact input window")
        return np.asarray(values, dtype=np.float32)[None, :, :]

    def infer(self, request, state):
        x = self._check_request(request)
        if state != self._state():
            raise ValueError("loaded state identity mismatch")
        with self._lock:
            self._verify()
            if self._engine is None:
                raise ValueError("load the fitted state before infer")
            if self._worker_python:
                return self._native_process("infer", request=request)
            tf = cpu_tensorflow()
            with tf.device("/CPU:0"):
                result = self._engine(x=tf.convert_to_tensor(x))["forecast"].numpy()
        if result.shape != (1, 1) or not np.isfinite(result).all():
            raise ValueError("native engine returned invalid forecast shape or non-finite values")
        # Preserve native float32 arithmetic, including its original-scale readout.
        j = self._manifest["columns"].index(self._manifest["targets"][0])
        scaler = self._manifest["scaler"]
        values = result * float(scaler["sd"][j]) + float(scaler["mean"][j])
        if not np.isfinite(values).all():
            raise ValueError("native output scaling produced a non-finite forecast")
        target = self._manifest["targets"][0]
        payload = dict(self._output_schema(), values=values.tolist())
        return {"outputs": {target: {"status": "OK", "uncertainty": "none", "payload": payload}},
                "population": copy.deepcopy(request["population"])}

    def chat_slots(self):
        """What this engine needs, and the only values it has. The workbench resolves ordinary phrasing against exactly
        this, so a paraphrase can reach the model and an unsupported target or horizon cannot."""
        if self._manifest is None:
            return []
        targets, horizons = self._manifest["targets"], self._manifest["horizons"]
        aliases = {t: [t.replace("_", " "), t.replace("_", " ").lower()] for t in targets}
        if "Global_active_power" in targets:
            aliases["Global_active_power"] += ["household power", "active power", "power consumption",
                                               "consumption", "potencia", "consumo"]
        horizon_aliases = {}
        for h in horizons:
            names = [f"{h} steps", f"{h} minutes", f"{h} pasos", f"{h} minutos"]
            if h == 60:
                names += ["one hour", "an hour", "next hour", "una hora", "la proxima hora", "próxima hora"]
            horizon_aliases[str(h)] = names
        return [{"name": "target", "allowed": list(targets), "aliases": aliases},
                {"name": "horizon", "allowed": [int(h) for h in horizons], "type": "integer",
                 "aliases": horizon_aliases,
                 "number_hints": ["step", "horizon", "minute", "hour", "ahead", "paso", "minuto", "hora", "adelante"]}]

    def chat_request(self, prompt, data, config, parameters=None):
        if self._manifest is None:
            raise ValueError("no trained DEV bundle configured")
        if not isinstance(prompt, str) or len(prompt) > 512:
            raise ValueError("prompt must be a string of at most 512 characters")
        if parameters:
            # Resolved against this bundle's own declared values, so neither a target nor a horizon can arrive from
            # outside what was actually trained. The canonical phrasing below remains accepted as it always was.
            if ([parameters.get("target")] != self._manifest["targets"]
                    or [int(parameters.get("horizon", -1))] != self._manifest["horizons"]):
                raise ValueError(f"this bundle forecasts {self._manifest['targets']} at {self._manifest['horizons']}")
        else:
            match = re.fullmatch(r"forecast ([A-Za-z][A-Za-z0-9_]*) at ([1-9][0-9]{0,4}) steps", prompt)
            if (not match or [match[1]] != self._manifest["targets"]
                    or [int(match[2])] != self._manifest["horizons"]):
                raise ValueError("expected: forecast Global_active_power at 60 steps")
        required = {"provider", "family", "output_kind", "state", "as_of", "parameters"}
        # Shared workbench fields are not forecasting model parameters.
        transport = {"input", "presentation", "context", "asset", "language", "max_age_seconds", "options"}
        if (not isinstance(config, dict) or not required <= set(config)
                or set(config) - required - transport):
            raise ValueError("config requires provider, family, output_kind, state, as_of, parameters; input is optional")
        if (config["provider"] != self.name or config["family"] != COMBINATION["family"]
                or config["output_kind"] != COMBINATION["output_kind"] or config.get("input", "json") != "json"):
            raise ValueError("chat config must select this point-forecast provider with JSON input")
        parameters = config["parameters"]
        if not isinstance(parameters, dict) or set(parameters) - {"request_id"}:
            raise ValueError("parameters only supports optional request_id; no implicit model settings")
        request_id = parameters.get("request_id", "forecast:" + digest({"prompt": prompt, "data": data, "config": config}))
        request = {"schema_version": "m5phet.task.draft2", "request_id": request_id,
                   "as_of": config["as_of"], "fitted_state_ref": config["state"],
                   **COMBINATION, "task_id": self._manifest["task_id"], "provider_ref": self.name,
                   "output_schema": self._output_schema(), "data": copy.deepcopy(data),
                   "population": {"input_sha256": digest(data)},
                   "execution_constraints": {"partial_results": False}}
        self._check_request(request)
        return request

    def chat_examples(self):
        """Actual DEV history from explicit export; no model load, training or synthetic fallback."""
        if self._manifest is None:
            return []
        request = json.loads((self._bundle / "example_request.json").read_text())
        self._check_request(request)
        return [{"title": "DEVELOPMENT: retained household-power model, 60-minute forecast",
                 "prompt": "forecast Global_active_power at 60 steps", "data": request["data"],
                 "config": {"input": "json", "provider": self.name, "family": COMBINATION["family"],
                            "output_kind": COMBINATION["output_kind"], "state": self._state_ref,
                            "as_of": request["as_of"], "parameters": {}}}]
