import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# from app.main import app
# client = TestClient(app)

# Note: We will use the client fixture from conftest.py

@patch('app.main.celery.send_task')
def test_create_prediction_endpoint(mock_send_task, client: TestClient):
    """
    Tests the POST /predict/ endpoint.
    It should accept a valid request, create a task, and return a 202 response.
    """
    mock_send_task.return_value = MagicMock(id="some-task-id")

    response = client.post(
        "/predict/",
        json={"prediction_type": "long_term", "datetime": "2025-01-01T00:00:00Z"}
    )

    assert response.status_code == 202
    assert "task_id" in response.json()
    assert response.json()["task_id"] == "some-task-id"

    # Verify that the background task was called correctly
    mock_send_task.assert_called_once_with(
        "app.main.run_prediction_pipeline",
        args=[{"prediction_type": "long_term", "datetime": "2025-01-01T00:00:00Z"}]
    )

def test_get_prediction_status_endpoint(client: TestClient):
    """
    Tests the GET /predict/{task_id} endpoint.
    This test will mock the celery result backend.
    """
    task_id = "some-existing-task-id"

    # Mock the AsyncResult to simulate different task states
    with patch('app.main.celery.AsyncResult') as mock_async_result:
        # 1. Test PENDING state
        mock_result_pending = MagicMock()
        mock_result_pending.state = 'PENDING'
        mock_async_result.return_value = mock_result_pending

        response_pending = client.get(f"/predict/{task_id}")
        assert response_pending.status_code == 200
        assert response_pending.json() == {"status": "PENDING"}

        # 2. Test COMPLETED state
        mock_result_completed = MagicMock()
        mock_result_completed.state = 'SUCCESS' # Celery uses SUCCESS for completed
        mock_result_completed.result = (123.45, 0.5)
        mock_async_result.return_value = mock_result_completed

        response_completed = client.get(f"/predict/{task_id}")
        assert response_completed.status_code == 200
        assert response_completed.json() == {
            "status": "COMPLETED",
            "prediction": 123.45,
            "uncertainty": 0.5
        }

        # 3. Test FAILED state
        mock_result_failed = MagicMock()
        mock_result_failed.state = 'FAILURE'
        mock_async_result.return_value = mock_result_failed

        response_failed = client.get(f"/predict/{task_id}")
        assert response_failed.status_code == 200
        assert response_failed.json() == {"status": "FAILED"}

def test_list_plugins_endpoint(client: TestClient):
    """
    Tests the GET /plugins/ endpoint.
    It should return a list of available plugins, categorized by type.
    """
    # This test might need to be adjusted based on the actual plugin loading implementation
    # For now, we assume a static or discoverable list of plugins.
    response = client.get("/plugins/")
    assert response.status_code == 200
    plugins = response.json()

    assert "feeder" in plugins
    assert "predictor" in plugins
    assert "pipeline" in plugins
    # Example assertion for a default plugin
    assert "default_feeder" in plugins["feeder"]
