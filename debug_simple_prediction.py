#!/usr/bin/env python3

"""Simple debug script to test prediction creation"""

from fastapi.testclient import TestClient
from app.main import app
import json
import time

client = TestClient(app)

def test_simple_prediction():
    """Test simple prediction creation"""
    print("Testing simple prediction creation...")
    
    # Make prediction without authentication (should work in public mode)
    print("1. Making prediction without authentication...")
    response = client.post(
        "/api/v1/predict",
        json={"ticker": "AAPL", "model_name": "default_model"}
    )
    print(f"Prediction creation - Status: {response.status_code}")
    if response.status_code != 201:
        print(f"Prediction creation failed: {response.text}")
        return
    
    prediction_data = response.json()
    prediction_id = prediction_data["prediction_id"]
    print(f"Prediction created: {prediction_id}")
    print(f"Full response: {json.dumps(prediction_data, indent=2)}")

if __name__ == "__main__":
    test_simple_prediction()
