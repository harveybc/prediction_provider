# Native Forecast Provider

This independently installable package supplies `predictor_forecast` through
`m5phet.providers`. It serves **exported, retained predictor checkpoints** — not a
replacement model, oracle, cached label, random-weight demo or implicit training
job. Serving uses the exported native TensorFlow graph. No root-service
dependencies or M5PHET edits are required.

Two bundles are exported today, and `M5PHET_FORECAST_BUNDLE` may point at either
one bundle or a directory holding several:

| Bundle | Model | Target | Horizon | Unit |
| --- | --- | --- | --- | --- |
| `forecast-household-dev-20260924` | retained **DEVELOPMENT** E1 household-power `R0_s1` TCN | `Global_active_power` | 60 steps (60 s each) | kW |
| `forecast-predictor-direction-dev-20260924` | predictor's committed `direction_cnn` champion from `examples/results/phase_1c_direction/` | `direction_long` | 1 step | probability |

Neither has a measured quality here. Every bundle states what it was trained on,
by whom and when, and says `"quality": "UNMEASURED"`; a bundle that cannot say
those things is refused at construction rather than served.

## Install and Run

Use a separate Python 3.12 environment. Base installation is discovery-light
(NumPy only); TensorFlow is imported only when a fitted model is loaded. A CPU
process is mandatory; the provider hides GPUs and places inference on CPU.

```bash
python3.12 -m venv /tmp/forecast-env
/tmp/forecast-env/bin/pip install -e '/path/to/prediction_provider/forecast[native,test]'
```

For a shared CPU-local M5PHET environment that **already has** TensorFlow 2.21:

```bash
/path/to/cpu-env/bin/pip install --no-deps -e /path/to/prediction_provider/forecast
export CUDA_VISIBLE_DEVICES=""
export M5PHET_FORECAST_BUNDLE=/path/to/exported-dev-bundle
```

If the web environment does not have TensorFlow, keep its dependencies unchanged
and set `M5PHET_FORECAST_PYTHON=/absolute/path/to/native-env/bin/python`. Install
this package plus its native extra in that separate environment. The operator
sets this variable, not a chat request. Load and infer use bounded CPU subprocesses
(60-second timeout each, no shell), passing the typed request over stdin. The host
never imports TensorFlow. Each invocation reloads the model, trading a few seconds
of startup for dependency isolation; no persistent service is started. Configure
these environment variables before starting the M5PHET web process.

### Persistent Local Deployment

The verified native interpreter is now
`$HOME/.local/share/m5phet/forecast-native-venv/bin/python`. It has a non-editable
provider installation and preserves all 37 working dependency versions,
including TensorFlow 2.21.0, Keras 3.15.0 and NumPy 2.5.1. Like the original
environment, it inherits dependencies from the existing persistent native Conda
base; retain that base without upgrades for exact replay. Nothing required by
this native environment is located in `/tmp`.

For the existing `$HOME/.local/share/m5phet/chat-venv` web deployment, set these
in the operator's persistent launcher/service environment before starting it:

```bash
export CUDA_VISIBLE_DEVICES=""
export M5PHET_FORECAST_PYTHON="$HOME/.local/share/m5phet/forecast-native-venv/bin/python"
# one bundle, exactly as before …
export M5PHET_FORECAST_BUNDLE="$HOME/.local/state/m5phet/forecast-household-dev-20260924"
# … or a directory holding several, which serves all of them
export M5PHET_FORECAST_BUNDLE="$HOME/.local/state/m5phet/forecast-bundles-20260924"
```

The retained household bundle and its state reference are unchanged; no export or
training is needed. A fresh stable-chat/stable-native subprocess replay matches the
recorded native forecast exactly: 0.5412255525588989 kW, including when it is
served from inside a directory of bundles. The direction bundle replays at
0.6035091876983643 (probability).

The multi-bundle directory on this machine holds symlinks to the two bundles
above, so each bundle keeps the path its evidence was recorded against:

```bash
R="$HOME/.local/state/m5phet/forecast-bundles-20260924"
mkdir -p "$R"
ln -sfn "$HOME/.local/state/m5phet/forecast-household-dev-20260924"        "$R/household-dev"
ln -sfn "$HOME/.local/state/m5phet/forecast-predictor-direction-dev-20260924" "$R/predictor-direction-dev"
```

After changing this package's source, reinstall it into every environment that
holds a non-editable copy — the native interpreter above, and the web
environment's `chat-venv` — or the running deployment keeps serving the old code:

```bash
"$HOME/.local/share/m5phet/forecast-native-venv/bin/pip" \
  install --no-deps --no-build-isolation --no-index /path/to/prediction_provider/forecast
```

Export is an explicit, offline one-time operation before starting chat. The
source root is trusted executable owner code, never an untrusted upload. The
run root is the existing `e1_household_successor_v3` directory. This requires
its `DATA.npz`, `DATA.json`, and `attempts/R0_s1/{job.json,cell.json,weights.weights.h5}`.
Missing or mismatched artifacts cause refusal, never a fallback model.

```bash
/tmp/forecast-env/bin/pip install -e '/path/to/prediction_provider/forecast[export]'
CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 /tmp/forecast-env/bin/m5phet-forecast export-dev \
  --predictor-root /path/to/predictor \
  --run-root "$HOME/.local/state/crispdm-data-foundation/e1_household_successor_v3" \
  --out /tmp/household-dev-bundle

CUDA_VISIBLE_DEVICES="" /tmp/forecast-env/bin/m5phet-forecast infer \
  --bundle /tmp/household-dev-bundle \
  --request /tmp/household-dev-bundle/example_request.json
```

## Exporting a predictor Example Checkpoint

predictor also ships trained example checkpoints under `examples/results/`,
committed beside the configuration and the data that produced them. One command
exports one of them; nothing is trained and no held-out data is read:

```bash
CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 PREDICTOR_QUIET=1 \
  "$HOME/.local/share/m5phet/forecast-native-venv/bin/m5phet-forecast" \
  export-predictor-example \
  --predictor-root /path/to/predictor \
  --inference-config examples/config/phase_1c_direction/inference/phase_1c_direction_cnn_direction_long_1d_inference_config.json \
  --out "$HOME/.local/state/m5phet/forecast-predictor-direction-dev-20260924"
```

The inference config is the only argument that varies: the exporter reads
`load_model`, `x_train_file`, `use_normalization_json`, `window_size`,
`predicted_horizons`, `add_window_stats` and `signal_type` from it, and the
feature order from the `*_model_metadata.json` saved beside the weights. The
example window is the first **train** window of `x_train_file`; no label column,
validation row or test row is read. Derived channels are appended by calling
predictor's own `preprocessor_plugins/stl_preprocessor.py`, whose hash is recorded —
the recipe is never reimplemented here, because a fork of it would keep working
after predictor changed and feed the graph channels it was never trained on.

Export refuses, rather than substituting anything, when: the model, metadata,
config, training CSV or normalization JSON is **uncommitted or modified** in the
predictor checkout (an artifact with no attributable author or date); the metadata
feature order disagrees with the CSV's column order; a label column appears among
the features; the head is not a single sigmoid unit while the bundle would publish
a probability; or the training file has no dominant time step.

Attribution comes from `git log` on the weights file, so the bundle's
`trained_by` / `trained_at` are the repository's answer, not anyone's memory.
`predictor` is only ever read: git is invoked with `--no-optional-locks`.

## Several Bundles at Once

`M5PHET_FORECAST_BUNDLE` accepts either one bundle directory (unchanged) or a
directory whose immediate subdirectories are bundles. Then:

- `known_states()` lists every bundle, in directory-name order.
- `capabilities()` declares the union: one `supported` entry per distinct
  operation/family/output_kind, every family, and a `bundles` list giving each
  fitted state's own targets, horizons, unit, scale, window and step. The
  singular `output_schema` is `null` when more than one bundle is configured,
  because no single contract can stand for two.
- `chat_slots()` declares the union of targets and horizons, each with its own
  bundle's aliases. A column that is an input somewhere and a target nowhere is
  listed under `known_unsupported`, so naming it is refused before any
  interpreter is consulted.
- A request naming a target and horizon resolves to the **one** bundle that has
  them. If two bundles share that pair the request is refused with **both**
  fitted states named; it is never resolved by picking the first. If the words
  resolve to one bundle and the config names another, that is refused too.
- A bundle that fails to validate refuses the **whole** provider. Serving the
  rest would report a shorter list as if it were the complete one.

Every bundle must carry provenance. A v2 manifest needs `trained_on`,
`trained_by`, `trained_at` and `quality`, and `quality` must be `UNMEASURED`:
this package never scores a model, so it cannot publish a quality number it did
not compute. A bundle whose provenance is missing or empty is refused.

`exposure` says what a bundle can honestly claim about held-out data.
`DEV_ONLY_NO_TEST_ACCESS` is a receipt a governed run wrote and the exporter
checked; predictor's committed examples have none, so they say
`PREDICTOR_EXAMPLE_NO_EXPOSURE_RECEIPT` instead of borrowing the stronger wording.

The household bundle keeps schema `prediction_provider.forecast_bundle.v1` and is
validated exactly as it always was. Its manifest bytes are load-bearing — the
state reference, `parity.json` and `example_request.json` all quote their digest —
so it is never rewritten to fit a widened contract. Everything new is
`…forecast_bundle.v2`, which additionally declares `state_id`, `family`, `title`,
`readout` (`target_scaler_inverse` or `identity`), `input_scale`,
`horizon_meaning`, and optional `aliases` / `horizon_aliases`.

`horizon_meaning` is required because a step is not self-explanatory outside a
fixed-grid regression: the direction bundle's `step_seconds` is the 4-hour spacing
of its input grid, and its label's look-ahead is defined by predictor's target
plugin and is **not** restated or verified here.

The smallest authentic input for the household bundle is 60 rows x 7 features, one
chronological history window, ending at its forecast origin. Export reads the first DEV **train**
origin and its standardized `Xs` history, not future labels, validation origins,
test data or saved predictions. It builds the original
`tools/df_e1_pilot.py::_model_for_target`, restores the actual weights, verifies
the detector digest against the trained receipt, and compares native
`predict_on_batch` against exported-graph/provider output. No fitting or scoring
is called. The bundle is published only after parity passes. Source artifact
hashes and four native source-module hashes are recorded without local paths.

## Registry and Chat

`ForecastProvider(bundle=None)` reads `M5PHET_FORECAST_BUNDLE` when no path is
given, and accepts either one bundle or a directory of them. `capabilities()`
declares only tested combinations -- one `supported` entry per configured
bundle's `infer / <family> / point_forecast` -- plus
`uncertainty_methods=["none"]` and the configured `known_states`.
`known_states()` returns that same list. With no bundle configured, discovery
works but the state list and examples are empty.
`load(state_ref)` checks hashes and returns a deepcopy-safe metadata dictionary;
`infer(request, state)` checks task, shape, scale, population and state identity.

`chat_request(prompt, data, config)` returns a full `m5phet.task.draft2` request.
Grammar is case-sensitive, exact, bounded to 512 characters, and one form is
accepted per configured bundle:

```text
forecast Global_active_power at 60 steps
forecast direction_long at 1 steps
```

`chat_request(..., parameters={"target": ..., "horizon": ...})` takes the values
the workbench resolved from ordinary phrasing through `chat_slots()`; they are
checked against the configured bundles exactly as the canonical prompt is.

No conversational guessing, synonyms, extrapolated horizons or external model.
`config` requires `provider`, `family`, `output_kind`, `state`, `as_of`, and
`parameters`. `input` must be `json` if present. `parameters` is `{}` or contains
only `request_id`. Shared web fields `presentation`, `context`, `asset`,
`language`, `max_age_seconds`, `options` are tolerated as transport metadata;
they do not change the forecast. The data argument must be the parsed object,
not a filename or attachment list. An aware ISO `as_of` is required.

`chat_examples()` returns one `{title,prompt,data,config}` entry per configured
bundle, labelled DEVELOPMENT, read from what export explicitly wrote, without
loading TensorFlow. A bundle that shipped no `example_request.json` contributes
no example; none is invented.
Its config uses `input:'json'`, the provider/family/output_kind above, the actual
state reference, `as_of` and `parameters:{}`. Export also writes those objects
to `example_data.json` and `example_config.json` for the CLI:

```bash
/tmp/forecast-env/bin/m5phet-forecast chat-request \
  --bundle /tmp/household-dev-bundle \
  --prompt 'forecast Global_active_power at 60 steps' \
  --data /tmp/household-dev-bundle/example_data.json \
  --config /tmp/household-dev-bundle/example_config.json
```

## Exact Payload

Request `output_schema`:

```json
{"targets":["Global_active_power"],"horizons":[60],"unit":"kW","scale":"original"}
```

Provider result (value shown is from the verified retained DEV example):

```json
{"outputs":{"Global_active_power":{"status":"OK","uncertainty":"none","payload":{
  "targets":["Global_active_power"],"horizons":[60],"values":[[0.5412255525588989]],
  "unit":"kW","scale":"original"
}}},"population":{"input_sha256":"<digest of the exact data object>"}}
```

`values[i][j]` is the scalar forecast for `targets[i]` at `horizons[j]`.
Horizons are positive integer **steps**; a bundle's `step_seconds` gives the
spacing of its own input grid (60 s for the household bundle, 14 400 s for the
direction bundle) and its `horizon_meaning` says what one step means for its
task. Each bundle serves exactly one target. Output IDs are the target name --
`Global_active_power`, `direction_long` -- never the generic word `forecast`.
No batch axis. Values must be finite JSON numbers, never booleans.

Input `data` has exactly `columns`, `values`, `scale` and `scaler_digest`. The
scale is the bundle's own `input_scale` (`train_standardized` for the household
bundle, `predictor_normalized` for the direction bundle) and the digest must be
that bundle's `scaler_digest`. For the household bundle `values` is `[60][7]`,
ordered oldest to newest. Feature order:
`Global_reactive_power, Voltage, Global_intensity, Sub_metering_1, Sub_metering_2,
Sub_metering_3, Global_active_power`. The manifest carries frozen train-only
means/standard deviations. New raw data must be transformed with those exact
statistics externally; the provider never fits a scaler or infers feature order.

`as_of` is the invocation/replay clock, **not** an invented event timestamp for
the historical window. This demo has row-index history and assumes the supplied
rows are a contiguous 60-second grid. It makes no freshness, event-availability,
governance, calibration, generalization, or application-eligibility claim.
Never use this input contract as a causal/availability certificate. No trades.

## Verification

```bash
CUDA_VISIBLE_DEVICES="" M5PHET_FORECAST_TEST_BUNDLE=/tmp/household-dev-bundle \
  /tmp/forecast-env/bin/python -m pytest -q /path/to/prediction_provider/forecast/tests
```

The multi-bundle rules are tested against METADATA FIXTURES -- manifests with no
native graph behind them -- because every one of them is settled before a model
is loaded, and fabricating a checkpoint to test a refusal would put untrained
weights behind something that looks like a real bundle. One test does use the
real household bundle inside a directory of bundles, and checks that it still
answers 0.5412255525588989.

Real-artifact tests skip when their bundle is not supplied; they never fabricate
a checkpoint. `parity.json` records source-native and adapter numbers, tolerance,
input/state/model hashes and the CPU/DEV-only scope. Runtime validation of
`point_forecast` belongs to M5PHET; versions lacking that validator correctly
refuse the task even though direct provider inference works.

SavedModel bundles are **trusted local executable artifacts**. Hashes detect
changes, not malicious graphs or forged training receipts. Never configure a
bundle uploaded by an untrusted chat client. Export requires TF 2.21 (matching
the exercised native environment); serving does not install the predictor app.
