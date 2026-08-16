# Prediction Provider

A plugin-based FastAPI service that serves financial time-series predictions
over HTTP. It loads predictor plugins (Keras/ONNX model wrappers, ideal
oracles, CSV replay), feeds them through a configurable feeder → pipeline →
predictor chain, and exposes prediction, health, info and metrics endpoints
with multi-role authentication, billing/marketplace records and SQL
persistence. It sits between the model-training repositories and the
execution side of the stack.

## Status

**ACTIVE — core repository.** Package `prediction_provider` version
**0.1.0** ([`setup.py`](setup.py)); nested package
`prediction-provider-mechanics` version **0.1.0**
([`mechanics/pyproject.toml`](mechanics/pyproject.toml)).

**Trading status:** this service only serves predictions; its consumers run
in **simulation and paper/demo venues only** — real capital is not enabled
anywhere in this stack, and nothing here is financial advice.

## Run this with an AI agent

Paste this into Claude Code, Cursor, Codex, GitHub Copilot or any coding agent
with shell access:

> Read `AGENTS.md` in this repository and follow the **Agent quickstart**
> section end to end: set up the environment, run the smoke test, execute the
> example oracle-predictor service run, then tell me the exact URL or file
> paths where I can see the results and one query I should try first.

`AGENTS.md` is the [agents.md](https://agents.md) convention, read natively by
most coding agents.

## Role and non-responsibilities

**Owns**

- HTTP prediction serving: `POST /api/v1/predict`,
  `POST /api/v1/predict/entry`, `POST /api/v1/predict/exit`,
  `GET /api/v1/model/info`, plus health/info/metrics endpoints
  ([`plugins_core/`](plugins_core/), [`plugins_endpoints/`](plugins_endpoints/)).
- Predictor plugin loading and inference orchestration.
- Multi-role auth (admin / provider / client / evaluator), billing records
  and prediction persistence ([`app/auth.py`](app/auth.py),
  [`app/billing_endpoints.py`](app/billing_endpoints.py),
  [`app/database_models.py`](app/database_models.py)).
- Deterministic serving mechanics: the nested
  [`mechanics/`](mechanics/) package
  (`prediction_provider_mechanics`) implements a provider-owned mechanics
  policy with hash-verified artifact loading that emits canonical
  `AssetIntent` objects typed by
  [trading-contracts](https://github.com/harveybc/trading-contracts).

**Does not own**

- Model training — models are produced by
  [predictor](https://github.com/harveybc/predictor) and related pipelines
  and are loaded here for serving.
- Order execution or venue connectivity —
  [lts](https://github.com/harveybc/lts) consumes this API and owns
  execution.
- Backtesting — [heuristic-strategy](https://github.com/harveybc/heuristic-strategy)
  queries this API per tick from its backtests.

## Architecture

Five plugin families form the serving pipeline (feeder → pipeline →
predictor, hosted by a core plugin that registers endpoint plugins):

| Group | Directory | Registered plugins (from `setup.py`) |
|---|---|---|
| `core.plugins` | [`plugins_core/`](plugins_core/) | `default_core` (async FastAPI + background tasks), `sync_core` (synchronous serving used by backtest clients) |
| `pipeline.plugins` | [`plugins_pipeline/`](plugins_pipeline/) | `default_pipeline` |
| `feeder.plugins` | [`plugins_feeder/`](plugins_feeder/) | `default_feeder` |
| `predictor.plugins` | [`plugins_predictor/`](plugins_predictor/) | `default_predictor`, `noisy_ideal_predictor`, `binary_ideal_oracle`, `binary_entry_predictor`, `binary_exit_predictor`, `binary_predictor`, `direction_predictor`, `direction_ideal_oracle`, `csv_direction_predictor` |
| `endpoints.plugins` | [`plugins_endpoints/`](plugins_endpoints/) | `default_endpoints`, `predict_endpoint`, `health_endpoint`, `info_endpoint`, `metrics_endpoint` |

The nested [`mechanics/`](mechanics/) package is a separate installable
project (`src/` layout, own tests) and is **not** installed by the root
`setup.py`.

Consumers of this service:

- [lts](https://github.com/harveybc/lts) — `prediction_strategy` broker/strategy
  integration over HTTP.
- [heuristic-strategy](https://github.com/harveybc/heuristic-strategy) —
  `api_predictions` plugin calls entry/exit endpoints on every tick.

## Requirements

- Root package: no `python_requires` declared in [`setup.py`](setup.py);
  verified with **Python 3.12.13**. The nested mechanics package requires
  **Python >= 3.12**.
- Key dependencies (from `install_requires`): `fastapi`, `uvicorn`,
  `flask`, `pandas`, `numpy`, `scikit-learn`, `tensorflow`, `onnxruntime`,
  `pyjwt`, `sqlalchemy`.
- `yfinance` is required to **boot the service at all**, not only for the
  `yfinance`-backed feeder path: `plugins_feeder/__init__.py` imports
  `real_feeder` → `data_fetcher`, which does an unguarded `import yfinance`,
  and `app/main.py` exits 1 when a plugin fails to load. It is listed in
  `requirements.txt` but not in `setup.py`'s `install_requires`; without it,
  five test files also fail collection.

## Installation

```bash
git clone https://github.com/harveybc/prediction_provider.git
cd prediction_provider
pip install -e .            # root service (unverified in a clean env)
pip install -e ./mechanics  # optional: deterministic mechanics package
```

Both installs are marked unverified for a clean environment; imports and
test collection were verified in an existing Python 3.12.13 environment.
Note that the root package installs a generic top-level package named
`app`, which can collide with sibling repositories installed editable in
the same environment — prefer a dedicated virtual environment or run with
`PYTHONPATH=./` from the repository root.

## Smallest working example

```bash
python app/main.py --help
```

Verified: exits 0 and prints the CLI reference (`--load_config`,
plugin-selection flags, output/remote-config options). Importing the
application (`PYTHONPATH=./ python -c "import app.main"`) was also verified
and logs `All endpoint routers successfully registered`.

To boot the server against a committed fixture with no model artifact and no
network access:

```bash
PYTHONPATH=./ python app/main.py \
  --load_config examples/config/direction_ideal_oracle.json \
  --csv_file examples/data/phase_1c_direction_test_ohlc.csv \
  --host 127.0.0.1 --port 8000
```

Verified (with `yfinance` importable): `/health` returns `{"status":"ok"}`,
`/docs`, `/redoc` and `/openapi.json` return `200`, and
`POST /api/v1/predict/entry` with
`{"datetime":"03.12.2018 08:00:00.000","tp":50,"sl":25}` returns
`{"buy_entry_binary":0,"sell_entry_binary":1,"bars_remaining":2,...}`. The two
overrides are needed because the committed config points `csv_file` at a path
in a sibling repository and sets `host` to `0.0.0.0`.

Caveats for the other configs: `default_config.json` points `data_file_path`
at `examples/data/phase_3/base_d1.csv`, which is not present (the committed
files are `base_d2/d3/d5/d6.csv`); adjust that key to an existing CSV before
booting. Example request payloads are in
[`examples/requests/`](examples/requests/); the committed `.http` file also
references the missing `base_d1.csv`.

For an agent-executable version of this recipe, see
[`AGENTS.md`](AGENTS.md).

## Configuration and plugin reference

Configuration is JSON merged from defaults, `--load_config`, CLI flags and
unknown-argument passthrough ([`app/config_handler.py`](app/config_handler.py),
[`app/config_merger.py`](app/config_merger.py)). Repository-owned configs
live in [`examples/config/`](examples/config/). Detailed plugin interface
documentation: [`REFERENCE_plugins.md`](REFERENCE_plugins.md).

## Tests and validation

```bash
PYTHONPATH=./ python -m pytest -q --collect-only     # root suite
cd mechanics && python -m pytest -q                  # nested package
```

Observed results (Python 3.12.13):

- Root, without `yfinance`: `178 tests collected, 5 errors` — all five
  collection errors are `ModuleNotFoundError: No module named 'yfinance'`.
- Root, with `yfinance` importable: `192 tests collected`, clean.
- Root unit subset excluding the two feeder test files: `40 passed`, no
  `yfinance` needed.
- Mechanics: `19 passed`, and
  `from prediction_provider_mechanics import policy, loader` imports OK.

Test suites are organized under [`tests/`](tests/) (unit, integration,
system, acceptance, behavioral, security, production).

## Artifacts, data and outputs

- Persistence is SQLite. Note that `app/database.py` hard-codes
  `sqlite:///./prediction_provider.db`: the `database_url` config key is
  parsed and merged but is not wired to the engine, so the database file
  follows the process working directory. Predictions, users, roles and
  billing records live there.
- Served model artifacts are external inputs referenced by config; the
  mechanics package verifies artifact hashes before loading.
- Example datasets for oracle/replay predictors are committed under
  [`examples/data/`](examples/data/).

## Safety, security and credentials

- Multi-role RBAC (admin / provider / client / evaluator) with JWT and API
  keys; `auth_type: "none"` exists for local experimentation only and must
  not be exposed publicly.
- No credentials are committed; database URLs and secrets come from local
  config/environment.
- This service must sit behind trusted networking in any deployment; it has
  no venue connectivity and moves no capital.

## Limitations

- **Undocumented-by-packaging `mechanics/` package.** It is a separate
  project inside the repo, absent from the root `setup.py`; install it
  explicitly if you need contract-typed mechanics.
- **Entry-point group collision.** The unqualified group names are shared
  with sibling projects: `feeder.plugins` is also claimed by the legacy
  [timeseries-gan](https://github.com/harveybc/timeseries-gan) package, and in
  a shared environment `predictor.plugins` and `pipeline.plugins` resolve to
  the `predictor` and `agent-multi` distributions. `app/plugin_loader.py`
  takes the first match in the group, so resolution depends on `sys.path`
  order. Use a dedicated environment, or run from the repository root with
  `PYTHONPATH=./` so the local `prediction_provider.egg-info` is found first.
- **Root script sprawl and committed residue.** The repository root carries
  one-off analysis scripts (`analyze_column_ranges.py`,
  `compare_indicators.py`, `create_stoch_lookup.py`, `fast_test_check.py`),
  a vendored copy of `heuristic_strategy` logic
  ([`app/heuristic_strategy.py`](app/heuristic_strategy.py)), several
  overlapping guides (`README_REAL_FEEDER.md`, `TESTING_GUIDE.md`,
  `BEHAVIORAL_TESTING_GUIDE.md`, `PLUGIN_REPLICABILITY_GUIDE.md`, design
  documents) and run residue (`app.log`, `pp_server.log`,
  `prediction_provider.db`, `fe_replicated_output*.csv`). This README is
  the authoritative entry point; treat the rest as historical.
- **`database_url` is not wired.** `app/database.py` hard-codes
  `sqlite:///./prediction_provider.db`, so the config key has no effect and
  the database path follows the process working directory.
- The stale `data_file_path` in `default_config.json` (see the example
  section) and the generic top-level `app` package name remain unfixed.
- No LICENSE file currently exists in this repository.
