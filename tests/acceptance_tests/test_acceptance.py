import pytest
import requests
import uuid
import time
from fastapi.testclient import TestClient
from app.main import app  # Assuming your FastAPI app is in app/main.py

API_URL = "http://127.0.0.1:8000"
client = TestClient(app)

@pytest.mark.acceptance
def test_request_prediction():
    """
    Feature: Request a prediction for a financial instrument.
    Scenario: A user requests a prediction for a specific instrument.
    Given: The prediction provider service is running.
    When: A POST request is sent to /predict with a valid payload.
    Then: The service should accept the request and return a 202 status code,
          along with a prediction_id and a 'pending' status.
    """
    prediction_id = str(uuid.uuid4())
    payload = {
        "instrument": "EUR_USD",
        "timeframe": "H1",
        "prediction_id": prediction_id,
        "parameters": {
            "n_steps": 60,
            "plugin": "default_predictor"
        }
    }

    response = requests.post(f"{API_URL}/predict", json=payload)

    assert response.status_code == 202
    response_data = response.json()
    assert response_data["prediction_id"] == prediction_id
    assert response_data["status"] == "pending"
    assert "message" in response_data

@pytest.mark.acceptance
def test_get_prediction_status_and_result():
    """
    Feature: Retrieve the status and result of a prediction.
    Scenario: A user polls for the result of a previously requested prediction.
    Given: A prediction request has been successfully submitted.
    When: The user polls the /status/{prediction_id} endpoint.
    Then: The service should eventually return a 'completed' status
          and a valid prediction result.
    """
    prediction_id = str(uuid.uuid4())
    payload = {
        "instrument": "EUR_USD",
        "timeframe": "H1",
        "prediction_id": prediction_id,
        "parameters": {
            "n_steps": 60,
            "plugin": "default_predictor"
        }
    }

    post_response = requests.post(f"{API_URL}/predict", json=payload)
    assert post_response.status_code == 202
    
    status_url = f"{API_URL}/status/{prediction_id}"
    
    for _ in range(10):  # Poll for 10 seconds
        time.sleep(1)
        status_response = requests.get(status_url)
        if status_response.status_code == 200:
            status_data = status_response.json()
            if status_data["status"] == "completed":
                assert "prediction" in status_data
                assert "uncertainty" in status_data
                assert isinstance(status_data["prediction"], list)
                assert isinstance(status_data["uncertainty"], list)
                return  # Test successful
            elif status_data["status"] == "failed":
                pytest.fail(f"Prediction failed: {status_data.get('message', 'No message')}")
    
    pytest.fail("Prediction did not complete in time.")

def test_get_prediction_by_id_not_found():
    """
    Test retrieving a prediction with an ID that does not exist.
    """
    response = client.get("/api/v1/predictions/9999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Prediction not found"}

def test_delete_prediction():
    """
    Test deleting a prediction.
    """
    # First, create a prediction to delete
    prediction_data = {
        "symbol": "GOOGL",
        "interval": "1d",
        "predictor_plugin": "default_predictor",
        "feeder_plugin": "default_feeder",
        "pipeline_plugin": "default_pipeline"
    }
    response = client.post("/api/v1/predictions/", json=prediction_data)
    assert response.status_code == 201
    prediction_id = response.json()["id"]
    
    # Now, delete the prediction
    response = client.delete(f"/api/v1/predictions/{prediction_id}")
    assert response.status_code == 200
    assert response.json()["message"] == "Prediction deleted successfully"
    
    # Verify it's gone
    response = client.get(f"/api/v1/predictions/{prediction_id}")
    assert response.status_code == 404

def test_get_all_predictions_empty():
    """
    Test retrieving all predictions when none exist.
    """
    # Assuming a clean slate for this test
    response = client.get("/api/v1/predictions/")
    assert response.status_code == 200
    assert response.json() == []

def test_create_and_get_all_predictions():
    """
    Test creating multiple predictions and retrieving them all.
    """
    prediction_data_1 = {
        "symbol": "MSFT",
        "interval": "1h",
        "predictor_plugin": "default_predictor",
        "feeder_plugin": "default_feeder",
        "pipeline_plugin": "default_pipeline"
    }
    prediction_data_2 = {
        "symbol": "TSLA",
        "interval": "30m",
        "predictor_plugin": "default_predictor",
        "feeder_plugin": "default_feeder",
        "pipeline_plugin": "default_pipeline"
    }
    
    client.post("/api/v1/predictions/", json=prediction_data_1)
    client.post("/api/v1/predictions/", json=prediction_data_2)
    
    response = client.get("/api/v1/predictions/")
    assert response.status_code == 200
    assert len(response.json()) >= 2  # Use >= in case other tests left data

def test_get_plugins():
    """
    Test the endpoint for retrieving available plugins.
    """
    response = client.get("/api/v1/plugins/")
    assert response.status_code == 200
    plugins = response.json()
    assert "predictor_plugins" in plugins
    assert "feeder_plugins" in plugins
    assert "pipeline_plugins" in plugins
    assert "default_predictor" in plugins["predictor_plugins"]
    assert "default_feeder" in plugins["feeder_plugins"]
    assert "default_pipeline" in plugins["pipeline_plugins"]

def test_asynchronous_prediction_workflow(test_client):
    """
    Test the full asynchronous prediction workflow:
    1. Create a prediction request.
    2. Poll the status until the prediction is complete.
    3. Verify the final result.
    """
    # 1. Create a prediction request
    prediction_data = {
        "symbol": "NVDA",
        "interval": "1d",
        "predictor_plugin": "default_predictor",
        "feeder_plugin": "default_feeder",
        "pipeline_plugin": "default_pipeline"
    }
    response = test_client.post("/api/v1/predictions/", json=prediction_data)
    assert response.status_code == 201
    prediction_job = response.json()
    prediction_id = prediction_job["id"]
    assert prediction_job["status"] == "pending"

    # 2. Poll for completion
    timeout = 120  # 2 minutes
    start_time = time.time()
    final_prediction = None

    while time.time() - start_time < timeout:
        response = test_client.get(f"/api/v1/predictions/{prediction_id}")
        assert response.status_code == 200
        current_job = response.json()
        if current_job["status"] == "completed":
            final_prediction = current_job
            break
        elif current_job["status"] == "failed":
            pytest.fail(f"Prediction job {prediction_id} failed.")
        
        time.sleep(2)  # Wait 2 seconds between polls

    if final_prediction is None:
        pytest.fail("Prediction did not complete within the timeout period.")

    # 3. Verify the final result
    assert final_prediction is not None
    assert final_prediction["status"] == "completed"
    assert "result" in final_prediction
    assert final_prediction["result"] is not None
    assert "prediction" in final_prediction["result"]
    assert "uncertainty" in final_prediction["result"]

