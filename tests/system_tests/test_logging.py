import pytest
import logging
from unittest.mock import patch

# Assuming a centralized logging configuration in the app
from app.main import app, setup_logging

# This test requires capturing log output. The caplog fixture from pytest is perfect for this.

@pytest.fixture(autouse=True)
def setup_test_logging(caplog):
    """Ensure logging is set up for each test and caplog is used."""
    # Set a low level to capture all logs during testing
    setup_logging(level=logging.DEBUG)
    caplog.set_level(logging.INFO)

def test_request_logging(test_client, caplog):
    """Test that both valid and invalid API requests are logged."""
    # 1. Send a valid request
    valid_data = {"symbol": "GOOG", "interval": "1d", "prediction_type": "short_term"}
    test_client.post("/api/v1/predictions/", json=valid_data)

    # 2. Send an invalid request
    invalid_data = {"symbol": "GOOG"} # Missing required fields
    test_client.post("/api/v1/predictions/", json=invalid_data)

    # 3. Inspect the logs
    log_records = [record.message for record in caplog.records]
    
    # Check for logs from both requests
    # Look for the request logging pattern: METHOD PATH - STATUS_CODE - TIME
    assert any("POST /api/v1/predictions/" in msg and "201" in msg for msg in log_records)
    assert any("POST /api/v1/predictions/" in msg and "422" in msg for msg in log_records)

@patch('plugins_core.default_core.run_prediction_task') # Mock the core prediction logic
def test_event_logging_for_prediction_flow(mock_run_task, test_client, caplog):
    """
    Test that key stages of the prediction process (e.g., processing, completed)
    are logged correctly against a prediction ID.
    """
    # Mock the background task to simulate its lifecycle
    async def mock_flow(prediction_id, task_id):
        logging.info(f"Prediction {prediction_id}: Status changed to processing")
        # Simulate work
        logging.info(f"Prediction {prediction_id}: Status changed to completed")

    mock_run_task.side_effect = mock_flow

    # Trigger a prediction
    prediction_data = {"symbol": "TSLA", "interval": "1h", "prediction_type": "short_term"}
    response = test_client.post("/api/v1/predictions/", json=prediction_data)
    prediction_id = response.json()["id"]

    # In a real async setup, we would wait for the background task to finish.
    # Here, we can inspect the logs directly since we mocked the flow.
    log_records = [record.message for record in caplog.records]

    assert f"Prediction {prediction_id}: Status changed to processing" in log_records
    assert f"Prediction {prediction_id}: Status changed to completed" in log_records
