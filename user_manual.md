# User Manual — Prediction Provider

## Overview

The Prediction Provider is a financial time series prediction marketplace with three primary roles:

- **Client**: Request predictions and pay for them
- **Provider**: Register models, set pricing, earn from predictions
- **Admin**: Manage users, billing, and system configuration

## Getting Started

### 1. Registration & Activation

Users are created by an administrator:

```bash
# Admin creates your account
curl -X POST http://localhost:8000/api/v1/admin/users \
  -H "X-API-KEY: <admin-key>" \
  -H "Content-Type: application/json" \
  -d '{"username": "yourname", "email": "you@example.com", "role": "client"}'
```

The response includes an `api_key`. Save it — you'll need it for all authenticated requests.

Your account starts **inactive**. An admin must activate it:

```bash
curl -X POST http://localhost:8000/api/v1/admin/users/yourname/activate \
  -H "X-API-KEY: <admin-key>"
```

### 2. Authentication

Use your API key in all requests:

```bash
curl -H "X-API-KEY: your-api-key-here" http://localhost:8000/api/v1/users/profile
```

To get a new API key (if you know your password):

```bash
curl -X POST http://localhost:8000/api/v1/auth/api-key \
  -H "Content-Type: application/json" \
  -d '{"username": "yourname", "password": "password"}'
```

Default password for new accounts is `password`. Change it immediately:

```bash
curl -X PUT http://localhost:8000/api/v1/users/password \
  -H "X-API-KEY: your-key" \
  -H "Content-Type: application/json" \
  -d '{"old_password": "password", "new_password": "your-secure-password"}'
```

---

## For Clients

### Requesting Predictions

#### Simple Prediction (Public Endpoint)

No authentication required by default:

```bash
curl -X POST http://localhost:8000/api/v1/predict \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "prediction_type": "short_term",
    "prediction_horizon": 6
  }'
```

#### Authenticated Prediction

Using your API key links the prediction to your account:

```bash
curl -X POST http://localhost:8000/api/v1/predict \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: your-key" \
  -d '{
    "symbol": "MSFT",
    "prediction_type": "short_term",
    "interval": "1h",
    "predictor_plugin": "default_predictor",
    "feeder_plugin": "default_feeder",
    "prediction_horizon": 6
  }'
```

#### Marketplace Prediction (Client Endpoint)

For the full marketplace experience with cost estimates, queuing, and evaluator matching:

```bash
curl -X POST http://localhost:8000/api/v1/client/predict \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: your-key" \
  -d '{
    "symbol": "AAPL",
    "prediction_type": "short_term",
    "datetime_requested": "2025-06-01T12:00:00Z",
    "lookback_ticks": 1000,
    "prediction_horizon": 6,
    "interval": "1h",
    "priority": 5,
    "max_cost": 10.00
  }'
```

### Checking Prediction Status

```bash
# By prediction ID
curl http://localhost:8000/api/v1/predictions/1

# List all your predictions
curl -H "X-API-KEY: your-key" http://localhost:8000/api/v1/predictions/

# Detailed marketplace prediction status
curl -H "X-API-KEY: your-key" http://localhost:8000/api/v1/client/predictions/<uuid>
```

### Cancelling a Prediction

Only pending predictions can be cancelled:

```bash
curl -X DELETE http://localhost:8000/api/v1/client/predictions/<uuid> \
  -H "X-API-KEY: your-key"
```

### Viewing Spend

```bash
curl -H "X-API-KEY: your-key" "http://localhost:8000/api/v1/client/spend?days=30"
```

---

## For Providers

### Setting Model Pricing

```bash
curl -X POST http://localhost:8000/api/v1/provider/pricing \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: your-provider-key" \
  -d '{
    "model_name": "my_lstm_model",
    "price_per_request": 0.25,
    "currency": "USD"
  }'
```

Setting new pricing for an existing model deactivates the previous pricing.

### Viewing Pricing

```bash
curl -H "X-API-KEY: your-provider-key" http://localhost:8000/api/v1/provider/pricing
```

### Viewing Earnings

```bash
curl -H "X-API-KEY: your-provider-key" "http://localhost:8000/api/v1/provider/earnings?days=30"
```

---

## For Administrators

### Creating Users

```bash
curl -X POST http://localhost:8000/api/v1/admin/users \
  -H "X-API-KEY: admin-key" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newclient",
    "email": "client@example.com",
    "role": "client"
  }'
```

Available roles: `client`, `provider`, `evaluator`, `administrator`, `operator`, `guest`

### Activating / Deactivating Users

```bash
# Activate
curl -X POST http://localhost:8000/api/v1/admin/users/newclient/activate \
  -H "X-API-KEY: admin-key"

# Deactivate
curl -X POST http://localhost:8000/api/v1/admin/users/newclient/deactivate \
  -H "X-API-KEY: admin-key"
```

### Viewing All Users

```bash
curl -H "X-API-KEY: admin-key" http://localhost:8000/api/v1/admin/users
```

### Viewing Usage Stats

```bash
curl -H "X-API-KEY: admin-key" http://localhost:8000/api/v1/admin/usage/newclient
```

### Viewing System Logs

```bash
curl -H "X-API-KEY: admin-key" "http://localhost:8000/api/v1/admin/logs?hours=24"
```

**Note**: Audit logs cannot be deleted or modified (returns 405).

### Billing Management

```bash
# All billing records
curl -H "X-API-KEY: admin-key" http://localhost:8000/api/v1/admin/billing

# Billing summary
curl -H "X-API-KEY: admin-key" "http://localhost:8000/api/v1/admin/billing/summary?days=30"

# All active pricing
curl -H "X-API-KEY: admin-key" http://localhost:8000/api/v1/admin/pricing
```

---

## Configuration Options

### Running the Server

```bash
# Default
prediction_provider

# Custom host/port
prediction_provider --host 0.0.0.0 --port 8080

# With config file
prediction_provider --load_config my_config.json

# Quiet mode (suppress verbose output)
PREDICTION_PROVIDER_QUIET=1 prediction_provider
```

### Config File Example

```json
{
  "host": "0.0.0.0",
  "port": 8000,
  "feeder_plugin": "default_feeder",
  "predictor_plugin": "default_predictor",
  "pipeline_plugin": "default_pipeline",
  "instrument": "MSFT",
  "prediction_horizon": 6,
  "data_source": "file",
  "data_file_path": "data/eurusd_hourly.csv"
}
```

### Using the Noisy Ideal Predictor

For noise-sweep experiments:

```json
{
  "predictor_plugin": "noisy_ideal_predictor",
  "csv_file": "data/eurusd_hourly.csv",
  "noise_std": 0.5,
  "noise_seed": 42,
  "hourly_horizons": 6,
  "daily_horizons": 6
}
```

---

## API Documentation (Interactive)

When the server is running, access the auto-generated Swagger docs at:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
