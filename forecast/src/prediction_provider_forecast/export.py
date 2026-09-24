"""Export only an existing E1 DEV checkpoint; never fit or score a model."""

from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

import numpy as np

from .provider import ForecastProvider, cpu_tensorflow, digest, file_digest


def _write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def export_dev(predictor_root, run_root, destination):
    """Requires trusted local owner source and receipts; outputs a portable inference bundle.

    The source directory is executable code, not a user-uploaded model. Run export
    in a fresh isolated CLI process; serving never imports the training repository.
    """
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError("destination already exists; refusing to overwrite an artifact")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".forecast-export-", dir=destination.parent) as scratch:
        staging = Path(scratch) / "bundle"
        result = _export_dev(predictor_root, run_root, staging)
        if destination.exists():
            raise ValueError("destination appeared during export; refusing to overwrite")
        staging.rename(destination)
    return dict(result, bundle=str(destination))


def _export_dev(predictor_root, run_root, destination):
    source = Path(predictor_root).resolve() / "tools"
    root = Path(run_root).resolve()
    out = Path(destination).resolve()
    if out.exists():
        raise ValueError("destination already exists; refusing to overwrite an artifact")
    attempt = root / "attempts" / "R0_s1"
    paths = {"job": attempt / "job.json", "cell": attempt / "cell.json",
             "weights": attempt / "weights.weights.h5", "data": root / "DATA.npz",
             "data_receipt": root / "DATA.json"}
    for path in paths.values():
        if not path.is_file():
            raise FileNotFoundError(f"missing retained DEV artifact: {path}")
    job = json.loads(paths["job"].read_text())
    cell = json.loads(paths["cell"].read_text())
    receipt = json.loads(paths["data_receipt"].read_text())
    design = job["design"]
    if (design.get("schema") != "df_e1_pilot_design.v1" or design.get("phase") != "DEVELOPMENT"
            or job.get("kind") != "fit" or job.get("regime") != "R0" or job.get("seed") != 1
            or cell.get("exposure") != "NO_TEST_ACCESS" or cell.get("regime") != "R0"
            or cell.get("cell_id") != "R0_s1" or cell.get("seed") != 1
            or not cell.get("training", {}).get("restore_verified")
            or cell.get("training", {}).get("updates", 0) <= 0):
        raise ValueError("not a verified retained R0_s1 trained DEV checkpoint")
    if (design["graph"]["core_kind"] != "tcn_w" or design["graph"]["arch"] != "A"
            or design["graph"]["fusion"] != "sequence"
            or design["task"]["target"] != ["Global_active_power"]
            or design["task"]["window_steps"] != 60 or design["task"]["horizon_steps"] != 60
            or design["contract"]["step_seconds"] != 60):
        raise ValueError("unsupported native architecture/task; no automatic substitution")
    hashes = {name: file_digest(path) for name, path in paths.items()}
    if (hashes["data"] != job["data_sha256"] or hashes["data"] != cell["data_sha256"]
            or hashes["data"] != receipt["data_sha256"]
            or len({design["design_sha256"], cell["design_sha256"], receipt["design_sha256"]}) != 1):
        raise ValueError("DEV data/design receipt hash binding mismatch")
    # Only these named arrays are read. Y, eval_origins and saved predictions are never accessed.
    with np.load(paths["data"], allow_pickle=False) as data:
        W, h, j = (int(data[k][0]) for k in ("window", "horizon", "target_channel"))
        mean, sd = data["scaler_mean"], data["scaler_sd"]
        origin = int(data["train_origins"][0])
        x = data["Xs"][origin - W + 1:origin + 1][None, :, :]
    columns = design["graph"]["input_columns"]
    if (W != 60 or h != 60 or origin < W - 1 or x.shape != (1, 60, 7)
            or not np.isfinite(x).all() or j != columns.index("Global_active_power")
            or columns != receipt["input_columns"] or receipt["window"] != W or receipt["horizon"] != h
            or not np.array_equal(mean, receipt["scaler"]["mean"])
            or not np.array_equal(sd, receipt["scaler"]["sd"])):
        raise ValueError("native DEV input/scaler contract mismatch")
    modules = ("df_e1_pilot", "df_mod_e0", "df_e1_loader", "df_e1_regimes")
    if any(name in sys.modules for name in modules):
        raise ValueError("export requires a fresh process with no preloaded native modules")
    source_hashes = {f"tools/{name}.py": file_digest(source / f"{name}.py") for name in modules}
    tf = cpu_tensorflow()
    if tf.__version__ != "2.21.0":
        raise ValueError("native export requires the exercised TensorFlow 2.21.0 environment")
    spec = importlib.util.spec_from_file_location("df_e1_pilot", source / "df_e1_pilot.py")
    native = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = native
    old_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(native)
    finally:
        sys.dont_write_bytecode = old_bytecode
    # The native factory sets TF thread configuration before creating its first op.
    model = native._model_for_target(design["graph"]["assignment"], W, len(columns), j,
                                     job["seed"], core="tcn_w")
    with tf.device("/CPU:0"):
        model.load_weights(str(paths["weights"]))
        det = native.RG.detector_layer_names(model)
        if native.RG.weights_digest(model, det) != cell["detector_digest_after_fit"]:
            raise ValueError("retained detector weights do not match the trained receipt")
        expected = np.asarray(model.predict_on_batch(x))
        if expected.shape != (1, 1) or not np.isfinite(expected).all():
            raise ValueError("native model produced an invalid point forecast")
        expected_values = expected * float(sd[j]) + float(mean[j])

        class NativeGraph(tf.Module):
            def __init__(self):
                super().__init__()
                self.model = model

            @tf.function(input_signature=[tf.TensorSpec((1, W, len(columns)), tf.float32, name="x")])
            def forecast(self, x):
                return {"forecast": self.model(x, training=False)}

        graph = NativeGraph()
        out.mkdir(parents=True)
        tf.saved_model.save(graph, str(out / "saved_model"),
                            signatures={"serving_default": graph.forecast})
    files = {p.relative_to(out).as_posix(): file_digest(p)
             for p in sorted((out / "saved_model").rglob("*")) if p.is_file()}
    scaler = {"mean": mean.tolist(), "sd": sd.tolist(), "fitted_on": receipt["scaler"]["fitted_on"]}
    manifest = {"schema": "prediction_provider.forecast_bundle.v1", "engine": "tensorflow_saved_model",
                "exposure": "DEV_ONLY_NO_TEST_ACCESS", "task_id": "e1.household.W60_h60",
                "columns": columns, "targets": ["Global_active_power"], "window": W,
                "horizons": [h], "step_seconds": 60, "unit": "kW", "scale": "original",
                "scaler": scaler, "scaler_digest": digest(scaler), "files": files,
                "provenance": {"artifact_hashes": hashes, "native_source_hashes": source_hashes,
                               "design_sha256": design["design_sha256"], "cell_id": "R0_s1",
                               "updates": cell["training"]["updates"],
                               "restored_checkpoint_epoch": cell["training"]["restored_checkpoint_epoch"],
                               "tensorflow": tf.__version__, "numpy": np.__version__,
                               "parity_population": "one DEV TRAIN history window; no labels read",
                               "origin_row_in_dev_slice": origin}}
    _write(out / "manifest.json", manifest)
    provider = ForecastProvider(out)
    data = {"columns": columns, "values": x[0].tolist(), "scale": "train_standardized",
            "scaler_digest": manifest["scaler_digest"]}
    request = provider.chat_request("forecast Global_active_power at 60 steps", data,
                                    {"provider": provider.name, "family": "regression_forecasting",
                                     "output_kind": "point_forecast", "input": "json",
                                     "as_of": datetime.now(timezone.utc).isoformat(),
                                     "state": provider.known_states()[0],
                                     "parameters": {"request_id": "retained-dev-example"}})
    state = provider.load(request["fitted_state_ref"])
    answer = provider.infer(request, state)
    actual = answer["outputs"]["Global_active_power"]["payload"]["values"]
    np.testing.assert_allclose(actual, expected_values, rtol=1e-6, atol=1e-6)
    # Read-only source artifacts must not change underneath export.
    if hashes != {name: file_digest(path) for name, path in paths.items()}:
        raise ValueError("retained source artifacts changed during export")
    if source_hashes != {f"tools/{name}.py": file_digest(source / f"{name}.py") for name in modules}:
        raise ValueError("native source changed during export")
    _write(out / "example_request.json", request)
    example = provider.chat_examples()[0]
    _write(out / "example_data.json", example["data"])
    _write(out / "example_config.json", example["config"])
    _write(out / "parity.json", {"native_values": expected_values.tolist(), "provider_values": actual,
                                 "rtol": 1e-6, "atol": 1e-6,
                                 "max_absolute_error": float(np.max(np.abs(np.asarray(actual) - expected_values))),
                                 "state_digest": state["digest"], "model_sha256": state["model_sha256"],
                                 "input_sha256": digest(data), "population": "DEV TRAIN history only",
                                 "no_training": True, "no_heldout_scoring": True, "device": "CPU"})
    return {"bundle": str(out), "state_ref": state["state_ref"], "native_parity": "PASS"}
