#!/usr/bin/env python3

from fastapi.testclient import TestClient
from plugins_core.default_core import app

client = TestClient(app)

# Test a simple endpoint first
response = client.get("/api/v1/plugins/")

print(f"Status: {response.status_code}")
print(f"Response: {response.text}")
