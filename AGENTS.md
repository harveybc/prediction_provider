# AGENTS.md — prediction_provider

Guidance for coding agents working in this repository. Follows the
[agents.md](https://agents.md) convention.

## Project overview

`prediction_provider` is a plugin-based FastAPI service that serves financial
time-series predictions over HTTP. It loads a core plugin, an endpoints plugin,
a feeder, a pipeline and a predictor from setuptools entry points, then exposes
prediction, health, model-info and metrics endpoints backed by SQLAlchemy
persistence and multi-role authentication.

It does **not** train models — trained artifacts are produced elsewhere and
loaded here for inference. It does **not** execute orders or connect to any
trading venue; `lts` consumes this API and owns execution. It does **not** run
backtests; `heuristic-strategy` calls this API per tick from its own backtests.
The service moves no capital and its consumers run in simulation and
paper/demo venues only.

## Agent quickstart (install → run → show the user results)

Everything below is offline. No network calls, no venue connectivity, no
trained-model artifact required — the example uses an oracle predictor that
reads a committed CSV.

### 1. Environment

```bash
cd /path/to/prediction_provider
python -m venv .venv && source .venv/bin/activate   # or use an existing env
pip install -e .
pip install yfinance
```

`yfinance` is **required to boot the service at all**, even for configurations
that never fetch market data: `plugins_feeder/__init__.py` imports
`real_feeder` → `data_fetcher`, which does an unguarded `import yfinance`, and
`app/main.py` exits with status 1 if any of the five plugins fails to load. It
is listed in `requirements.txt` but not in `setup.py`'s `install_requires`.

Prefer a dedicated virtual environment. This package installs a top-level
package literally named `app`, and its entry-point group names
(`feeder.plugins`, `pipeline.plugins`, `predictor.plugins`, …) are unqualified
and shared with sibling projects — see *Conventions and constraints* below.

### 2. Smoke test

```bash
python app/main.py --help                    # exits 0, prints the CLI reference
PYTHONPATH=. python -m pytest -q tests/unit_tests \
  --ignore=tests/unit_tests/test_feeder_plugins.py \
  --ignore=tests/unit_tests/test_unit_feeder.py
```

Verified: `--help` exits 0; the unit subset reports `40 passed`. The two
ignored files exercise the `yfinance`-backed feeder and need real network
mocking to be meaningful.

### 3. Representative safe run — serve an oracle predictor

Start the service from the repository root, bound to loopback, pointed at a
committed fixture CSV:

```bash
PYTHONPATH=. python app/main.py \
  --load_config examples/config/direction_ideal_oracle.json \
  --csv_file examples/data/phase_1c_direction_test_ohlc.csv \
  --host 127.0.0.1 --port 8000
```

Why this config is safe: it selects `core_plugin: sync_core` and
`predictor_plugin: direction_ideal_oracle`. That predictor is a pure
pandas/numpy look-ahead oracle over an OHLC CSV
(`plugins_predictor/direction_ideal_oracle.py`) — it imports no TensorFlow, needs
no model artifact and touches no network. The two CLI overrides matter:

- `--csv_file` — the committed config points at a path in a **sibling**
  repository (`heuristic-strategy`); the override redirects it to this repo's
  own fixture, `examples/data/phase_1c_direction_test_ohlc.csv` (8 682 hourly
  EURUSD bars, columns `DATE_TIME,OPEN,HIGH,LOW,CLOSE`).
- `--host 127.0.0.1` — the committed config sets `0.0.0.0`, which binds every
  interface. Keep it on loopback.

Unknown CLI flags are merged into the config by
`app/config_merger.process_unknown_args`, which is why `--csv_file` works even
though it is not declared in `app/cli.py`.

### 4. Verify it is serving

```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/api/v1/model/info
curl -s -X POST http://127.0.0.1:8000/api/v1/predict/entry \
  -H 'Content-Type: application/json' \
  -d '{"datetime":"03.12.2018 08:00:00.000","tp":50,"sl":25}'
```

Verified responses:

```json
{"status":"ok"}
{"model_name":"direction_ideal_oracle","window_size":256,"supported_types":["entry","exit"],
 "entry_directions":["buy","sell"],"exit_directions":["buy","sell"],
 "prediction_scope":"path_scanning","required_columns":["OPEN","HIGH","LOW","CLOSE"],
 "accepts_ohlc_window":false}
{"buy_entry_binary":0,"sell_entry_binary":1,"bars_remaining":2,
 "buy_confidence":1.0,"sell_confidence":1.0}
```

Request timestamps use `DD.MM.YYYY HH:MM:SS.000` (parsed in
`plugins_core/sync_core.py`), while the CSV uses `YYYY-MM-DD HH:MM:SS`. Pick a
timestamp inside the fixture's range (2018-12-02 22:00 onwards).

### 5. Interactive API browser

The FastAPI app declares no custom `docs_url`, so the interactive docs are at
the default paths. Verified: `/docs`, `/redoc` and `/openapi.json` all return
`200`, and the schema enumerates 50+ routes including `/api/v1/predict`,
`/api/v1/predict/entry`, `/api/v1/predict/exit`, `/api/v1/model/info`,
`/api/v1/plugins/` and `/api/v1/plugins/status`.

- Swagger UI: <http://127.0.0.1:8000/docs>
- ReDoc: <http://127.0.0.1:8000/redoc>
- Raw schema: <http://127.0.0.1:8000/openapi.json>

Stop the server with Ctrl-C when finished.

### 6. Final message to the user

Report exactly this:

> The prediction service is running locally.
>
> - Interactive API docs (Swagger UI): **http://127.0.0.1:8000/docs**
> - ReDoc: http://127.0.0.1:8000/redoc — raw schema: http://127.0.0.1:8000/openapi.json
> - It is serving the `direction_ideal_oracle` predictor over the committed
>   fixture `examples/data/phase_1c_direction_test_ohlc.csv`. No trained model
>   artifact and no network access are involved.
> - Unit-test output: `40 passed` from `tests/unit_tests` (feeder tests
>   excluded — they need `yfinance`).
> - Prediction rows are persisted to `./prediction_provider.db` relative to the
>   directory you started the server in.
>
> **One request to try first** — ask the oracle whether a buy or a sell would
> have paid off at a given bar:
>
> ```bash
> curl -s -X POST http://127.0.0.1:8000/api/v1/predict/entry \
>   -H 'Content-Type: application/json' \
>   -d '{"datetime":"03.12.2018 08:00:00.000","tp":50,"sl":25}'
> ```
>
> Then sweep `tp`/`sl` (e.g. 25/25, 50/25, 100/50) over the same timestamp and
> watch `buy_entry_binary` / `sell_entry_binary` flip. Because this is a
> look-ahead oracle, the result is the theoretical ceiling for that
> take-profit/stop-loss geometry, which is the number a real predictor gets
> scored against.

## Build, test and lint commands

```bash
# install
pip install -e .                     # root service
pip install yfinance                 # required to boot (see quickstart)
pip install -e ./mechanics           # optional nested package

# tests — root suite
PYTHONPATH=. python -m pytest -q --collect-only
PYTHONPATH=. python -m pytest -q tests/unit_tests \
  --ignore=tests/unit_tests/test_feeder_plugins.py \
  --ignore=tests/unit_tests/test_unit_feeder.py

# tests — nested mechanics package
cd mechanics && python -m pytest -q

# run
PYTHONPATH=. python app/main.py --help
PYTHONPATH=. python app/main.py --load_config <config.json>
./pp.sh --load_config <config.json>   # same thing; sets PYTHONPATH for you
```

Observed on Python 3.12.13:

| Command | Result |
|---|---|
| root `--collect-only`, no `yfinance` | `178 tests collected, 5 errors` (all five are `ModuleNotFoundError: No module named 'yfinance'`) |
| root `--collect-only`, `yfinance` importable | `192 tests collected`, clean |
| `tests/unit_tests` minus the two feeder files | `40 passed` |
| `mechanics/` suite | `19 passed` |

There is no linter configured in this repository — no `ruff`, `flake8`,
`black` or pre-commit configuration exists. `pyproject.toml` declares only the
build backend and pytest markers (`integration`, `acceptance`).

`run_all_tests.sh` exists but hard-codes an absolute path to one machine's
checkout; prefer the `pytest` invocations above.

## Layout

| Path | Contents |
|---|---|
| `app/` | Service internals: entry point (`main.py`), CLI, config load/merge, plugin loader, SQLAlchemy models, auth, and the admin/client/billing/evaluator routers. |
| `plugins_core/` | Core plugins that own the FastAPI app object and the uvicorn boot: `default_core` (async) and `sync_core` (adds the entry/exit/model-info routes used by backtest and execution clients). |
| `plugins_endpoints/` | Individually registrable endpoint plugins (predict, health, info, metrics). |
| `plugins_feeder/` | Data acquisition. Hard-imports `yfinance` at package import time. |
| `plugins_pipeline/` | Orchestration between feeder and predictor. |
| `plugins_predictor/` | Predictor plugins: Keras/ONNX wrappers, binary/direction models, CSV replay, and the look-ahead oracles used for ceilings and fixtures. |
| `mechanics/` | Separate installable project (`prediction-provider-mechanics`, `src/` layout, own tests and `tools/`): deterministic mechanics policy plus hash-verified artifact loading emitting `AssetIntent` typed by `trading-contracts`. Not installed by the root `setup.py`. |
| `examples/config/` | Repository-owned JSON configs. |
| `examples/data/` | Committed OHLC fixtures for oracle and replay predictors. |
| `examples/requests/` | Sample HTTP requests (`.http` format). |
| `tests/` | `unit_tests/`, `integration_tests/`, `system_tests/`, `acceptance_tests/`, `behavioral_tests/`, `security_tests/`, `production_tests/`. |
| `docs/` | Sparse — one design document under `docs/preprocessor/`. |

## Conventions and constraints

- **Plugin architecture via entry points.** Five groups declared in
  `setup.py`: `core.plugins`, `endpoints.plugins`, `feeder.plugins`,
  `pipeline.plugins`, `predictor.plugins`. `app/plugin_loader.py` resolves a
  name to the **first** matching entry point in the group.
- **Unqualified group names collide across repositories.** In a shared
  environment the groups `predictor.plugins` and `pipeline.plugins` are also
  claimed by the `predictor` and `agent-multi` distributions, and
  `feeder.plugins` by the legacy `timeseries-gan` package. Resolution then
  depends on `sys.path` order. Running from the repository root with
  `PYTHONPATH=.` makes this repo's own entry points win, because
  `importlib.metadata` discovers the local `prediction_provider.egg-info`
  first. Use a dedicated environment when correctness matters.
- **Config-driven, layered merge.** Precedence is plugin defaults →
  `app/config.py:DEFAULT_VALUES` → `--load_config` file → CLI flags →
  unknown CLI flags (`app/config_merger.py`). Any `--key value` pair works even
  if undeclared in `app/cli.py`.
- **Fail-closed boot.** `app/main.py` loads all five plugin types before
  starting, and `sys.exit(1)` on the first failure. There is no partial boot.
- **Hash-verified artifacts.** The `mechanics` package verifies artifact hashes
  before loading a policy (`mechanics/src/prediction_provider_mechanics/loader.py`),
  so a mismatched artifact is refused rather than silently served.
- **Known wiring gap.** `app/database.py` hard-codes
  `SQLALCHEMY_DATABASE_URL = "sqlite:///./prediction_provider.db"`. The
  `database_url` config key is parsed and merged but is **not** wired to the
  engine. The database path therefore follows the process working directory,
  not the config.
- **Auth.** Multi-role RBAC (admin / provider / client / evaluator) with JWT
  and API keys. `auth_type: "none"` exists for local experimentation only and
  must never be exposed beyond loopback.
- **Historical documents.** `README_REAL_FEEDER.md`, `TESTING_GUIDE.md`,
  `BEHAVIORAL_TESTING_GUIDE.md`, `PLUGIN_REPLICABILITY_GUIDE.md`, `REFERENCE*.md`
  and the `design_*.md` files predate the current layout. `README.md` and this
  file are the authoritative entry points.

## Do not touch

- **Do not commit or transmit credentials, account identifiers, broker
  credentials, private IP addresses or host names.** Use `<your-host>`
  placeholders in anything written to this repository.
- **Do not delete or rewrite `prediction_provider.db`.** It is several hundred
  MB of accumulated prediction, billing and audit rows. Run experiments from a
  scratch working directory (the sqlite path is relative to the CWD) or against
  a copy.
- **Do not bind the service to `0.0.0.0` or expose it off loopback.** It ships
  a config with `auth_type: "none"`, so an exposed instance is unauthenticated.
- **Do not start or stop anything in the sibling repositories.** `lts` runs
  live paper/demo trading runners and `agent-multi` runs GPU training workers.
  Never submit or cancel a broker order from here; this service has no venue
  connectivity and must not acquire any.
- **Do not modify the committed fixtures under `examples/data/`.** Recorded
  results elsewhere in the stack are reproducible only against these exact
  bytes.
- **Do not edit `mechanics/` artifacts or their recorded hashes** to make a
  load succeed. A hash mismatch is a real refusal — investigate the artifact,
  do not relax the check.
- **Do not install into a shared environment casually.** Because the
  entry-point group names collide with sibling distributions, a careless
  `pip install -e .` can change which plugin another repository resolves.
