# Unit Design — As Built

## Core Units

### Prediction Model (`app/models.py`)
- `Prediction` SQLAlchemy model with columns: id, task_id, user_id, timestamp, status, symbol, interval, predictor_plugin, feeder_plugin, pipeline_plugin, prediction_type, ticker, result, prediction, uncertainty
- `to_dict()` serialization method
- Pydantic `PredictionRequest` model for validation
- Helper functions: `create_database_engine()`, `create_tables()`, `get_session()`

### Database Models (`app/database_models.py`)
- `User`: id, username, email, hashed_password, hashed_api_key, is_active, created_at, last_login, role_id
- `Role`: id, name, description, permissions (JSON)
- `PredictionJob`: id (UUID string), user_id, ticker, model_name, status, request_payload (JSON), result (JSON), error_message, processing_time_ms, created_at, updated_at, completed_at
- `ApiLog`: id, request_id, user_id, ip_address, user_agent, endpoint, method, request_payload, request_timestamp, response_status_code, response_time_ms, response_size_bytes
- `TimeSeriesData`: ticker+timestamp composite PK, OHLCV columns
- `SystemConfiguration`: key-value with JSON value
- `BillingRecord`: client_id, provider_id, prediction_id, cost, currency, description, timestamp
- `ProviderPricing`: provider_id, model_name, price_per_request, currency, is_active
- `UserSession`: id, user_id, ip_address, user_agent, created_at, last_activity, expires_at, is_active

### Authentication (`app/auth.py`)
- `verify_password(plain, hashed)` — bcrypt comparison
- `get_password_hash(password)` — bcrypt hashing
- `create_access_token(data, expires_delta)` — JWT encoding
- `generate_api_key()` — `secrets.token_urlsafe(32)`
- `hash_api_key(api_key)` — SHA-256 hash
- `authenticate_user(db, username, password)` — DB lookup + password verify
- `get_user_by_api_key(db, api_key)` — Hash and lookup
- `get_current_user(api_key, db)` — FastAPI dependency
- `require_role(roles)` — Returns dependency that checks user role
- Pre-built dependencies: `require_admin`, `require_client`, `require_provider`, `require_evaluator`, `require_operator`, `require_admin_or_operator`, `require_evaluator_or_admin`

### Plugin Loader (`app/plugin_loader.py`)
- `load_plugin(group, name)` → `(class, param_keys)` — Loads via `importlib.metadata.entry_points().select(group=group)`
- `get_plugin_params(group, name)` → `dict` — Returns `plugin_params` from plugin class

### Plugin Manager (`app/plugin_manager.py`)
- `PluginManager`: Simple name→instance registry with `register(plugin)` and `get(name)`

### Input Sanitization (`plugins_core/default_core.py`)
- `sanitize_input(value)` — HTML escape + regex removal of script/iframe/event handlers
- `sanitize_request_data(data)` — Recursive dict sanitization
- `validate_ticker(ticker)` — Alphanumeric with `.`, `-`, `_`; no dangerous chars

### Rate Limiter (`plugins_core/default_core.py`)
- `RateLimiter(max_requests, window_seconds)` — Sliding window rate limiter
- `is_allowed(key)` → bool — Checks and records request
- `auth_rate_limiter` — Global instance (3 requests/60s)

### Concurrent Prediction Tracking (`plugins_core/default_core.py`)
- `check_concurrent_predictions(user_id)` → bool
- `increment_concurrent_predictions(user_id)`
- `decrement_concurrent_predictions(user_id)`
- Thread-safe with `threading.Lock`

## Plugin Units

### DefaultFeeder
- `fetch()` → `pd.DataFrame` — Main data fetch (yfinance or file)
- `set_params(**kwargs)` — Update config
- Internal: `_load_file_data()`, `_load_normalization_params()`

### DefaultPipelinePlugin
- `initialize(predictor, feeder)` — Wire plugins
- `run_request(request)` → `dict` — Single prediction via feeder+predictor
- `run()` — Main loop
- `request_prediction()` → `int` — Create DB record
- Internal: `_run_single_cycle()`, `_store_prediction()`, `_update_prediction_status()`, `_validate_system()`

### DefaultPredictor
- `load_model(path)` → `bool` — Load Keras/sklearn model with caching
- `predict(input_data)` → `np.ndarray` — Basic prediction
- `predict_with_uncertainty(input_data, mc_samples)` → `dict` — MC-dropout
- `predict_request(input_df, request)` → `dict` — Ideal baseline predictor
- Internal: `_denormalize()`, `_configure_tensorflow()`, `_load_normalization_params()`, `_cache_model()`

### NoisyIdealPredictor
- `load_data(csv_file)` — Load OHLC CSV
- `predict_at(timestamp)` → `dict` — Predictions at specific time
- `generate_all_predictions()` → `{"hourly": DataFrame, "daily": DataFrame}` — All timestamps
- `predict(input_data)` → `dict` — Pipeline compatibility

### DefaultCorePlugin
- `set_plugins(plugins)` — Receive and wire all plugins
- `start()` — Run uvicorn
- `stop()` — Placeholder

## Pydantic Request/Response Models

### Core (`default_core.py`)
- `PredictionRequest`: symbol, ticker, interval, predictor_plugin, feeder_plugin, pipeline_plugin, prediction_type, model_name, prediction_horizon, baseline_datetime, horizons, date_column, target_column
- `PredictionResponse`: id, prediction_id, status, symbol, interval, plugins, ticker, task_id, result, model_name

### Client (`client_endpoints.py`)
- `PredictionRequest`: symbol (regex), prediction_type, datetime_requested (future), lookback_ticks, plugins, interval, prediction_horizon, priority, max_cost, notification_webhook, custom_parameters
- `PredictionResponse`, `DetailedPredictionResponse`, `PredictionListResponse`, `PredictionUpdate`

### Admin (`admin_endpoints.py`)
- `UserCreate`, `UserCreateResponse`, `UserUpdate`, `UserSummary`, `UserListResponse`
- `AuditLogEntry`, `AuditLogResponse`
- `SystemStatsResponse` (overview, financial, performance, evaluator, predictions, resources)
- `ConfigUpdate`, `SystemHealthResponse`

### Billing (`billing_endpoints.py`)
- `PricingCreate`, `PricingResponse`
- `BillingResponse`, `EarningsSummary`, `SpendSummary`

### Evaluator (`evaluator_endpoints.py`)
- `PendingRequestSummary`, `PendingRequestsResponse`
- `ClaimRequest`, `ClaimResponse`
- `SubmitRequest`, `SubmitResponse`
- `AssignedRequest`, `AssignedRequestsResponse`
- `ReleaseRequest`, `EvaluatorStats`

### User Management (`user_management.py`)
- `UserCreate`, `UserResponse`, `LoginRequest`, `TokenResponse`
- `ApiKeyResponse`, `PasswordChangeRequest`
- `UsageStats`, `LogEntry`, `LogsResponse`
