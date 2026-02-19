# Testing Guide

## Quick Start

```bash
cd prediction_provider
pip install -e .
PREDICTION_PROVIDER_QUIET=1 TF_CPP_MIN_LOG_LEVEL=3 pytest tests/ -v
```

## Test Structure

```
tests/
├── conftest.py                          # Root conftest (shared fixtures)
├── _shared_reset.py                     # Shared DB reset utilities
├── requirements.txt                     # Test dependencies
├── unit_tests/
│   ├── test_unit.py                     # Core unit tests
│   ├── test_unit_core.py               # Core plugin unit tests
│   ├── test_unit_database.py           # Database model tests
│   ├── test_unit_endpoints.py          # Endpoint unit tests
│   ├── test_unit_feeder.py             # Feeder plugin tests
│   ├── test_unit_models.py             # Pydantic model tests
│   ├── test_unit_pipeline.py           # Pipeline plugin tests
│   ├── test_unit_predictor.py          # Predictor plugin tests
│   ├── test_api_endpoints.py           # API endpoint tests
│   ├── test_database_models.py         # Database model tests
│   ├── test_feeder_plugin.py           # Feeder plugin tests
│   ├── test_feeder_plugins.py          # Multiple feeder tests
│   ├── test_feeder_plugins_new.py      # New feeder tests
│   ├── test_noisy_ideal_predictor.py   # Noisy ideal predictor tests
│   ├── test_pipeline_plugins.py        # Pipeline plugin tests
│   ├── test_predictor_plugin.py        # Predictor plugin tests
│   └── test_predictor_plugins.py       # Multiple predictor tests
├── integration_tests/
│   ├── conftest.py                      # Integration fixtures
│   ├── test_api_integration.py         # Full API integration
│   ├── test_database_interaction.py    # DB interaction tests
│   ├── test_database_interaction_clean.py
│   ├── test_database_prediction_lifecycle.py
│   ├── test_database_prediction_lifecycle_simple.py
│   ├── test_database_schema.py         # Schema validation
│   ├── test_database_schema_clean.py
│   ├── test_integration.py             # General integration
│   ├── test_model_selection_pipeline.py
│   ├── test_plugin_loading.py          # Plugin entry point loading
│   ├── test_plugin_loading_clean.py
│   ├── test_prediction_pipeline.py     # Pipeline flow tests
│   └── test_prediction_pipeline_clean.py
├── security_tests/
│   ├── conftest.py                      # Security fixtures (users, roles, API keys)
│   ├── test_authentication.py          # Auth flow tests
│   ├── test_authorization.py           # Role-based access tests
│   ├── test_billing.py                 # Billing endpoint tests
│   ├── test_input_validation.py        # Input sanitization tests
│   ├── test_rate_limiting.py           # Rate limiting tests
│   └── test_security_vulnerabilities.py # XSS, injection, etc.
├── acceptance_tests/
│   ├── test_acceptance.py              # End-to-end acceptance
│   ├── test_api_workflow.py            # Full API workflow
│   └── test_lts_workflow.py            # LTS integration workflow
├── system_tests/
│   ├── conftest.py                      # System test fixtures
│   ├── test_core_orchestration.py      # Core plugin orchestration
│   ├── test_database_integrity.py      # DB integrity checks
│   ├── test_logging.py                 # Logging tests
│   ├── test_security.py               # System-level security
│   └── test_system.py                  # General system tests
├── behavioral_tests/
│   ├── conftest.py                      # Behavioral fixtures
│   └── test_user_behavior.py           # User workflow patterns
└── production_tests/
    ├── conftest.py                      # Production fixtures
    └── test_production_readiness.py    # Production readiness checks
```

## Running Specific Suites

```bash
# Unit tests only
pytest tests/unit_tests/ -v

# Integration tests
pytest tests/integration_tests/ -v

# Security tests
pytest tests/security_tests/ -v

# Acceptance tests
pytest tests/acceptance_tests/ -v

# System tests
pytest tests/system_tests/ -v

# Behavioral tests
pytest tests/behavioral_tests/ -v

# Production readiness
pytest tests/production_tests/ -v

# Single test file
pytest tests/unit_tests/test_noisy_ideal_predictor.py -v

# Single test
pytest tests/security_tests/test_authentication.py::test_login_success -v
```

## Test Dependencies

```bash
pip install pytest pytest-asyncio pytest-cov httpx
```

Key test dependencies (from `tests/requirements.txt` and `requirements.txt`):
- `pytest` — Test runner
- `pytest-asyncio` — Async test support
- `pytest-cov` — Coverage reporting
- `httpx` — Async HTTP client for FastAPI TestClient
- `bcrypt` — Password hashing
- `python-jose[cryptography]` — JWT tokens

## Common Test Fixtures

The `tests/conftest.py` and suite-specific conftest files provide:

- **Database fixtures**: In-memory SQLite with fresh schema per test
- **User fixtures**: Admin, client, provider, evaluator users with API keys
- **TestClient**: FastAPI TestClient with dependency overrides
- **Role fixtures**: Pre-created roles (admin, client, provider, evaluator, operator)

## Environment Variables for Testing

```bash
PREDICTION_PROVIDER_QUIET=1    # Suppress verbose output
TF_CPP_MIN_LOG_LEVEL=3         # Suppress TensorFlow logs
SKIP_BACKGROUND_TASKS=true     # Skip async prediction tasks
SKIP_RATE_LIMITING=true        # Disable rate limiting in tests
REQUIRE_AUTH=false              # Allow public access to flexible endpoints
```

## Coverage Report

```bash
pytest tests/ --cov=app --cov=plugins_core --cov=plugins_feeder --cov=plugins_pipeline --cov=plugins_predictor --cov-report=html
```

## Notes

- Some tests use `"_clean"` suffix variants that ensure a fresh database state
- The `_shared_reset.py` module provides utilities for resetting database state between tests
- Security tests create their own user/role fixtures to test auth flows in isolation
- Integration tests may require `pip install -e .` for entry point resolution
