#!/usr/bin/env python3

"""Debug script to test user creation endpoint"""

from fastapi.testclient import TestClient
from app.main import app
import json

client = TestClient(app)

def test_user_creation():
    """Test user creation endpoint"""
    print("Testing user creation endpoint...")
    
    # Create user
    response = client.post(
        "/api/v1/admin/users",
        json={
            "username": "debug_user",
            "email": "debug@example.com",
            "role": "client"
        },
        headers={"X-API-KEY": "admin_key"}
    )
    
    print(f"Status code: {response.status_code}")
    print(f"Response: {response.text}")
    print(f"JSON: {json.dumps(response.json(), indent=2)}")

if __name__ == "__main__":
    test_user_creation()
