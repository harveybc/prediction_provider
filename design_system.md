# System Design — As Built

## Architecture

The Prediction Provider is a FastAPI-based web application with a plugin architecture for modular data feeding, prediction, and pipeline orchestration.

### Component Diagram

```
                    ┌──────────────────────────────────────┐
                    │            FastAPI App                │
                    │       (default_core.py)               │
                    │                                      │
                    │  ┌─────────┐  ┌──────────────────┐   │
                    │  │ Middleware│  │   Route Handlers  │   │
                    │  │ - CORS   │  │ - /api/v1/predict │   │
                    │  │ - Logging│  │ - /api/v1/admin/* │   │
                    │  │ - Rate   │  │ - /api/v1/client/*│   │
                    │  │   Limit  │  │ - /api/v1/eval/*  │   │
                    │  └─────────┘  │ - /api/v1/billing/*│   │
                    │               └──────────────────┘   │
                    └──────────┬───────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
    ┌─────────▼──┐   ┌────────▼───┐   ┌───────▼────────┐
    │   Feeder   │   │  Pipeline  │   │   Predictor    │
    │  Plugin    │──▶│  Plugin    │──▶│   Plugin       │
    │            │   │            │   │                │
    │ - yfinance │   │ - fetch()  │   │ - Keras models │
    │ - CSV file │   │ - predict()│   │ - MC-dropout   │
    └────────────┘   │ - store()  │   │ - Ideal/Noisy  │
                     └──────┬─────┘   └────────────────┘
                            │
                     ┌──────▼─────┐
                     │  SQLite DB │
                     │            │
                     │ - users    │
                     │ - roles    │
                     │ - predict. │
                     │ - api_logs │
                     │ - billing  │
                     └────────────┘
```

### Plugin Loading

Plugins are discovered via Python entry points (`setup.py`). At startup:

1. `main.py` parses CLI args and loads config
2. For each plugin type (core, endpoints, feeder, pipeline, predictor):
   - `plugin_loader.load_plugin()` finds the entry point
   - Instantiates the plugin class with config
   - Calls `set_params()` with merged config
3. Core plugin receives all plugins via `set_plugins()`
4. Pipeline is initialized with predictor + feeder
5. Core starts uvicorn server

### Request Flow

**Prediction Request** (`POST /api/v1/predict`):
1. Rate limit middleware checks
2. Request logging middleware captures metadata
3. Optional authentication resolves user from API key
4. Input validation via Pydantic model
5. Input sanitization (XSS prevention)
6. Prediction record created in DB (status: pending)
7. Background task spawned via `BackgroundTasks`
8. Response returned immediately (201)
9. Background: pipeline calls `feeder.fetch()` → `predictor.predict_request(df, request)`
10. Result stored in DB, status updated to completed/failed

### Database

SQLAlchemy ORM with SQLite. Connection managed via `SessionLocal` generator pattern (`get_db()`). Tables auto-created on import of `default_core.py`.

Key relationships:
- `User` → `Role` (many-to-one via `role_id`)
- `User` → `Prediction` (one-to-many via `user_id`)
- `User` → `PredictionJob` (one-to-many via `user_id`)
- `User` → `ApiLog` (one-to-many via `user_id`)
- `BillingRecord` → `User` (client_id, provider_id)
- `ProviderPricing` → `User` (provider_id)

### Authentication Flow

```
Client ──▶ X-API-KEY header ──▶ hash_api_key(SHA-256) ──▶ lookup users.hashed_api_key
                                                           ├── Found + active → User object
                                                           ├── Found + inactive → 403
                                                           └── Not found → 403 (or pass-through for flexible auth)
```

### Middleware Stack (order of execution)

1. **CORS middleware** — handles cross-origin requests
2. **Rate limit middleware** — currently disabled (pass-through)
3. **Request logging middleware** — logs to Python logger + `api_logs` table

### Background Task Execution

Predictions use FastAPI's `BackgroundTasks` for async processing:

```python
def run_prediction_task_sync(prediction_id, task_id, user_id=None):
    # 1. Mark prediction as "processing"
    # 2. Get pipeline plugin from globals
    # 3. Call pipeline.run_request(request_payload)
    # 4. Store result, mark "completed"
    # 5. On error: mark "failed"
    # 6. Decrement concurrent prediction count
```

### Security Layers

1. **Transport**: CORS (currently permissive)
2. **Authentication**: API key (SHA-256) or JWT (HS256)
3. **Authorization**: Role-based with `require_role()` dependency injection
4. **Input validation**: Pydantic models with regex validators
5. **Input sanitization**: HTML escaping, script removal, ticker validation
6. **Rate limiting**: Login attempts (3/60s), concurrent predictions (10/user)
7. **Audit**: All API requests logged, logs immutable (405 on DELETE/PUT)
