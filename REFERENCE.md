# API Reference

Complete API reference for the Prediction Provider. All endpoints are served by FastAPI on the configured host/port (default `http://localhost:8000`).

## Authentication

Two authentication mechanisms:

1. **API Key**: `X-API-KEY` header with a valid key obtained from `/api/v1/auth/api-key`
2. **JWT Bearer Token**: `Authorization: Bearer <token>` obtained from `/api/v1/auth/login`

Flexible endpoints accept both authenticated and unauthenticated requests (unless `REQUIRE_AUTH=true`).

---

## Root & Health

### `GET /`

Root endpoint with API information.

**Auth**: None

**Response** `200`:
```json
{"message": "Prediction Provider API", "version": "0.1.0", "docs": "/docs"}
```

### `GET /health`

Health check.

**Auth**: None

**Response** `200`:
```json
{"status": "ok"}
```

---

## Authentication Endpoints

### `POST /api/v1/auth/login`

Login with username and password.

**Auth**: None  
**Rate Limit**: 3 attempts per 60 seconds per IP

**Request Body**:
```json
{"username": "string", "password": "string"}
```

**Response** `200`:
```json
{"access_token": "string", "token_type": "bearer"}
```

**Errors**: `401` Invalid credentials or inactive account, `429` Rate limited

### `POST /api/v1/auth/api-key`

Get an API key for authentication.

**Auth**: None (authenticates via body)

**Request Body**:
```json
{"username": "string", "password": "string"}
```

**Response** `200`:
```json
{"api_key": "string", "expires_in_days": 90}
```

**Errors**: `401` Invalid credentials or inactive account

### `POST /api/v1/auth/regenerate-key`

Regenerate API key for current user.

**Auth**: API Key required

**Response** `200`:
```json
{"api_key": "string", "expires_in_days": 90}
```

---

## Prediction Endpoints (Flexible Auth)

These endpoints work with or without authentication. When `REQUIRE_AUTH=true`, API key is required. When a valid API key is provided, predictions are associated with the user.

### `POST /api/v1/predict`

Create a new prediction.

**Auth**: Optional (API Key)

**Request Body**:
```json
{
  "symbol": "AAPL",
  "ticker": "AAPL",
  "interval": "1d",
  "predictor_plugin": "default_predictor",
  "feeder_plugin": "default_feeder",
  "pipeline_plugin": "default_pipeline",
  "prediction_type": "short_term",
  "model_name": "default_predictor",
  "prediction_horizon": 1,
  "baseline_datetime": "2024-01-01T00:00:00",
  "horizons": [1, 2, 3],
  "date_column": "DATE_TIME",
  "target_column": "CLOSE"
}
```

Required: either `symbol` or `ticker` must be provided.

`prediction_type` must be one of: `short_term`, `long_term`, `medium_term`.

**Response** `201`:
```json
{
  "id": 1,
  "prediction_id": 1,
  "status": "pending",
  "symbol": "AAPL",
  "interval": "1d",
  "predictor_plugin": "default_predictor",
  "feeder_plugin": "default_feeder",
  "pipeline_plugin": "default_pipeline",
  "prediction_type": "short_term",
  "ticker": "AAPL",
  "task_id": "uuid-string",
  "result": {},
  "model_name": "default_predictor"
}
```

**Errors**: `401` Invalid API key (if provided), `403` Admin users cannot create predictions, `429` Too many concurrent predictions, `500` Server error

### `POST /api/v1/predictions/`

Alias for creating predictions with flexible auth.

Same request/response as `POST /api/v1/predict`.

### `GET /api/v1/predictions/`

List all predictions.

**Auth**: Optional. Authenticated clients see own predictions only; admins see all; unauthenticated sees all.

**Response** `200`: Array of prediction objects.

### `GET /api/v1/predictions/{prediction_id}`

Get prediction by ID.

**Auth**: Optional. Authenticated non-admin users can only access own predictions.

**Response** `200`: Prediction object  
**Errors**: `403` Access denied, `404` Not found

### `DELETE /api/v1/predictions/{prediction_id}`

Delete a prediction.

**Auth**: Optional. Authenticated non-admin users can only delete own predictions.

**Response** `200`:
```json
{"message": "Prediction deleted successfully"}
```

**Errors**: `403` Access denied, `404` Not found

---

## Secure Prediction Endpoints

Require authentication via API Key.

### `POST /api/v1/secure/predictions/`

Create prediction (requires authentication).

**Auth**: API Key required

Same request/response format as `POST /api/v1/predict`, status `201`.

### `GET /api/v1/secure/predictions/`

List own predictions (admin sees all).

**Auth**: API Key required

### `GET /api/v1/secure/predictions/{prediction_id}`

Get prediction (own or admin).

**Auth**: API Key required  
**Errors**: `403` Access denied, `404` Not found

### `DELETE /api/v1/secure/predictions/{prediction_id}`

Delete prediction (own or admin).

**Auth**: API Key required  
**Errors**: `403` Access denied, `404` Not found

### `POST /api/v1/auth/predictions/`

Create prediction (authenticated).

**Auth**: API Key required. Same as secure endpoint.

---

## User Profile Endpoints

### `GET /api/v1/users/profile`

Get current user profile.

**Auth**: API Key required

**Response** `200`:
```json
{
  "id": 1,
  "username": "string",
  "email": "string",
  "is_active": true,
  "role": "client",
  "created_at": "2024-01-01T00:00:00"
}
```

### `PUT /api/v1/users/password`

Change password.

**Auth**: API Key required

**Request Body**:
```json
{"old_password": "string", "new_password": "string"}
```

**Response** `200`:
```json
{"message": "Password changed successfully"}
```

**Errors**: `400` Invalid old password or missing fields

### `PUT /api/v1/users/profile`

Update profile. Users cannot change their own role.

**Auth**: API Key required

**Request Body**:
```json
{"email": "newemail@example.com"}
```

**Errors**: `400` Email exists, `403` Cannot change role

---

## Admin Endpoints (Core)

### `POST /api/v1/admin/users`

Create a new user.

**Auth**: API Key required, `administrator`/`admin` role

**Request Body**:
```json
{"username": "string", "email": "string", "role": "client"}
```

New users are created with default password `"password"`, `is_active=False`.

**Response** `201`:
```json
{
  "id": 1,
  "username": "string",
  "email": "string",
  "is_active": false,
  "role": "client",
  "created_at": "2024-01-01T00:00:00",
  "api_key": "generated-api-key"
}
```

**Errors**: `400` Username/email exists or invalid role

### `POST /api/v1/admin/users/{username}/activate`

Activate a user account.

**Auth**: `administrator`/`admin`

**Response** `200`:
```json
{"message": "User {username} activated successfully"}
```

### `POST /api/v1/admin/users/{username}/deactivate`

Deactivate a user account.

**Auth**: `administrator`/`admin`

### `GET /api/v1/admin/users`

List all users.

**Auth**: `administrator`/`admin`

**Response** `200`: Array of user objects.

### `GET /api/v1/admin/logs`

Get system logs.

**Auth**: Any authenticated user (note: in core; admin router requires admin)

**Query Parameters**:
- `user` (str, optional): Filter by username
- `endpoint` (str, optional): Filter by endpoint
- `hours` (int, default 24): Time window

**Response** `200`:
```json
{
  "logs": [{"id": 1, "request_id": "uuid", "user_id": 1, "ip_address": "...", "endpoint": "...", "method": "POST", "request_timestamp": "...", "response_status_code": 200, "response_time_ms": 10.5}],
  "total": 1
}
```

### `GET /api/v1/admin/usage/{username}`

Get usage statistics.

**Auth**: `administrator`/`admin`/`operator`

**Response** `200`:
```json
{
  "username": "string",
  "total_requests": 100,
  "total_predictions": 50,
  "total_processing_time_ms": 5000.0,
  "cost_estimate": 5.0
}
```

### `DELETE /api/v1/admin/logs/{log_id}`

**Always returns** `405` — audit logs cannot be deleted.

### `PUT /api/v1/admin/logs/{log_id}`

**Always returns** `405` — audit logs cannot be modified.

---

## Admin Router Endpoints (`/api/v1/admin/`)

These are from `admin_endpoints.py`, providing richer admin functionality.

### `POST /api/v1/admin/users` (admin router)

Create user with full options.

**Auth**: `administrator`

**Request Body**:
```json
{
  "username": "string",
  "email": "string",
  "password": "string",
  "role": "client|evaluator|administrator|guest",
  "subscription_tier": "basic|premium|enterprise",
  "is_active": true,
  "initial_credits": 0.0,
  "billing_address": {}
}
```

**Response** `200`:
```json
{"id": 1, "username": "string", "email": "string", "role": "client", "api_key": "string", "created_at": "..."}
```

**Errors**: `409` Username/email exists, `400` Invalid role

### `GET /api/v1/admin/users` (admin router)

List users with filtering.

**Query Parameters**: `role`, `is_active`, `subscription_tier`, `created_after`, `search`, `limit` (1-100), `offset`

**Response** `200`:
```json
{
  "users": [{"id": 1, "username": "...", "email": "...", "role": "...", "subscription_tier": "basic", "is_active": true, "total_predictions": 0, "total_spent": 0.0, ...}],
  "total_count": 1,
  "active_users": 1,
  "new_users_this_month": 1
}
```

### `PUT /api/v1/admin/users/{user_id}`

Update user.

**Request Body**:
```json
{"is_active": true, "role": "client", "subscription_tier": "premium"}
```

### `DELETE /api/v1/admin/users/{user_id}`

Deactivate or delete user.

**Query**: `action=deactivate|delete`, `notify_user=true`

**Error**: `400` Cannot deactivate own account

### `GET /api/v1/admin/audit`

Audit logs with comprehensive filtering.

**Query**: `user_id`, `action`, `start_date`, `end_date`, `endpoint`, `method`, `status_code`, `risk_score_min`, `limit`, `offset`

### `GET /api/v1/admin/stats`

System statistics.

**Query**: `period=1d|7d|30d`, `include_forecasts=true`

Returns: `system_overview`, `financial_metrics`, `performance_metrics`, `evaluator_performance`, `predictions`, `resource_utilization`

### `POST /api/v1/admin/config`

Update system configuration.

**Request Body**:
```json
{"prediction_timeout": 300, "max_concurrent_predictions": 10, "rate_limits": {}, "default_plugins": {}}
```

### `GET /api/v1/admin/system/health`

Detailed system health.

Returns: `overall_status`, `components` (database, redis_cache, plugin_system), `alerts`, `last_backup`, `disk_space`

---

## Billing & Provider Endpoints

### `POST /api/v1/provider/pricing`

Set pricing for a model.

**Auth**: `provider`/`administrator`/`admin`

**Request Body**:
```json
{"model_name": "string", "price_per_request": 0.10, "currency": "USD"}
```

**Response** `201`: Pricing object

### `GET /api/v1/provider/pricing`

Get own active pricing.

**Auth**: `provider`/`administrator`/`admin`

### `GET /api/v1/provider/earnings`

Provider earnings summary.

**Auth**: `provider`/`administrator`/`admin`

**Query**: `days` (1-365, default 30)

**Response** `200`:
```json
{"total_earnings": 100.0, "currency": "USD", "total_requests": 50, "period_days": 30}
```

### `GET /api/v1/client/spend`

Client spending summary.

**Auth**: `client`/`administrator`/`admin`

**Query**: `days` (1-365, default 30)

### `GET /api/v1/client/billing`

Client billing history.

**Auth**: `client`/`administrator`/`admin`

**Query**: `limit` (1-500, default 50)

### `GET /api/v1/admin/billing`

All billing records.

**Auth**: `administrator`/`admin`

### `GET /api/v1/admin/billing/summary`

Billing summary.

**Auth**: `administrator`/`admin`

**Query**: `days` (1-365, default 30)

**Response** `200`:
```json
{"total_revenue": 500.0, "total_transactions": 100, "unique_clients": 10, "unique_providers": 5, "period_days": 30, "currency": "USD"}
```

### `GET /api/v1/admin/pricing`

All active pricing.

**Auth**: `administrator`/`admin`

---

## Client Endpoints (`/api/v1/client/`)

### `POST /api/v1/client/predict`

Submit a marketplace prediction request.

**Auth**: `client`/`administrator`

**Request Body**:
```json
{
  "symbol": "AAPL",
  "prediction_type": "short_term|long_term|custom",
  "datetime_requested": "2025-01-01T00:00:00Z",
  "lookback_ticks": 1000,
  "predictor_plugin": "default_predictor",
  "feeder_plugin": "default_feeder",
  "pipeline_plugin": "default_pipeline",
  "interval": "1h|1d|1w|1M",
  "prediction_horizon": 6,
  "priority": 5,
  "max_cost": 10.0,
  "notification_webhook": "https://...",
  "custom_parameters": {}
}
```

Symbol must match `^[A-Z]{3,6}$`. `datetime_requested` must be in the future.

**Errors**: `429` Max concurrent predictions exceeded, `402` Cost exceeds max_cost

### `GET /api/v1/client/predictions/{id}`

Detailed prediction with progress, evaluator info, cost, results.

### `GET /api/v1/client/predictions/`

List with pagination and filtering.

**Query**: `status`, `symbol`, `prediction_type`, `start_date`, `end_date`, `limit`, `offset`, `sort` (created_at|completed_at|priority|cost), `order` (asc|desc)

### `PUT /api/v1/client/predictions/{id}`

Update pending prediction (priority, max_cost, webhook).

### `DELETE /api/v1/client/predictions/{id}`

Cancel pending prediction. Returns refund amount.

### `GET /api/v1/client/predictions/{id}/download/{file_type}`

Download result files. Allowed types: `results.csv`, `plot.png`, `metadata.json`, `logs.txt`.

**Note**: Currently returns placeholder response — file streaming not implemented.

---

## Evaluator Endpoints (`/api/v1/evaluator/`)

### `GET /api/v1/evaluator/pending`

List pending requests available for processing.

**Auth**: `evaluator`/`administrator`

**Query**: `prediction_type`, `symbol`, `min_priority`, `max_priority`, `min_payment`, `max_payment`, `predictor_plugin`, `sort`, `order`, `limit`

### `POST /api/v1/evaluator/claim/{request_id}`

Claim a pending request.

**Request Body**:
```json
{"estimated_completion": "2025-01-01T01:00:00Z", "processing_node_info": {}}
```

Returns processing details with 30-minute timeout.

**Errors**: `404` Not found/already claimed, `410` Expired

### `POST /api/v1/evaluator/submit/{request_id}`

Submit results for a claimed request.

**Request Body**:
```json
{
  "predictions": [1.0, 2.0],
  "uncertainties": [0.1, 0.2],
  "confidence_intervals": {"95": [0.8, 1.8]},
  "model_metadata": {},
  "processing_log": "string",
  "resource_usage": {},
  "quality_metrics": {}
}
```

Returns quality score, payment, bonus, performance rating.

**Errors**: `403` Not authorized, `408` Timeout exceeded

### `GET /api/v1/evaluator/assigned`

List assigned requests with time remaining.

### `POST /api/v1/evaluator/release/{request_id}`

Release request back to queue.

**Request Body**:
```json
{"reason": "insufficient_resources|technical_issue|other", "details": "string"}
```

### `GET /api/v1/evaluator/stats`

Performance statistics.

**Query**: `period=7d|30d|90d`, `include_rankings=true`

---

## Plugin Endpoints

### `GET /api/v1/plugins/`

List available plugins.

**Response** `200`:
```json
{
  "feeder_plugins": ["default_feeder"],
  "predictor_plugins": ["default_predictor"],
  "pipeline_plugins": ["default_pipeline"],
  "endpoint_plugins": ["predict_endpoint", "health_endpoint"],
  "core_plugins": ["default_core"]
}
```

### `GET /api/v1/plugins/status`

Plugin status.

**Response** `200`:
```json
{
  "plugins": {"core": {"status": "active"}, "feeder": {"status": "active"}, ...},
  "total_plugins": 4,
  "system_status": "operational"
}
```

---

## Legacy Endpoints

### `POST /predict`

Legacy prediction endpoint.

**Request Body**:
```json
{"instrument": "EUR_USD", "timeframe": "H1", "parameters": {"plugin": "default_predictor"}}
```

**Response** `200`:
```json
{"prediction_id": "uuid", "status": "pending", "message": "Prediction request accepted"}
```

### `GET /status/{prediction_id}`

Legacy status check.

---

## Utility Endpoints

### `POST /test/reset-rate-limit`

Reset rate limit store (testing only).

### `OPTIONS /api/v1/predict`

CORS preflight handler.

---

## Common Error Codes

| Code | Meaning |
|---|---|
| `400` | Bad request / validation error |
| `401` | Authentication failed |
| `402` | Cost exceeds maximum |
| `403` | Insufficient permissions |
| `404` | Resource not found |
| `405` | Method not allowed (audit log protection) |
| `408` | Request timeout |
| `409` | Conflict (e.g., updating non-pending prediction) |
| `410` | Resource expired |
| `429` | Rate limited / too many concurrent requests |
| `500` | Internal server error |
