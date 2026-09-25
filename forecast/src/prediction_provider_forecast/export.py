"""Export only an existing trained checkpoint; never fit or score a model."""

import collections
import csv
from datetime import datetime, timezone
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np

from .provider import (COMBINATION, REPRESENTATION_NOT_RECORDED, SCHEMA_V2, UNMEASURED, ForecastProvider,
                       cpu_tensorflow, digest,
                       file_digest)


def _write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def _staged(destination, build):
    """Publish a bundle only once it is complete and its parity has passed.

    Everything is written into a sibling temporary directory and renamed at the end, so a refusal half way through leaves
    no directory that looks like a servable bundle. An operator who finds a bundle path can rely on it having passed.
    """
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError("destination already exists; refusing to overwrite an artifact")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".forecast-export-", dir=destination.parent) as scratch:
        staging = Path(scratch) / "bundle"
        result = build(staging)
        if destination.exists():
            raise ValueError("destination appeared during export; refusing to overwrite")
        staging.rename(destination)
    return dict(result, bundle=str(destination))


def export_dev(predictor_root, run_root, destination):
    """Requires trusted local owner source and receipts; outputs a portable inference bundle.

    The source directory is executable code, not a user-uploaded model. Run export
    in a fresh isolated CLI process; serving never imports the training repository.
    """
    return _staged(destination, lambda staging: _export_dev(predictor_root, run_root, staging))


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


# ---------------------------------------------------------------------------------------------------------------------
# predictor's own committed example checkpoints
#
# The household bundle above comes from a governed DEV run with an exposure receipt. predictor also ships trained example
# checkpoints under `examples/results/`, committed next to the configuration and the data that produced them. Those have
# no exposure receipt and no measured quality, so this exporter publishes them saying exactly that rather than borrowing
# the household bundle's wording. It still refuses anything it cannot attribute: an uncommitted or modified artifact has
# no author and no date, and a bundle that cannot name its origin is worse than no bundle at all.
# ---------------------------------------------------------------------------------------------------------------------

#: predictor writes `<name>_model.keras` and `<name>_model_metadata.json` side by side. The metadata is the only record of
#: the feature order the graph was trained on, so an export without it is refused rather than guessed from the CSV.
METADATA_SUFFIX = "_metadata.json"

#: what predictor's own preprocessor appends to every window when `add_window_stats` is on. This exporter never reimplements
#: it -- it calls predictor's function -- but it does record which module it called and that module's hash.
WINDOW_STATS_MODULE = "preprocessor_plugins/stl_preprocessor.py"


def export_predictor_example(predictor_root, inference_config, destination):
    """Export one committed predictor example checkpoint as a servable bundle. Never trains, never scores, never trades."""
    return _staged(destination, lambda staging: _export_predictor_example(predictor_root, inference_config, staging))


def _git(root, *args):
    """Read-only interrogation of a repository this package must never write to.

    `--no-optional-locks` keeps `git status` from refreshing the index, which would touch a sibling repository's `.git`
    directory for no reason. A missing git, a missing repository or a non-zero exit is an unattributable artifact.
    """
    try:
        done = subprocess.run(["git", "-C", str(root), "--no-optional-locks", *args],
                              capture_output=True, text=True, check=False, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError(f"cannot read git provenance from {root}: {exc}") from exc
    if done.returncode:
        raise ValueError(f"cannot read git provenance from {root}: {done.stderr.strip()[:500]}")
    return done.stdout


def _attribution(root, paths, subject):
    """Who trained this, and when, taken from the repository rather than from anybody's memory.

    The date and author come from the commit that last touched the WEIGHTS, not from whichever of the inputs happens to
    sort first: a later edit to the configuration file beside them would otherwise be published as the training date.
    """
    relative = sorted(str(p.relative_to(root)) for p in paths)
    subject = str(Path(subject).relative_to(root))
    dirty = _git(root, "status", "--porcelain", "--", *relative).strip()
    if dirty:
        raise ValueError("refusing to export an uncommitted or modified predictor artifact; it has no attributable "
                         f"author or date:\n{dirty[:500]}")
    record = _git(root, "log", "-1", "--format=%H%x1f%an%x1f%aI%x1f%s", "--", subject).strip()
    if not record:
        raise ValueError(f"{subject} has no commit in {root}; an unattributable checkpoint is not exported")
    commit, author, when, subject = record.split("\x1f")
    return {"commit": commit, "author": author, "authored_at": when, "commit_subject": subject,
            "committed_paths": relative}


def _read_columns(path, columns):
    """The training CSV, read for its header order and its history rows. No label column is ever selected."""
    with Path(path).open(newline="") as stream:
        reader = csv.reader(stream)
        header = next(reader)
        if len(set(header)) != len(header):
            raise ValueError(f"{path} has duplicate column names; the feature order cannot be resolved")
        wanted = set(columns)
        # The graph was trained on the CSV's own left-to-right order. If the metadata lists the same names in a different
        # order the export would feed every channel to the wrong filter and still produce a confident number, so it stops.
        if [c for c in header if c in wanted] != list(columns):
            raise ValueError("the model metadata's feature order does not match the training CSV's column order")
        index = {name: i for i, name in enumerate(header)}
        stamps, rows = [], []
        for raw in reader:
            stamps.append(raw[index[header[0]]])
            rows.append([float(raw[index[c]]) for c in columns])
    return header[0], stamps, rows


def _grid_step(stamps):
    """The spacing of the input grid, measured rather than assumed.

    A market series has gaps -- weekends, holidays -- so the step is the modal spacing and the share it covers is
    published beside it. A file with no dominant spacing is refused: naming a step for it would invent a calendar.
    """
    times = []
    for value in stamps:
        try:
            times.append(datetime.fromisoformat(value))
        except ValueError as exc:
            raise ValueError(f"unparseable timestamp {value!r} in the training file") from exc
    deltas = [int((b - a).total_seconds()) for a, b in zip(times, times[1:]) if b > a]
    if not deltas:
        raise ValueError("the training file has no increasing timestamps; its grid cannot be measured")
    step, count = collections.Counter(deltas).most_common(1)[0]
    share = count / len(deltas)
    if share < 0.5:
        raise ValueError(f"the training file has no dominant step ({step}s covers only {share:.0%} of the rows)")
    return step, round(share, 6)


def _window_stats(predictor_root, window, columns, config):
    """Append the derived channels using predictor's OWN preprocessor function.

    Reimplementing the recipe here would be a fork: it would keep working after predictor changed the statistics, and the
    graph would then be fed channels it was never trained on while every hash in the manifest still matched. So the real
    module is imported by path and its hash is recorded, exactly as the household export does with the native factory.
    """
    source = Path(predictor_root) / WINDOW_STATS_MODULE
    if not source.is_file():
        raise FileNotFoundError(f"missing predictor preprocessor: {source}")
    if str(predictor_root) not in sys.path:
        sys.path.insert(0, str(predictor_root))
    from preprocessor_plugins.stl_preprocessor import PreprocessorPlugin
    payload = {"X_train": window, "feature_names": list(columns)}
    # __new__ rather than __init__: only this one pure method is wanted, not whatever a full preprocessor sets up.
    plugin = PreprocessorPlugin.__new__(PreprocessorPlugin)
    plugin._add_window_stats_features(payload, config)
    derived = [name for name in payload["feature_names"] if name not in columns]
    out = np.asarray(payload["X_train"], dtype=np.float32)
    if out.shape != (1, window.shape[1], len(columns) + len(derived)) or not np.isfinite(out).all():
        raise ValueError("predictor's window statistics produced an unusable input window")
    return out, list(columns) + derived, file_digest(source)


def _export_predictor_example(predictor_root, inference_config, destination):
    root = Path(predictor_root).resolve()
    config_path = Path(inference_config)
    config_path = (config_path if config_path.is_absolute() else root / config_path).resolve()
    out = Path(destination).resolve()
    if not config_path.is_file():
        raise FileNotFoundError(f"missing predictor configuration: {config_path}")
    config = json.loads(config_path.read_text())
    for key in ("load_model", "x_train_file", "use_normalization_json", "window_size", "predicted_horizons",
                "target_column", "signal_type", "predictor_plugin"):
        if key not in config:
            raise ValueError(f"{config_path.name} does not declare {key}; it is not an exportable inference config")
    model_path = (root / config["load_model"]).resolve()
    metadata_path = model_path.with_name(model_path.stem + METADATA_SUFFIX)
    train_path = (root / config["x_train_file"]).resolve()
    scaler_path = (root / config["use_normalization_json"]).resolve()
    paths = {"model": model_path, "metadata": metadata_path, "config": config_path,
             "train_data": train_path, "normalization": scaler_path}
    for name, path in paths.items():
        if not path.is_file():
            raise FileNotFoundError(f"missing predictor artifact ({name}): {path}")
        if not path.is_relative_to(root):
            raise ValueError(f"{name} lies outside the predictor checkout; refusing to export it")
    metadata = json.loads(metadata_path.read_text())

    if metadata.get("model_type") != "binary":
        # Only the binary heads have been exercised end to end here. A regression head would need its target scaler and a
        # different readout, and guessing which would publish numbers in a unit nobody declared.
        raise ValueError(f"unsupported predictor model_type {metadata.get('model_type')!r}; only 'binary' is exported")
    signal = metadata.get("signal_type")
    if not signal or signal != config["signal_type"]:
        raise ValueError("the saved metadata and the configuration disagree about which signal this model predicts")
    window_size = metadata.get("window_size")
    if window_size != config["window_size"] or not isinstance(window_size, int) or window_size <= 0:
        raise ValueError("the saved metadata and the configuration disagree about the window size")
    horizons = config["predicted_horizons"]
    if horizons != [1] or metadata.get("output_names") != ["output_horizon_1"]:
        raise ValueError("only a single-head next-step classifier has been exported; no multi-head layout is guessed")
    columns = metadata.get("feature_columns")
    if not isinstance(columns, list) or not columns or len(set(columns)) != len(columns):
        raise ValueError("the saved metadata does not list distinct feature columns")
    excluded = set(metadata.get("excluded_columns") or ())
    if excluded & set(columns):
        # These are the label columns. A label among the inputs is the failure this whole package exists to avoid.
        raise ValueError("the saved metadata lists an excluded label column among its features")

    attribution = _attribution(root, paths.values(), model_path)
    hashes = {name: file_digest(path) for name, path in paths.items()}
    time_column, stamps, rows = _read_columns(train_path, columns)
    if time_column in columns:
        raise ValueError("the timestamp column is not an input feature of this graph")
    if len(rows) < window_size:
        raise ValueError(f"{train_path.name} has fewer than {window_size} rows; no history window can be taken")
    step_seconds, grid_share = _grid_step(stamps)
    base = np.asarray(rows[:window_size], dtype=np.float32)[None, :, :]
    if not np.isfinite(base).all():
        raise ValueError("the first training history window contains non-finite values")
    stats_config = {"add_window_stats": config.get("add_window_stats", False),
                    "window_stats_periods": config.get("window_stats_periods", [12, 48]),
                    "target_column": config["target_column"]}
    x, all_columns, preprocessor_hash = _window_stats(root, base, columns, stats_config)

    tf = cpu_tensorflow()
    import keras
    model = keras.saving.load_model(str(model_path), compile=False)
    if tuple(model.input_shape) != (None, window_size, len(all_columns)):
        raise ValueError(f"the saved graph expects {model.input_shape}, not the window this configuration describes")
    head = model.get_layer(metadata["output_names"][0])
    if getattr(head.activation, "__name__", None) != "sigmoid" or head.units != 1:
        # The bundle publishes this number as a probability. A linear or multi-unit head would make that a false unit.
        raise ValueError("the output head is not a single sigmoid unit, so its output is not a probability")
    with tf.device("/CPU:0"):
        expected = np.asarray(model.predict_on_batch(x))
        if expected.shape != (1, 1) or not np.isfinite(expected).all() or not (0.0 <= float(expected[0][0]) <= 1.0):
            raise ValueError("the native model did not produce a finite probability")

        class NativeGraph(tf.Module):
            def __init__(self):
                super().__init__()
                self.model = model

            @tf.function(input_signature=[tf.TensorSpec((1, window_size, len(all_columns)), tf.float32, name="x")])
            def forecast(self, x):
                return {"forecast": self.model(x, training=False)}

        graph = NativeGraph()
        out.mkdir(parents=True)
        tf.saved_model.save(graph, str(out / "saved_model"),
                            signatures={"serving_default": graph.forecast})
    files = {p.relative_to(out).as_posix(): file_digest(p)
             for p in sorted((out / "saved_model").rglob("*")) if p.is_file()}

    statistics = json.loads(scaler_path.read_text())
    scaler = {"kind": "per_column_zscore",
              "columns": {c: statistics[c] for c in columns if c in statistics},
              "unscaled_columns": [c for c in all_columns if c not in statistics],
              "fitted_on": (f"predictor {scaler_path.relative_to(root)}; that file records statistics only, so the "
                            f"population they were fitted on is not known to this bundle")}
    name = model_path.stem.replace("_model", "").replace("_", "-").lower()
    manifest = {
        "schema": SCHEMA_V2, "engine": "tensorflow_saved_model",
        # predictor's committed examples carry no held-out exposure receipt, so this bundle claims none. Reusing the
        # household bundle's DEV_ONLY_NO_TEST_ACCESS wording would assert a receipt that was never written.
        "exposure": "PREDICTOR_EXAMPLE_NO_EXPOSURE_RECEIPT",
        "state_id": name, "task_id": f"predictor.{name}.W{window_size}_h{horizons[0]}",
        "title": f"DEVELOPMENT: retained predictor {config['predictor_plugin']} example, {signal} probability",
        "family": "binary_classification",
        "columns": all_columns, "targets": [signal], "horizons": [int(h) for h in horizons],
        "window": window_size, "step_seconds": step_seconds,
        "unit": "probability", "scale": "probability",
        # The graph's own sigmoid output IS the published number. There is no target channel to un-standardise, and
        # rescaling a probability would push it outside [0, 1] while still looking like a forecast.
        "readout": "identity", "input_scale": "predictor_normalized",
        "horizon_meaning": (f"output head {horizons[0]} of predictor's {signal} classifier. How far ahead that label "
                            f"looks is defined by predictor's target plugin and is NOT restated or verified here"),
        "aliases": {signal: [signal.replace("_", " "), signal.replace("_", " ") + " probability"]},
        "horizon_aliases": {str(horizons[0]): ["next step", "one step", "un paso", "proximo paso", "próximo paso"]},
        "scaler": scaler, "scaler_digest": digest(scaler), "files": files,
        "provenance": {
            "trained_on": (f"predictor {train_path.relative_to(root)} as x_train_file, normalized with "
                           f"{scaler_path.relative_to(root)}, configured by {config_path.relative_to(root)}"),
            "trained_by": (f"{attribution['author']} in predictor, with the {config['predictor_plugin']} plugin; "
                           f"commit {attribution['commit']}: {attribution['commit_subject']}"),
            "trained_at": attribution["authored_at"],
            # This package never scores a model. Whatever number a training run printed is not evidence this bundle owns.
            "quality": UNMEASURED,
            "quality_note": ("neither this export nor this provider has evaluated this model on any data. No accuracy, "
                             "calibration, profitability or eligibility claim is made or implied"),
            "artifact_hashes": hashes, "predictor_source_hashes": {WINDOW_STATS_MODULE: preprocessor_hash},
            "predictor_commit": attribution["commit"], "committed_paths": attribution["committed_paths"],
            "derived_columns": [c for c in all_columns if c not in columns],
            "window_stats_config": stats_config,
            "grid": {"step_seconds": step_seconds, "modal_step_share": grid_share,
                     "note": "a market series has gaps; the step is the modal spacing, not a guarantee of regularity"},
            "keras": keras.__version__, "tensorflow": tf.__version__, "numpy": np.__version__,
            "parity_population": "the first TRAIN history window of x_train_file; no label column was read",
            "origin_row_in_train_file": window_size - 1,
        },
    }
    _write(out / "manifest.json", manifest)

    provider = ForecastProvider(out)
    data = {"columns": all_columns, "values": x[0].tolist(), "scale": manifest["input_scale"],
            "scaler_digest": manifest["scaler_digest"]}
    request = provider.chat_request(f"forecast {signal} at {horizons[0]} steps", data,
                                    {"provider": provider.name, "family": manifest["family"],
                                     "output_kind": "point_forecast", "input": "json",
                                     "as_of": datetime.now(timezone.utc).isoformat(),
                                     "state": provider.known_states()[0],
                                     "parameters": {"request_id": "retained-predictor-example"}})
    state = provider.load(request["fitted_state_ref"])
    answer = provider.infer(request, state)
    actual = answer["outputs"][signal]["payload"]["values"]
    np.testing.assert_allclose(actual, expected, rtol=1e-6, atol=1e-6)
    # Read-only source artifacts must not change underneath export.
    if hashes != {name: file_digest(path) for name, path in paths.items()}:
        raise ValueError("the predictor artifacts changed during export")
    if preprocessor_hash != file_digest(root / WINDOW_STATS_MODULE):
        raise ValueError("predictor's preprocessor changed during export")
    _write(out / "example_request.json", request)
    example = provider.chat_examples()[0]
    _write(out / "example_data.json", example["data"])
    _write(out / "example_config.json", example["config"])
    _write(out / "parity.json", {"native_values": expected.tolist(), "provider_values": actual,
                                 "rtol": 1e-6, "atol": 1e-6,
                                 "max_absolute_error": float(np.max(np.abs(np.asarray(actual) - expected))),
                                 "state_digest": state["digest"], "model_sha256": state["model_sha256"],
                                 "input_sha256": digest(data), "population": "TRAIN history only",
                                 "no_training": True, "no_heldout_scoring": True, "device": "CPU"})
    return {"bundle": str(out), "state_ref": state["state_ref"], "native_parity": "PASS"}


# ---------------------------------------------------------------------------------------------------------------------
# a bundle fitted by predictor's `tools/fit_pipeline_spec.py`
#
# WP18 step 7 fits one pipeline spec on a holdout that was SEALED BEFORE the fit and writes, beside the graph, a run
# manifest (`predictor.fitted_forecast.v1`) naming the columns, the window, the horizon, the scaler fitted on the train
# rows only, the seal and the protocol the holdout was scored under. That is everything a servable bundle needs and it is
# all written by the tool that did the fitting, so this exporter READS -- it never re-derives a scaler, never re-reads a
# label, never scores anything. The quality measured on that holdout stays in the evaluation report that measured it;
# this manifest still says `quality: UNMEASURED`, because this package computed none of it.
# ---------------------------------------------------------------------------------------------------------------------

#: schema of predictor's run manifest. A different one is not a weaker manifest but an unknown one.
FITTED_SCHEMA = "predictor.fitted_forecast.v1"

#: exposure of a bundle fitted this way: the seal is the receipt, and it is the only claim made
FITTED_EXPOSURE = "DEV_FIT_HOLDOUT_SEALED_BEFORE_SCORING"


def measured_error_from_report(report, *, report_sha256):
    """The held-out error the evaluation package measured, QUOTED from its report with the conditions that bind it.

    This is not a quality this package computed, and it does not change `provenance.quality`, which stays `UNMEASURED`
    for exactly that reason. It is the report's own first metric set, copied by value together with the corpus seal,
    the protocol digest, the row count and the digest of the file it was read from -- everything a reader needs to go
    back to the report and check it. A number without those conditions is the thing this package refuses to publish;
    a number with them is the report speaking, and a catalog that cannot repeat what the report says forces every
    reader to be told the error out of band.

    Nothing here says the model is good, and nothing here says the number generalises: the population is whatever the
    seal names, and whether those rows ever ranked this model is a question the seal cannot answer and this block does
    not pretend to.
    """
    metric_set = (report.get("metric_sets") or [None])[0]
    if not isinstance(metric_set, dict) or not isinstance(metric_set.get("values"), dict):
        raise ValueError("the evaluation report carries no metric set; a bundle cannot quote an error from it")
    baseline = metric_set.get("baseline") or {}
    return {
        "source": "m5phet-evaluation-report/1",
        "metric_set": metric_set.get("name"),
        "values": dict(metric_set["values"]),
        "baseline": {"name": baseline.get("name"), "mae": baseline.get("mae"), "rmse": baseline.get("rmse"),
                     "same_rows_as_model": baseline.get("same_rows_as_model")},
        "scale": report.get("scale"),
        "target": report.get("target"),
        "horizon": report.get("horizon"),
        "corpus_seal": report.get("corpus_seal"),
        "protocol_digest": report.get("protocol_digest"),
        "sealed_rows": report.get("sealed_row_count"),
        "sealed_at": report.get("sealed_at"),
        "label_provenance": report.get("label_provenance"),
        "label_source": report.get("label_source"),
        "report_sha256": report_sha256,
        "computed_by": ("M5PHET/evaluation, not this package; this package scored nothing and its "
                        "provenance.quality stays UNMEASURED"),
        "conditions": ("this error is the value measured on the sealed population named above and on no other rows. "
                       "It is not a guarantee for other rows, other weeks or other households, and it says nothing "
                       "about whether those rows were used to choose this model -- read the round that produced them"),
    }


def fitted_custom_objects():
    """Loader-side implementations of the custom layers predictor's model plugins write into a saved graph.

    A graph whose branch reads a SUBSET of the input columns carries a gather layer, and a saved layer is only as
    loadable as the code that can rebuild it. Two ways were available and only one of them is honest:

    * import predictor's plugin package here -- which would make a *servable* bundle of this package depend, at load
      time, on the repository that trained it, and on that repository's TensorFlow-Probability stack;
    * rebuild the layer from the configuration THE FILE CARRIES. The gather's channel indices are in its own config
      (``indices``), written there by the fitting plugin, so nothing is re-derived from the column names -- a
      re-derivation would look exactly like the original and could gather other columns.

    This is the second. It reads, it does not infer. A graph saved before predictor made that layer serialisable (a
    bare ``Lambda`` over a closure) cannot be loaded by anybody, including the process that saved it, and is refused
    here with the loader's own message rather than repaired by a guess.
    """
    import keras

    @keras.saving.register_keras_serializable(package="prediction_provider_forecast.loader")
    class GatherColumns(keras.layers.Layer):
        def __init__(self, indices, **kwargs):
            super().__init__(**kwargs)
            self.indices = tuple(int(index) for index in indices)

        def call(self, tensor):
            import tensorflow as tf_local
            return tf_local.gather(tensor, tf_local.constant(self.indices, dtype=tf_local.int32), axis=-1)

        def compute_output_shape(self, input_shape):
            return tuple(input_shape[:-1]) + (len(self.indices),)

        def get_config(self):
            config = super().get_config()
            config["indices"] = list(self.indices)
            return config

    return {"predictor_plugins.fused_branches>GatherColumns": GatherColumns, "GatherColumns": GatherColumns}


def export_fitted_forecast(fit_root, destination, *, state_id=None, title=None):
    """Export one graph fitted by `tools/fit_pipeline_spec.py` as a servable v2 bundle. Never trains, never scores."""
    return _staged(destination, lambda staging: _export_fitted_forecast(fit_root, staging, state_id, title))


def _fitted_history_window(fit, columns):
    """The FIRST window of the training file, standardised with the bundle's own scaler. No label column is read.

    The parity population is deliberately a TRAIN window: the sealed holdout is what the model is judged on, and reading
    one of its rows here -- even as input, even without its label -- would put the export inside the evaluation.
    """
    path = Path(fit["data"]["path"])
    window = int(fit["window"])
    with path.open(newline="") as stream:
        reader = csv.reader(stream)
        header = next(reader)
        if len(set(header)) != len(header):
            raise ValueError(f"{path.name} has duplicate column names; the feature order cannot be resolved")
        wanted = set(columns)
        if [c for c in header if c in wanted] != list(columns):
            raise ValueError("the run manifest's feature order does not match the training file's column order")
        index = {name: position for position, name in enumerate(header)}
        rows = []
        for raw in reader:
            rows.append([float(raw[index[c]]) for c in columns])
            if len(rows) == window:
                break
    if len(rows) < window:
        raise ValueError(f"{path.name} has fewer than {window} rows; no history window can be taken")
    raw = np.asarray(rows, dtype=np.float64)
    mean = np.asarray(fit["scaler"]["mean"], dtype=np.float64)
    sd = np.asarray(fit["scaler"]["sd"], dtype=np.float64)
    x = ((raw - mean) / sd).astype(np.float32)[None, :, :]
    if not np.isfinite(x).all():
        raise ValueError("the first training history window contains non-finite values")
    return x


def _export_fitted_forecast(fit_root, destination, state_id, title):
    root = Path(fit_root).resolve()
    out = Path(destination).resolve()
    manifest_path = root / "fitted" / "fit_manifest.json"
    model_path = root / "fitted" / "model.keras"
    report_path = root / "report.json"
    for path in (manifest_path, model_path, report_path):
        if not path.is_file():
            raise FileNotFoundError(f"missing fitted artifact: {path}")
    fit = json.loads(manifest_path.read_text())
    if fit.get("schema") != FITTED_SCHEMA:
        raise ValueError(f"{manifest_path.name}: schema {fit.get('schema')!r} is not {FITTED_SCHEMA!r}")
    for key in ("stage", "fitted_at", "config", "columns", "target", "horizons", "window", "step_seconds",
                "scaler", "data", "population", "training", "plugin_module", "head"):
        if key not in fit:
            raise ValueError(f"{manifest_path.name} does not declare {key}; it is not an exportable run manifest")
    columns = list(fit["columns"])
    target = fit["target"]
    horizons = [int(h) for h in fit["horizons"]]
    window = int(fit["window"])
    head = fit["head"]
    if head not in ("point", "quantile"):
        raise ValueError(f"unsupported fitted head {head!r}")
    quantiles = [float(q) for q in (fit.get("quantiles") or ())] if head == "quantile" else []
    if head == "quantile" and (len(quantiles) < 2 or 0.5 not in quantiles):
        raise ValueError("a quantile head is exported only with at least two quantiles including the median")
    if target not in columns or len(horizons) != 1:
        raise ValueError("only a single-horizon graph whose target is one of its input columns is exported")
    scaler_mean, scaler_sd = fit["scaler"]["mean"], fit["scaler"]["sd"]
    if (len(scaler_mean) != len(columns) or len(scaler_sd) != len(columns)
            or any(not math.isfinite(v) for v in scaler_mean) or any(v <= 0 for v in scaler_sd)):
        raise ValueError("the run manifest's scaler does not cover every input column with a positive spread")
    report = json.loads(report_path.read_text())
    if report.get("corpus_seal") != fit["population"]["seal"]:
        raise ValueError("the evaluation report beside this fit was computed against another corpus seal")

    hashes = {"model": file_digest(model_path), "fit_manifest": file_digest(manifest_path),
              "report": file_digest(report_path)}
    tf = cpu_tensorflow()
    import keras
    model = keras.saving.load_model(str(model_path), compile=False, custom_objects=fitted_custom_objects())
    width = len(horizons) * (len(quantiles) or 1)
    if tuple(model.input_shape) != (None, window, len(columns)):
        raise ValueError(f"the saved graph expects {model.input_shape}, not the window this run manifest describes")
    if tuple(model.output_shape) != (None, width):
        raise ValueError(f"the saved graph emits {model.output_shape}, not the {width} value(s) this manifest declares")
    x = _fitted_history_window(fit, columns)
    with tf.device("/CPU:0"):
        expected = np.asarray(model.predict_on_batch(x))
        if expected.shape != (1, width) or not np.isfinite(expected).all():
            raise ValueError("the fitted model did not produce a finite output of the declared width")
        if quantiles and (np.diff(expected.reshape(len(horizons), len(quantiles)), axis=1) < 0).any():
            raise ValueError("the fitted quantiles cross on the parity window; the pair would not be an interval")
        j = columns.index(target)
        expected_values = expected * float(scaler_sd[j]) + float(scaler_mean[j])

        class NativeGraph(tf.Module):
            def __init__(self):
                super().__init__()
                self.model = model

            @tf.function(input_signature=[tf.TensorSpec((1, window, len(columns)), tf.float32, name="x")])
            def forecast(self, x):
                return {"forecast": self.model(x, training=False)}

        graph = NativeGraph()
        out.mkdir(parents=True)
        tf.saved_model.save(graph, str(out / "saved_model"), signatures={"serving_default": graph.forecast})
    files = {p.relative_to(out).as_posix(): file_digest(p)
             for p in sorted((out / "saved_model").rglob("*")) if p.is_file()}

    scaler = {"kind": "per_column_zscore", "mean": list(scaler_mean), "sd": list(scaler_sd),
              "fitted_on": fit["scaler"]["fitted_on"]}
    name = state_id or f"{fit['stage'].replace('_', '-')}-{Path(fit['data']['path']).stem.replace('_', '-')}"
    step = int(fit["step_seconds"])
    minutes = step == 60
    # WP06: which designed representation produced this bundle. It is copied from the run manifest, where the fitting
    # tool wrote the representation BY VALUE; a run manifest that carried only a path to the spec file records nothing
    # here, because a path is not an answer -- the file may have changed, or may not exist on the host that reads this.
    representation = (fit["spec"] or {}).get("representation")
    if not isinstance(representation, dict) or not str(representation.get("schema") or "").strip():
        representation = REPRESENTATION_NOT_RECORDED
    manifest = {
        "schema": SCHEMA_V2, "engine": "tensorflow_saved_model",
        "exposure": FITTED_EXPOSURE,
        "representation_spec": representation,
        # WP27: the held-out error the evaluation package measured for THIS graph, quoted with its seal, its protocol
        # and the digest of the report it came from. `provenance.quality` stays UNMEASURED: this package computed none
        # of it, and the distinction between "measured elsewhere, quoted here with its conditions" and "measured here"
        # is the whole point.
        "measured_error": measured_error_from_report(report, report_sha256=hashes["report"]),
        "state_id": name, "task_id": f"predictor.{name}.W{window}_h{horizons[0]}",
        "title": title or (f"DEVELOPMENT: {fit['stage']} household forecast, "
                           f"{'quantile' if quantiles else 'point'} head at {horizons[0]} steps"),
        "family": COMBINATION["family"],
        "heads": ["quantile"] if quantiles else ["point"],
        "columns": columns, "targets": [target], "horizons": horizons,
        "window": window, "step_seconds": step,
        "unit": "kW", "scale": "original",
        "readout": "target_scaler_inverse", "input_scale": "train_standardized",
        "horizon_meaning": (f"the realised value of {target} exactly {horizons[0]} rows ({horizons[0] * step} s) after "
                            f"the last row of the window, which is what the fit was trained against"),
        "aliases": {target: ["household power", "active power", "power consumption", "consumption",
                             "potencia", "consumo"]},
        "horizon_aliases": {str(horizons[0]): (["one hour", "an hour", "next hour", "una hora", "la proxima hora",
                                                "próxima hora"] if minutes and horizons[0] == 60 else [])},
        "scaler": scaler, "scaler_digest": digest(scaler), "files": files,
        "provenance": {
            "trained_on": (f"{Path(fit['data']['path']).name}, rows 0..{fit['data']['holdout_start_row']} (TRAIN only); "
                           f"the holdout was sealed as {fit['population']['seal']} before the fit"),
            "trained_by": (f"predictor tools/fit_pipeline_spec.py, stage {fit['stage']}, plugin "
                           f"{fit['plugin_module']}, spec {Path(fit['spec']['path']).name}"),
            "trained_at": fit["fitted_at"],
            # this package scores nothing; the numbers measured on that seal live in the evaluation report named below
            "quality": UNMEASURED,
            "quality_note": ("this export neither trained nor scored anything. The fit was measured by "
                             "M5PHET/evaluation under protocol "
                             f"{fit['population']['protocol_digest']} against corpus seal "
                             f"{fit['population']['seal']} ({fit['population']['sealed_rows']} rows); that report is "
                             "the only place those numbers may be quoted from, with its conditions"),
            "artifact_hashes": hashes,
            "evaluation": {"protocol_digest": fit["population"]["protocol_digest"],
                           "corpus_seal": fit["population"]["seal"],
                           "sealed_rows": fit["population"]["sealed_rows"],
                           "sealed_at": fit["population"]["sealed_at"],
                           "report_sha256": hashes["report"]},
            # the REFERENCE to the spec file the fit read: its path, its digest, its decision records. The
            # representation itself is the top-level `representation_spec`; this says where it came from.
            "representation_spec_ref": fit["spec"],
            "preprocessing": fit["preprocessing"],
            "training": fit["training"],
            "keras": keras.__version__, "tensorflow": tf.__version__, "numpy": np.__version__,
            "parity_population": "the first TRAIN history window of the training file; no label was read",
            "origin_row_in_train_file": window - 1,
        },
    }
    if quantiles:
        manifest["quantiles"] = quantiles
    _write(out / "manifest.json", manifest)

    provider = ForecastProvider(out)
    data = {"columns": columns, "values": x[0].tolist(), "scale": manifest["input_scale"],
            "scaler_digest": manifest["scaler_digest"]}
    request = provider.chat_request(f"forecast {target} at {horizons[0]} steps", data,
                                    {"provider": provider.name, "family": manifest["family"],
                                     "output_kind": "point_forecast", "input": "json",
                                     "as_of": datetime.now(timezone.utc).isoformat(),
                                     "state": provider.known_states()[0],
                                     "parameters": {"request_id": "fitted-bundle-example"}})
    state = provider.load(request["fitted_state_ref"])
    answer = provider.infer(request, state)
    payload = answer["outputs"][target]["payload"]
    actual = payload["quantile_values"] if quantiles else payload["values"]
    np.testing.assert_allclose(np.asarray(actual).reshape(1, width), expected_values, rtol=1e-6, atol=1e-6)
    if hashes != {"model": file_digest(model_path), "fit_manifest": file_digest(manifest_path),
                  "report": file_digest(report_path)}:
        raise ValueError("the fitted artifacts changed during export")
    _write(out / "example_request.json", request)
    example = provider.chat_examples()[0]
    _write(out / "example_data.json", example["data"])
    _write(out / "example_config.json", example["config"])
    _write(out / "parity.json", {"native_values": expected_values.tolist(),
                                 "provider_values": np.asarray(actual).reshape(1, width).tolist(),
                                 "rtol": 1e-6, "atol": 1e-6,
                                 "max_absolute_error": float(np.max(np.abs(
                                     np.asarray(actual).reshape(1, width) - expected_values))),
                                 "state_digest": state["digest"], "model_sha256": state["model_sha256"],
                                 "input_sha256": digest(data), "population": "TRAIN history only",
                                 "no_training": True, "no_heldout_scoring": True, "device": "CPU"})
    return {"bundle": str(out), "state_ref": state["state_ref"], "native_parity": "PASS"}
