# Integration Design — As Built

## Integration Points

### 1. Plugin ↔ Core Integration

**How plugins are wired**:
- `main.py` loads plugins via entry points, calls `set_params()`, then passes all to `core.set_plugins(plugins)`
- Core's `set_plugins()` stores plugins in `self.plugins` and in `globals()["_LOADED_PLUGINS"]` for background task access
- Core calls `pipeline.initialize(predictor, feeder)` to wire the prediction flow

**Background task access**:
- `run_prediction_task_sync()` is a module-level function that reads `_LOADED_PLUGINS` from globals
- This is necessary because FastAPI `BackgroundTasks` runs outside the plugin instance scope

### 2. Database ↔ Application Integration

**Session management**: `get_db()` generator yields a `SessionLocal()` session per request via FastAPI `Depends()`.

**Two database model files**:
- `app/models.py` → `Prediction` table (used by core prediction endpoints)
- `app/database_models.py` → `User`, `Role`, `PredictionJob`, `ApiLog`, `TimeSeriesData`, `SystemConfiguration`, `BillingRecord`, `ProviderPricing`, `UserSession` (used by admin, client, evaluator, billing endpoints)

**Note**: `Prediction` (from `models.py`) and `PredictionJob` (from `database_models.py`) are separate tables serving different endpoint groups. Core endpoints use `Prediction`; client/evaluator marketplace endpoints use `PredictionJob`.

### 3. Feeder ↔ Pipeline Integration

- Pipeline calls `feeder.fetch()` → returns `pd.DataFrame`
- Enhanced pipeline can call `feeder.fetch_data_for_period(start_date, end_date, additional_previous_ticks)` if the feeder supports it
- Default feeder supports yfinance and CSV file sources

### 4. Pipeline ↔ Predictor Integration

- Pipeline calls `predictor.predict_request(input_df, request)` for API-triggered predictions
- Pipeline calls `predictor.predict_with_uncertainty(input_df)` for scheduled predictions
- Both methods return dicts with prediction data

### 5. Auth ↔ Endpoint Integration

- `get_current_user` dependency: extracts user from `X-API-KEY` header
- `optional_auth` dependency: returns user if API key provided, None otherwise (for flexible endpoints)
- `require_role(["admin"])` dependency: validates user role, returns 403 if insufficient
- Dependencies are composed via FastAPI's `Depends()` injection

### 6. Middleware ↔ Request Flow Integration

Middleware chain (applied to all requests):
1. CORS middleware adds headers
2. Rate limit middleware (currently pass-through)
3. Request logging middleware:
   - Reads request body for POST/PUT/PATCH on `/api/` paths
   - Resets `request._receive` so downstream can re-read body
   - After response: logs to Python logger and `api_logs` table
   - Resolves user_id from API key header if present

### 7. Router Integration

Multiple routers are registered on the FastAPI app:

```python
# From imports at top of default_core.py
app.include_router(client_router, prefix="/api/v1/client")
app.include_router(billing_router, prefix="/api/v1")

# From try/except block at bottom
app.include_router(user_router, prefix="/api/v1")
app.include_router(evaluator_router, prefix="/api/v1/evaluator")
app.include_router(client_router, prefix="/api/v1/client")  # registered twice
app.include_router(admin_router, prefix="/api/v1/admin")
```

**Note**: `client_router` is registered twice — once at the top and once at the bottom of `default_core.py`. The second registration adds duplicate routes but FastAPI handles this gracefully (first match wins).

### 8. External System Integration

- **yfinance**: Default feeder uses `yfinance` library for market data (optional dependency)
- **TensorFlow/Keras**: Default predictor loads `.keras`/`.h5` model files
- No external payment or notification systems integrated

### 9. Test Integration

- Tests use `fastapi.testclient.TestClient` with the `app` instance from `default_core.py`
- Database dependencies are overridden with in-memory SQLite
- `SKIP_BACKGROUND_TASKS=true` prevents actual prediction processing
- `SKIP_RATE_LIMITING=true` disables rate limiting in test fixtures
