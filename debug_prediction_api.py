#!/usr/bin/env python3

"""Debug script to test prediction API endpoints"""

from fastapi.testclient import TestClient
from app.main import app
import json
import time

client = TestClient(app)

def test_prediction_api():
    """Test prediction API workflow"""
    print("Testing prediction API workflow...")
    
    # Create and activate a user first
    print("1. Creating user...")
    response = client.post(
        "/api/v1/admin/users",
        json={
            "username": f"test_user_{int(time.time())}",
            "email": f"test_{int(time.time())}@example.com",
            "role": "client"
        },
        headers={"X-API-KEY": "admin_key"}
    )
    print(f"User creation - Status: {response.status_code}")
    if response.status_code != 201:
        print(f"User creation failed: {response.text}")
        return
    
    user_data = response.json()
    api_key = user_data["api_key"]
    username = user_data["username"]
    print(f"User created: {username}, API key: {api_key[:20]}...")
    
    # Activate user
    print("2. Activating user...")
    response = client.post(
        f"/api/v1/admin/users/{username}/activate",
        headers={"X-API-KEY": "admin_key"}
    )
    print(f"User activation - Status: {response.status_code}")
    if response.status_code != 200:
        print(f"User activation failed: {response.text}")
        return
    
    # Make prediction
    print("3. Making prediction...")
    response = client.post(
        "/api/v1/predict",
        json={"ticker": "AAPL", "model_name": "default_model"},
        headers={"X-API-KEY": api_key}
    )
    print(f"Prediction creation - Status: {response.status_code}")
    if response.status_code != 201:
        print(f"Prediction creation failed: {response.text}")
        return
    
    prediction_data = response.json()
    prediction_id = prediction_data["prediction_id"]
    print(f"Prediction created: {prediction_id}")
    
    # Get prediction
    print("4. Getting prediction...")
    response = client.get(
        f"/api/v1/predictions/{prediction_id}",
        headers={"X-API-KEY": api_key}
    )
    print(f"Get prediction - Status: {response.status_code}")
    if response.status_code != 200:
        print(f"Get prediction failed: {response.text}")
        return
    
    print(f"Get prediction success: {response.json()}")
    
    # Test access with different user
    print("5. Testing access control...")
    # Create another user
    response = client.post(
        "/api/v1/admin/users",
        json={
            "username": f"test_user2_{int(time.time())}",
            "email": f"test2_{int(time.time())}@example.com",
            "role": "client"
        },
        headers={"X-API-KEY": "admin_key"}
    )
    
    if response.status_code == 201:
        user2_data = response.json()
        api_key2 = user2_data["api_key"]
        username2 = user2_data["username"]
        
        # Activate user2
        client.post(
            f"/api/v1/admin/users/{username2}/activate",
            headers={"X-API-KEY": "admin_key"}
        )
        
        # Try to access first user's prediction
        response = client.get(
            f"/api/v1/predictions/{prediction_id}",
            headers={"X-API-KEY": api_key2}
        )
        print(f"Access control test - Status: {response.status_code}")
        if response.status_code == 403:
            print("Access control working correctly - 403 Forbidden")
        else:
            print(f"Access control issue: {response.text}")

if __name__ == "__main__":
    test_prediction_api()
