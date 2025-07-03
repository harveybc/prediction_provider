"""
Acceptance tests for the Prediction Provider API.
"""
import pytest
import requests
import time
import subprocess
import os

# Define the base URL for the API
BASE_URL = "http://localhost:5000"

@pytest.fixture(scope="module")
def running_service():
    """
    Fixture to start and stop the prediction provider service for the test module.
    """
    # Command to run the main application
    command = ["python3", "app/main.py"]
    
    # Start the service as a subprocess
    process = subprocess.Popen(command, cwd="/home/harveybc/Documents/GitHub/prediction_provider")
    
    # Wait for the service to be ready
    # In a real scenario, you'd poll the /health endpoint until it's 200
    time.sleep(10)
    
    yield
    
    # Teardown: stop the service
    process.terminate()
    process.wait()

def test_health_endpoint(running_service):
    """
    GIVEN a running prediction provider service
    WHEN the /health endpoint is requested
    THEN it should return a 200 OK status and a healthy status message.
    """
    response = requests.get(f"{BASE_URL}/health")
    assert response.status_code == 200
    json_response = response.json()
    assert json_response["pipeline_running"] is True
    assert json_response["system_ready"] is True

def test_info_endpoint(running_service):
    """
    GIVEN a running prediction provider service
    WHEN the /info endpoint is requested
    THEN it should return a 200 OK status and debug information.
    """
    response = requests.get(f"{BASE_URL}/info")
    assert response.status_code == 200
    json_response = response.json()
    assert "pipeline_enabled" in json_response
    assert "db_path" in json_response

def test_get_predictions_endpoint(running_service):
    """
    GIVEN a running prediction provider service that has had time to generate predictions
    WHEN the /predictions endpoint is requested
    THEN it should return a 200 OK status and a list of predictions.
    """
    # Wait for at least one prediction cycle to complete
    time.sleep(15) # Assuming a short prediction interval for testing
    
    response = requests.get(f"{BASE_URL}/predictions")
    assert response.status_code == 200
    json_response = response.json()
    assert isinstance(json_response, list)
    # Check if the list is not empty (assuming the pipeline runs and stores something)
    assert len(json_response) > 0
    # Check the structure of the first prediction
    prediction = json_response[0]
    assert "prediction_timestamp" in prediction
    assert "prediction" in prediction
    assert "uncertainty" in prediction
    assert "metadata" in prediction
