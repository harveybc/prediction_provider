#!/usr/bin/env python3
"""Simple test to check if the system test works."""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from app.main import app
import time

def test_system():
    client = TestClient(app)
    
    # Test prediction creation
    prediction_data = {
        "symbol": "AAPL",
        "interval": "1d",
        "predictor_plugin": "default_predictor",
        "feeder_plugin": "default_feeder",
        "pipeline_plugin": "default_pipeline"
    }
    
    print("Creating prediction...")
    response = client.post("/api/v1/predictions/", json=prediction_data)
    print(f"Create response: {response.status_code}")
    
    if response.status_code == 201:
        prediction = response.json()
        print(f"Created prediction: {prediction}")
        prediction_id = prediction["id"]
        
        print("Waiting for background task...")
        time.sleep(3)
        
        print("Checking status...")
        response = client.get(f"/api/v1/predictions/{prediction_id}")
        print(f"Get response: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Final result: {result}")
            print("Test completed!")
        else:
            print(f"Error getting prediction: {response.text}")
    else:
        print(f"Error creating prediction: {response.text}")

if __name__ == "__main__":
    test_system()
