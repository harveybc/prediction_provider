# Prediction Provider

A plugin-based, asynchronous prediction provider for financial time series, built on FastAPI with a multi-role authentication system, billing marketplace, and modular architecture.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Plugin System](#plugin-system)
- [Authentication & Authorization](#authentication--authorization)
- [API Endpoints](#api-endpoints)
- [Database Schema](#database-schema)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Testing](#testing)
- [Security Features](#security-features)

## Architecture Overview

The system is built around five plugin types that form a processing pipeline:

```
┌─────────────┐     ┌──────────────┐     ┌────────────┐
│   Feeder    │────▶│   Pipeline   │────▶│  Predictor  │
│  (data in)  │     │ (orchestrate)│     │ (model out) │
└─────────────┘     └──────────────┘     └────────────┘
                           │
                    ┌──────┴──────┐
                    │    Core     │
                    │  (FastAPI)  │
                    └──────┬──────┘
                           │
                    ┌──────┴──────┐
                    │  Endpoints  │
                    │  (routers)  │
                    └─────────────┘
```

**Core** (`plugins_core/default_core.py`): Central FastAPI application. Manages middleware (CORS, rate limiting, request logging), authentication, all API routes, and background prediction tasks.

**Feeder** (`plugins_feeder/`): Data acquisition — fetches from yfinance or CSV files, handles normalization and date filtering.

**Pipeline** (`plugins_pipeline/`): Orchestrates feeder → predictor flow. Manages prediction lifecycle (pending → processing → completed/failed).

**Predictor** (`plugins_predictor/`): Model loading and inference. Supports Keras models with MC-dropout uncertainty, ideal baseline predictions, and noisy ideal predictions.

**Endpoints** (`plugins_endpoints/`): Additional endpoint plugins (health, info, metrics, predict). Most routing is handled directly in the core plugin.

## Plugin System

Plugins are loaded via Python entry points defined in `setup.py`. Each plugin type has a dedicated directory:

| Plugin Type | Directory | Entry Point Group | Available Plugins |
|---|---|---|---|
| Core | `plugins_core/` | `core.plugins` | `default_core` |
| Feeder | `plugins_feeder/` | `feeder.plugins` | `default_feeder` |
| Pipeline | `plugins_pipeline/` | `pipeline.plugins` | `default_pipeline` |
| Predictor | `plugins_predictor/` | `predictor.plugins` | `default_predictor`, `noisy_ideal_predictor` |
| Endpoints | `plugins_endpoints/` | `endpoints.plugins` | `default_endpoints`, `predict_endpoint`, `health_endpoint`, `info_endpoint`, `metrics_endpoint` |

All plugins follow a common interface:
- `plugin_params` (dict): Default parameter values
- `plugin_debug_vars` (list): Keys for debug info
- `__init__(config)`: Initialize with config dict
- `set_params(**kwargs)`: Update parameters

See [REFERENCE_plugins.md](REFERENCE_plugins.md) for detailed plugin documentation.

## Authentication & Authorization

### Roles

The system uses role-based access control with these roles stored in the `roles` table:

| Role | Description |
|---|---|
| `administrator` / `admin` | Full system access, user management, billing oversight |
| `provider` | Can set model pricing, view earnings |
| `client` | Can request predictions, view own data, view spend |
| `evaluator` | Can claim and process prediction requests from queue |
| `operator` | Can view logs and usage stats |
| `guest` | Minimal access |

### Authentication Methods

1. **API Key** (primary): Pass `X-API-KEY` header. Keys are SHA-256 hashed and stored in `users.hashed_api_key`.
2. **JWT Token**: Obtain via `/api/v1/auth/login`, pass as Bearer token.
3. **Flexible auth**: Main prediction endpoints (`/api/v1/predictions/`, `/api/v1/predict`) support optional authentication — public access when `REQUIRE_AUTH=false` (default), API key validated when provided.

### User Lifecycle

1. Admin creates user via `POST /api/v1/admin/users` → user gets API key, `is_active=False`
2. Admin activates via `POST /api/v1/admin/users/{username}/activate`
3. User obtains API key via `POST /api/v1/auth/api-key` (username/password)
4. User authenticates all requests with `X-API-KEY` header

## API Endpoints

### Public / Flexible Auth

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Root — API info |
| `GET` | `/health` | Health check |
| `POST` | `/api/v1/predict` | Create prediction (public or authenticated) |
| `POST` | `/api/v1/predictions/` | Create prediction (flexible auth) |
| `GET` | `/api/v1/predictions/` | List predictions |
| `GET` | `/api/v1/predictions/{id}` | Get prediction by ID |
| `DELETE` | `/api/v1/predictions/{id}` | Delete prediction |
| `GET` | `/api/v1/plugins/` | List available plugins |
| `GET` | `/api/v1/plugins/status` | Plugin status |
| `POST` | `/predict` | Legacy predict endpoint |
| `GET` | `/status/{id}` | Legacy status endpoint |

### Authenticated (API Key Required)

| Method | Path | Role | Description |
|---|---|---|---|
| `POST` | `/api/v1/auth/login` | any | Login, get JWT token |
| `POST` | `/api/v1/auth/api-key` | any | Get API key |
| `POST` | `/api/v1/auth/regenerate-key` | any | Regenerate API key |
| `POST` | `/api/v1/secure/predictions/` | any | Create prediction (secure) |
| `GET` | `/api/v1/secure/predictions/` | any | List own predictions (secure) |
| `GET` | `/api/v1/secure/predictions/{id}` | any | Get prediction (secure) |
| `DELETE` | `/api/v1/secure/predictions/{id}` | any | Delete prediction (secure) |
| `POST` | `/api/v1/auth/predictions/` | any | Create prediction (authenticated) |
| `GET` | `/api/v1/users/profile` | any | Get own profile |
| `PUT` | `/api/v1/users/password` | any | Change password |
| `PUT` | `/api/v1/users/profile` | any | Update profile (no role changes) |

### Admin Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/admin/users` | Create user |
| `GET` | `/api/v1/admin/users` | List all users |
| `POST` | `/api/v1/admin/users/{username}/activate` | Activate user |
| `POST` | `/api/v1/admin/users/{username}/deactivate` | Deactivate user |
| `GET` | `/api/v1/admin/logs` | Get system logs |
| `GET` | `/api/v1/admin/usage/{username}` | Get user usage stats |
| `DELETE` | `/api/v1/admin/logs/{id}` | Blocked — returns 405 |
| `PUT` | `/api/v1/admin/logs/{id}` | Blocked — returns 405 |

### Admin Endpoints (v1 admin router — `admin_endpoints.py`)

These are registered under `/api/v1/admin` via the admin router:

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/admin/users` | Create user (with password, role, subscription) |
| `GET` | `/api/v1/admin/users` | List users with filtering/pagination |
| `PUT` | `/api/v1/admin/users/{user_id}` | Update user |
| `DELETE` | `/api/v1/admin/users/{user_id}` | Deactivate/delete user |
| `GET` | `/api/v1/admin/audit` | Audit logs with filtering |
| `GET` | `/api/v1/admin/stats` | System statistics |
| `POST` | `/api/v1/admin/config` | Update system config |
| `GET` | `/api/v1/admin/system/health` | Detailed system health |

### Billing & Provider Endpoints (`billing_endpoints.py`)

| Method | Path | Role | Description |
|---|---|---|---|
| `POST` | `/api/v1/provider/pricing` | provider/admin | Set model pricing |
| `GET` | `/api/v1/provider/pricing` | provider/admin | Get own pricing |
| `GET` | `/api/v1/provider/earnings` | provider/admin | Earnings summary |
| `GET` | `/api/v1/client/spend` | client/admin | Spend summary |
| `GET` | `/api/v1/client/billing` | client/admin | Billing history |
| `GET` | `/api/v1/admin/billing` | admin | All billing records |
| `GET` | `/api/v1/admin/billing/summary` | admin | Billing summary |
| `GET` | `/api/v1/admin/pricing` | admin | All active pricing |

### Client Endpoints (`client_endpoints.py`)

Registered under `/api/v1/client`:

| Method | Path | Role | Description |
|---|---|---|---|
| `POST` | `/api/v1/client/predict` | client/admin | Submit prediction request |
| `GET` | `/api/v1/client/predictions/{id}` | any authenticated | Get prediction details |
| `GET` | `/api/v1/client/predictions/` | any authenticated | List predictions with filters |
| `PUT` | `/api/v1/client/predictions/{id}` | client/admin | Update pending prediction |
| `DELETE` | `/api/v1/client/predictions/{id}` | client/admin | Cancel prediction |
| `GET` | `/api/v1/client/predictions/{id}/download/{file}` | any authenticated | Download result file |

### Evaluator Endpoints (`evaluator_endpoints.py`)

Registered under `/api/v1/evaluator`:

| Method | Path | Role | Description |
|---|---|---|---|
| `GET` | `/api/v1/evaluator/pending` | evaluator/admin | List pending requests |
| `POST` | `/api/v1/evaluator/claim/{id}` | evaluator/admin | Claim request for processing |
| `POST` | `/api/v1/evaluator/submit/{id}` | evaluator/admin | Submit results |
| `GET` | `/api/v1/evaluator/assigned` | evaluator/admin | List assigned requests |
| `POST` | `/api/v1/evaluator/release/{id}` | evaluator/admin | Release request back to queue |
| `GET` | `/api/v1/evaluator/stats` | evaluator/admin | Performance statistics |

## Database Schema

SQLite database (`prediction_provider.db`) with SQLAlchemy ORM.

### Core Tables

| Table | Description |
|---|---|
| `users` | User accounts with hashed passwords and API keys |
| `roles` | Role definitions with JSON permissions |
| `predictions` | Prediction records (main table used by core endpoints) |
| `prediction_jobs` | Extended prediction jobs (used by client/evaluator endpoints) |
| `api_logs` | HTTP request audit log |
| `time_series_data` | Cached time series data |
| `system_configuration` | Key-value system config |
| `billing_records` | Client-provider billing transactions |
| `provider_pricing` | Provider model pricing |
| `user_sessions` | Active user sessions |

### Extended Tables (`database_models_extended.py`)

Additional tables for the full marketplace (defined but not all actively used):

`predictions_extended`, `prediction_files`, `transactions`, `credits`, `invoices`, `audit_log_extended`, `security_events`, `compliance_reports`, `system_metrics`, `performance_metrics`, `users_extended`

## Installation

```bash
# Clone the repository
git clone git@github.com:harveybc/prediction_provider.git
cd prediction_provider

# Install dependencies
pip install -r requirements.txt

# Install the package (registers entry points for plugins)
pip install -e .

# Initialize database (tables created automatically on first run)
python -c "from plugins_core.default_core import app; print('DB initialized')"
```

### Requirements

- Python 3.12+
- TensorFlow 2.x (for default predictor)
- SQLite (bundled with Python)

## Configuration

Configuration is loaded in order of precedence (highest last):
1. `app/config.py` `DEFAULT_VALUES`
2. Config file (`--load_config config.json`)
3. CLI arguments
4. Unknown CLI args (plugin-specific)

### Key Configuration Parameters

```python
# Core
host = "127.0.0.1"
port = 8000

# Database
database_url = "sqlite:///predictions.db"

# Security
secret_key = "your-secret-key-here"
algorithm = "HS256"
access_token_expire_minutes = 30
require_activation = True  # Users must be activated by admin

# Feeder
feeder_plugin = "default_feeder"
instrument = "MSFT"
data_source = "yfinance"  # or "file"
data_file_path = None  # path to CSV when data_source="file"

# Predictor
predictor_plugin = "default_predictor"  # or "noisy_ideal_predictor"
model_path = None
prediction_horizon = 6

# Pipeline
pipeline_plugin = "default_pipeline"
prediction_interval = 300
```

### Environment Variables

| Variable | Description |
|---|---|
| `PREDICTION_PROVIDER_QUIET` | Set to `1` to suppress verbose output |
| `REQUIRE_AUTH` | Set to `true` to require authentication on flexible endpoints |
| `SKIP_BACKGROUND_TASKS` | Set to `true` to skip background prediction processing |
| `SKIP_RATE_LIMITING` | Set to `true` to disable rate limiting |
| `TF_CPP_MIN_LOG_LEVEL` | Set to `3` to suppress TensorFlow C++ logs |

## Usage

### Running the Server

```bash
# Basic start
prediction_provider

# With config file
prediction_provider --load_config config.json

# With custom host/port
prediction_provider --host 0.0.0.0 --port 8080

# Quiet mode
PREDICTION_PROVIDER_QUIET=1 prediction_provider
```

### Making Predictions

```bash
# Public prediction (no auth required by default)
curl -X POST http://localhost:8000/api/v1/predict \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL", "prediction_type": "short_term"}'

# Authenticated prediction
curl -X POST http://localhost:8000/api/v1/predict \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: your-api-key" \
  -d '{"symbol": "AAPL", "prediction_type": "short_term", "prediction_horizon": 6}'

# Check prediction status
curl http://localhost:8000/api/v1/predictions/1
```

### Admin Workflow

```bash
# Login as admin
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin_password"}'

# Create a client user
curl -X POST http://localhost:8000/api/v1/admin/users \
  -H "X-API-KEY: admin-api-key" \
  -H "Content-Type: application/json" \
  -d '{"username": "client1", "email": "client1@example.com", "role": "client"}'

# Activate the user
curl -X POST http://localhost:8000/api/v1/admin/users/client1/activate \
  -H "X-API-KEY: admin-api-key"
```

## Testing

```bash
# Run all tests
PREDICTION_PROVIDER_QUIET=1 pytest tests/ -v

# Run specific test suites
pytest tests/unit_tests/ -v
pytest tests/integration_tests/ -v
pytest tests/security_tests/ -v
pytest tests/acceptance_tests/ -v
pytest tests/system_tests/ -v
pytest tests/behavioral_tests/ -v
pytest tests/production_tests/ -v
```

### Test Structure

| Suite | Directory | Focus |
|---|---|---|
| Unit | `tests/unit_tests/` | Individual plugins, models, endpoints |
| Integration | `tests/integration_tests/` | Database, plugin loading, API integration, prediction pipeline |
| Security | `tests/security_tests/` | Authentication, authorization, billing, input validation, rate limiting |
| Acceptance | `tests/acceptance_tests/` | End-to-end API workflows, LTS workflow |
| System | `tests/system_tests/` | Core orchestration, database integrity, logging, security |
| Behavioral | `tests/behavioral_tests/` | User behavior patterns |
| Production | `tests/production_tests/` | Production readiness checks |

See [TESTING_GUIDE.md](TESTING_GUIDE.md) for details.

## Security Features

- **Password hashing**: bcrypt (via `app/auth.py`)
- **API key hashing**: SHA-256
- **JWT tokens**: HS256 algorithm with configurable expiration
- **Rate limiting**: Login endpoint limited to 3 attempts/60 seconds (configurable)
- **Concurrent prediction limits**: Max 10 per user (configurable)
- **Input sanitization**: HTML escaping, script tag removal, ticker validation
- **CORS**: Configurable (currently allows all origins)
- **Audit logging**: All API requests logged to `api_logs` table
- **Audit immutability**: DELETE/PUT on audit logs returns 405
- **Role-based access control**: Fine-grained permissions per endpoint

## Project Structure

```
prediction_provider/
├── app/                          # Core application code
│   ├── main.py                   # Entry point
│   ├── config.py                 # Default configuration values
│   ├── config_handler.py         # Config file loading
│   ├── config_merger.py          # Config merging logic
│   ├── cli.py                    # CLI argument parsing
│   ├── auth.py                   # Authentication & authorization
│   ├── database.py               # SQLAlchemy engine & session
│   ├── database_models.py        # Core database models
│   ├── database_models_extended.py # Extended marketplace models
│   ├── database_utilities.py     # DB utility functions
│   ├── models.py                 # Prediction SQLAlchemy model + Pydantic schemas
│   ├── plugin_loader.py          # Entry point plugin loading
│   ├── plugin_manager.py         # Plugin registry
│   ├── user_management.py        # User management router
│   ├── admin_endpoints.py        # Admin API router
│   ├── billing_endpoints.py      # Billing/provider API router
│   ├── client_endpoints.py       # Client API router
│   └── evaluator_endpoints.py    # Evaluator API router
├── plugins_core/                 # Core plugins
│   └── default_core.py           # FastAPI app, all routes, middleware
├── plugins_feeder/               # Data feeder plugins
│   ├── default_feeder.py         # yfinance/CSV data feeder
│   ├── real_feeder.py            # Real-time feeder
│   └── ...                       # Other feeder variants
├── plugins_pipeline/             # Pipeline plugins
│   ├── default_pipeline.py       # Standard pipeline orchestration
│   └── enhanced_pipeline.py      # Enhanced with date range support
├── plugins_predictor/            # Predictor plugins
│   ├── default_predictor.py      # Keras model predictor with MC-dropout
│   └── noisy_ideal_predictor.py  # Look-ahead predictor with noise
├── plugins_endpoints/            # Endpoint plugins
│   ├── default_endpoints.py      # Default endpoint plugin
│   ├── predict_endpoint.py       # Predict endpoint
│   ├── health_endpoint.py        # Health endpoint
│   ├── info_endpoint.py          # Info endpoint
│   └── metrics_endpoint.py       # Metrics endpoint
├── tests/                        # Test suites
├── setup.py                      # Package setup with entry points
├── requirements.txt              # Python dependencies
└── pyproject.toml                # Build configuration
```

## License

See repository for license information.

## Author

Harvey Bastidas
