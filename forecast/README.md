# Native Forecast Provider

This independently installable package supplies `predictor_forecast` through
`m5phet.providers`. It serves the retained **DEVELOPMENT** E1 household-power
`R0_s1` checkpoint from predictor, not a replacement model, oracle, cached label,
random-weight demo or implicit training job. Serving uses the exported native
TensorFlow graph. No root-service dependencies or M5PHET edits are required.

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
export M5PHET_FORECAST_BUNDLE="$HOME/.local/state/m5phet/forecast-household-dev-20260924"
```

The retained bundle and its state reference are unchanged; no export or training
is needed. A fresh stable-chat/stable-native subprocess replay matches the
recorded native forecast exactly: 0.5412255525588989 kW.

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

The smallest authentic input is 60 rows x 7 features, one chronological history
window, ending at its forecast origin. Export reads the first DEV **train**
origin and its standardized `Xs` history, not future labels, validation origins,
test data or saved predictions. It builds the original
`tools/df_e1_pilot.py::_model_for_target`, restores the actual weights, verifies
the detector digest against the trained receipt, and compares native
`predict_on_batch` against exported-graph/provider output. No fitting or scoring
is called. The bundle is published only after parity passes. Source artifact
hashes and four native source-module hashes are recorded without local paths.

## Registry and Chat

`ForecastProvider(bundle=None)` reads `M5PHET_FORECAST_BUNDLE` when no path is
given. `capabilities()` declares only the tested combination
`infer / regression_forecasting / point_forecast`, `uncertainty_methods=["none"]`
and configured `known_states`. `known_states()` also returns that list. With no
bundle configured, discovery works but the state list and examples are empty.
`load(state_ref)` checks hashes and returns a deepcopy-safe metadata dictionary;
`infer(request, state)` checks task, shape, scale, population and state identity.

`chat_request(prompt, data, config)` returns a full `m5phet.task.draft2` request.
Grammar is case-sensitive, exact, bounded to 512 characters:

```text
forecast Global_active_power at 60 steps
```

No conversational guessing, synonyms, extrapolated horizons or external model.
`config` requires `provider`, `family`, `output_kind`, `state`, `as_of`, and
`parameters`. `input` must be `json` if present. `parameters` is `{}` or contains
only `request_id`. Shared web fields `presentation`, `context`, `asset`,
`language`, `max_age_seconds`, `options` are tolerated as transport metadata;
they do not change the forecast. The data argument must be the parsed object,
not a filename or attachment list. An aware ISO `as_of` is required.

`chat_examples()` returns one `{title,prompt,data,config}` entry labelled
DEVELOPMENT from the explicitly exported bundle, without loading TensorFlow.
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
Horizons are positive integer **steps**, each 60 seconds, relative to the last
input row. The native slice supports one target and horizon `[60]` only.
Output IDs are `Global_active_power`, not the generic word `forecast`.
No batch axis. Values must be finite JSON numbers, never booleans.

Input `data` has exactly `columns`, `values`, `scale:'train_standardized'` and
`scaler_digest`. `values` is `[60][7]`, ordered oldest to newest. Feature order:
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

Real-artifact tests skip when their bundle is not supplied; they never fabricate
a checkpoint. `parity.json` records source-native and adapter numbers, tolerance,
input/state/model hashes and the CPU/DEV-only scope. Runtime validation of
`point_forecast` belongs to M5PHET; versions lacking that validator correctly
refuse the task even though direct provider inference works.

SavedModel bundles are **trusted local executable artifacts**. Hashes detect
changes, not malicious graphs or forged training receipts. Never configure a
bundle uploaded by an untrusted chat client. Export requires TF 2.21 (matching
the exercised native environment); serving does not install the predictor app.
