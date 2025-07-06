#!/usr/bin/env python3

from fastapi.testclient import TestClient
from plugins_core.default_core import app

client = TestClient(app)

# Test user creation endpoint
response = client.post(
    "/api/v1/admin/users",
    json={
        "username": "testuser123",
        "email": "testuser123@example.com",
        "role": "client"
    },
    headers={"X-API-KEY": "admin_key"}
)

print(f"Status: {response.status_code}")
print(f"Response: {response.text}")
