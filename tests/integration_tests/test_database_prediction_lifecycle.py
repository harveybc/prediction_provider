# This file will contain integration tests for the database prediction lifecycle.

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import time

# Assuming app.main.app and database session fixtures are available from conftest.py
# from app.main import app
# from app.database import get_db, Prediction

# Note: We will use the client and db_session fixtures defined in conftest.py

def test_prediction_lifecycle_in_database(client: TestClient, db_session: Session):
    """
    Tests the entire lifecycle of a prediction request, from creation to completion,
    ensuring database records are created and updated correctly.
    """
    # 1. Create a new prediction request
    response = client.post(
        "/api/v1/predict",
        json={"ticker": "AAPL", "model_name": "default", "prediction_horizon": 1}
    )
    assert response.status_code == 202
    data = response.json()
    task_id = data["task_id"]
    assert task_id is not None

    # 2. Verify initial "PENDING" status in the database
    # The test might need to query the DB directly using the db_session fixture
    from app.models import Prediction # Import here to avoid circular dependency issues
    prediction_record = db_session.query(Prediction).filter(Prediction.task_id == task_id).first()
    assert prediction_record is not None
    assert prediction_record.status == "PENDING"

    # 3. Poll for the result until the status is "COMPLETED"
    timeout = 60  # seconds
    start_time = time.time()
    while time.time() - start_time < timeout:
        response = client.get(f"/predict/{task_id}")
        assert response.status_code == 200
        status = response.json()["status"]
        if status == "COMPLETED":
            break
        elif status == "FAILED":
            pytest.fail(f"Prediction task {task_id} failed.")
        time.sleep(1) # Poll every second
    else:
        pytest.fail(f"Prediction task {task_id} did not complete within {timeout} seconds.")

    # 4. Verify the final state in the database
    final_response = client.get(f"/predict/{task_id}")
    final_data = final_response.json()

    assert final_data["status"] == "COMPLETED"
    assert "prediction" in final_data
    assert "uncertainty" in final_data

    # 5. Re-verify the database record reflects the completed state
    completed_record = db_session.query(Prediction).filter(Prediction.task_id == task_id).first()
    assert completed_record is not None
    assert completed_record.status == "COMPLETED"
    assert completed_record.prediction is not None
    assert completed_record.uncertainty is not None
