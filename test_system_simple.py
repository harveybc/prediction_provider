#!/usr/bin/env python3
"""Simple test script to verify the system tests work."""

import time
from fastapi.testclient import TestClient
from app.main import app

def test_system():
    client = TestClient(app)
    
    # Test health endpoint
    response = client.get('/health')
    print(f"Health check: {response.status_code} - {response.json()}")
    
    # Test prediction creation
    prediction_data = {
        "symbol": "AAPL",
        "interval": "1d",
        "predictor_plugin": "default_predictor",
        "feeder_plugin": "default_feeder",
        "pipeline_plugin": "default_pipeline"
    }
    
    response = client.post("/api/v1/predictions/", json=prediction_data)
    print(f"Create prediction: {response.status_code} - {response.json()}")
    
    if response.status_code == 201:
        prediction = response.json()
        prediction_id = prediction["id"]
        
        # Wait a bit for async processing
        time.sleep(3)
        
        # Check status
        response = client.get(f"/api/v1/predictions/{prediction_id}")
        print(f"Get prediction: {response.status_code} - {response.json()}")
        
        print("System test completed successfully!")
    else:
        print("System test failed!")

if __name__ == "__main__":
    test_system()
