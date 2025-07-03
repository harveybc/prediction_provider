#!/usr/bin/env python3
"""Debug test to check the API endpoint."""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# Test the prediction endpoint
prediction_data = {
    "symbol": "AAPL",
    "interval": "1d",
    "predictor_plugin": "default_predictor",
    "feeder_plugin": "default_feeder",
    "pipeline_plugin": "default_pipeline"
}

response = client.post("/api/v1/predictions/", json=prediction_data)
print(f"Status code: {response.status_code}")
print(f"Response content: {response.content}")
print(f"Response headers: {response.headers}")

if response.status_code != 201:
    print(f"Error response: {response.json()}")
