# Behavioral Testing Guide

## Overview

Behavioral tests verify user workflows and interaction patterns against expected system behavior. Located in `tests/behavioral_tests/`.

## Test File

### `test_user_behavior.py`

Tests user behavior patterns including:

- **Registration flow**: Admin creates user → user gets API key → user authenticates
- **Prediction workflow**: Client creates prediction → checks status → retrieves results
- **Multi-role interactions**: Admin manages users, clients request predictions, evaluators process them
- **Error handling behavior**: Invalid inputs, unauthorized access, rate limiting responses

## Running

```bash
PREDICTION_PROVIDER_QUIET=1 pytest tests/behavioral_tests/ -v
```

## Fixtures

`tests/behavioral_tests/conftest.py` provides:
- Pre-configured test database with roles and users
- TestClient with appropriate dependency overrides
- API keys for different user roles

## Writing Behavioral Tests

Behavioral tests should:
1. Simulate a complete user journey (not isolated units)
2. Use the HTTP API (via TestClient), not internal functions
3. Verify both success paths and error paths
4. Test state transitions (e.g., user inactive → active → can authenticate)

```python
def test_client_prediction_workflow(client, client_api_key):
    """Test the complete client prediction workflow."""
    # 1. Create prediction
    response = client.post("/api/v1/predict", 
        json={"symbol": "AAPL", "prediction_type": "short_term"},
        headers={"X-API-KEY": client_api_key})
    assert response.status_code == 201
    
    # 2. Check it exists
    pred_id = response.json()["id"]
    response = client.get(f"/api/v1/predictions/{pred_id}",
        headers={"X-API-KEY": client_api_key})
    assert response.status_code == 200
    assert response.json()["status"] in ["pending", "processing", "completed"]
```
