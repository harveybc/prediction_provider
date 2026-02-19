# File Reference

## Application Code (`app/`)

| File | Description |
|---|---|
| `main.py` | Entry point. Loads config, plugins, starts server. |
| `config.py` | `DEFAULT_VALUES` dict with all configuration parameters |
| `config_handler.py` | Config file loading (JSON) |
| `config_merger.py` | Merges config from defaults, files, CLI args |
| `cli.py` | CLI argument parser |
| `auth.py` | Authentication: bcrypt, JWT, API keys, role decorators |
| `database.py` | SQLAlchemy engine, `SessionLocal`, `Base`, `get_db()` |
| `database_models.py` | Core ORM models: User, Role, PredictionJob, ApiLog, TimeSeriesData, SystemConfiguration, BillingRecord, ProviderPricing, UserSession |
| `database_models_extended.py` | Extended ORM models for full marketplace (mostly schema-only) |
| `database_utilities.py` | `get_db_session()`, `create_all_tables()` |
| `models.py` | `Prediction` ORM model, Pydantic schemas, DB helpers |
| `plugin_loader.py` | Entry point plugin discovery and loading |
| `plugin_manager.py` | Simple plugin name→instance registry |
| `user_management.py` | User management router (auth, CRUD, logs, usage) |
| `admin_endpoints.py` | Admin router (users, audit, stats, config, health) |
| `billing_endpoints.py` | Billing router (pricing, earnings, spend, billing) |
| `client_endpoints.py` | Client router (predict, list, update, cancel, download) |
| `evaluator_endpoints.py` | Evaluator router (pending, claim, submit, release, stats) |
| `data_handler.py` | Data handling utilities |
| `data_processor.py` | Data processing utilities |
| `reconstruction.py` | Signal reconstruction utilities |
| `heuristic_strategy.py` | Heuristic trading strategy |
| `optimizer_ga.py` | Genetic algorithm optimizer |
| `arima_optimizer.py` | ARIMA model optimizer |

## Core Plugin (`plugins_core/`)

| File | Description |
|---|---|
| `default_core.py` | FastAPI app, all routes, middleware, auth, background tasks, input sanitization, rate limiting |

## Feeder Plugins (`plugins_feeder/`)

| File | Description |
|---|---|
| `default_feeder.py` | Main feeder: yfinance + CSV with normalization |
| `real_feeder.py` | Real-time data feeder |
| `real_feeder_original.py` | Original real-time feeder variant |
| `real_feeder_modular.py` | Modular real-time feeder |
| `fe_replicator_feeder.py` | Feature engineering replicator |
| `default_feeder_new.py` | Experimental feeder variant |
| `data_fetcher.py` | Data fetching utilities |
| `data_normalizer.py` | Data normalization |
| `data_validator.py` | Data validation |
| `feature_generator.py` | Feature generation |
| `stl_feature_generator.py` | STL decomposition features |
| `stl_preprocessor.py` | STL preprocessing |
| `technical_indicators.py` | Technical indicator computation |

## Pipeline Plugins (`plugins_pipeline/`)

| File | Description |
|---|---|
| `default_pipeline.py` | Standard pipeline: feeder→predictor→DB |
| `default_pipeline_new.py` | Experimental pipeline variant |
| `enhanced_pipeline.py` | Date range + real-time mode support |

## Predictor Plugins (`plugins_predictor/`)

| File | Description |
|---|---|
| `default_predictor.py` | Keras model loading, MC-dropout uncertainty, ideal baseline |
| `default_predictor_new.py` | Experimental predictor variant |
| `noisy_ideal_predictor.py` | Look-ahead predictions with Gaussian noise |

## Endpoint Plugins (`plugins_endpoints/`)

| File | Description |
|---|---|
| `default_endpoints.py` | Default endpoint plugin (FastAPI router) |
| `predict_endpoint.py` | Predict endpoint plugin |
| `health_endpoint.py` | Health check endpoint |
| `info_endpoint.py` | System info endpoint |
| `metrics_endpoint.py` | Metrics endpoint |
| `*_new.py` variants | Experimental endpoint variants |

## Configuration & Build

| File | Description |
|---|---|
| `setup.py` | Package setup with entry points |
| `pyproject.toml` | Build system config |
| `requirements.txt` | Python dependencies |

## Documentation

| File | Description |
|---|---|
| `README.md` | Project overview and reference |
| `REFERENCE.md` | Complete API reference |
| `REFERENCE_plugins.md` | Plugin reference |
| `REFERENCE_files.md` | This file |
| `user_manual.md` | User guide for clients, providers, admins |
| `IMPLEMENTATION_SUMMARY.md` | Implementation status |
| `TESTING_GUIDE.md` | Test structure and execution |
| `BEHAVIORAL_TESTING_GUIDE.md` | Behavioral test guide |
| `PLUGIN_REPLICABILITY_GUIDE.md` | Plugin creation guide |
| `design_system.md` | System architecture |
| `design_acceptance.md` | Acceptance criteria |
| `design_integration.md` | Integration points |
| `design_unit.md` | Unit specifications |

## Tests (`tests/`)

| Directory | Description |
|---|---|
| `unit_tests/` | Plugin, model, endpoint unit tests |
| `integration_tests/` | DB, API, pipeline, plugin loading integration |
| `security_tests/` | Auth, authz, billing, input validation, rate limiting |
| `acceptance_tests/` | End-to-end workflow tests |
| `system_tests/` | Core orchestration, DB integrity, logging, security |
| `behavioral_tests/` | User behavior patterns |
| `production_tests/` | Production readiness |
