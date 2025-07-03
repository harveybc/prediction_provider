
import pytest
import asyncio
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db, Base, engine
from app.models import Prediction
import time

# Use a separate test database
TEST_DATABASE_URL = "sqlite:///./test.db"

# This is a placeholder for now. We will need to implement the actual database setup and teardown
# in a conftest.py file later.
@pytest.fixture(scope="module")
def test_client():
    # Create the test database
    Base.metadata.create_all(bind=engine)
    client = TestClient(app)
    yield client
    # Drop the test database
    Base.metadata.drop_all(bind=engine)


def test_full_prediction_lifecycle(test_client):
    """
    Test the full lifecycle of a prediction:
    1. Create a prediction.
    2. Poll the status until it's complete.
    3. Retrieve the prediction and verify the results.
    """
    prediction_data = {
        "symbol": "AAPL",
        "interval": "1d",
        "predictor_plugin": "default_predictor",
        "feeder_plugin": "default_feeder",
        "pipeline_plugin": "default_pipeline"
    }
    
    # 1. Create a prediction
    response = test_client.post("/api/v1/predictions/", json=prediction_data)
    assert response.status_code == 201
    prediction = response.json()
    prediction_id = prediction["id"]
    assert prediction["status"] == "pending"

    # 2. Poll for completion
    timeout = 60  # 60 seconds
    start_time = time.time()
    while time.time() - start_time < timeout:
        response = test_client.get(f"/api/v1/predictions/{prediction_id}")
        assert response.status_code == 200
        status = response.json()["status"]
        if status == "completed":
            break
        elif status == "failed":
            pytest.fail("Prediction failed during processing.")
        time.sleep(1)
    else:
        pytest.fail("Prediction did not complete within the timeout period.")

    # 3. Retrieve and verify
    response = test_client.get(f"/api/v1/predictions/{prediction_id}")
    assert response.status_code == 200
    final_prediction = response.json()
    
    assert final_prediction["id"] == prediction_id
    assert final_prediction["status"] == "completed"
    assert final_prediction["symbol"] == "AAPL"
    assert "result" in final_prediction
    assert final_prediction["result"] is not None

