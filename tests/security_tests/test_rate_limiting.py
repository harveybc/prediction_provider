"""
Security tests for Prediction Provider rate limiting.
"""
import pytest
from fastapi.testclient import TestClient
from plugins_core.default_core import app


@pytest.fixture
def client():
    return TestClient(app)


class TestRateLimiting:
    def test_rapid_requests_handled(self, client):
        """Rapid requests should be handled (either processed or rate-limited)"""
        statuses = []
        for i in range(20):
            resp = client.post("/api/v1/predictions/", json={"symbol": "AAPL", "interval": "1d"}, headers={"X-API-KEY": "test_key"})
            statuses.append(resp.status_code)
        
        success = sum(1 for s in statuses if s == 201)
        limited = sum(1 for s in statuses if s == 429)
        assert success + limited == 20

    def test_invalid_key_rapid(self, client):
        """Rapid invalid auth attempts should all be rejected"""
        for i in range(10):
            resp = client.post("/api/v1/predictions/", json={"symbol": "AAPL", "interval": "1d"}, headers={"X-API-KEY": f"invalid_{i}"})
            assert resp.status_code in [403, 429]
