"""
Security tests for Prediction Provider input validation.
"""
import pytest
from fastapi.testclient import TestClient
from plugins_core.default_core import app


@pytest.fixture
def client():
    return TestClient(app)


class TestSQLInjection:
    def test_sql_injection_in_symbol(self, client):
        payloads = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "' UNION SELECT * FROM users --",
        ]
        for payload in payloads:
            resp = client.post("/api/v1/predictions/", json={"symbol": payload, "interval": "1d"}, headers={"X-API-KEY": "test_key"})
            assert resp.status_code in [400, 422, 201]
            # If accepted, verify it's stored as data not executed
            if resp.status_code == 201:
                pid = resp.json()["id"]
                get_resp = client.get(f"/api/v1/predictions/{pid}", headers={"X-API-KEY": "test_key"})
                assert get_resp.status_code == 200


class TestXSSPrevention:
    def test_xss_in_symbol(self, client):
        xss_payloads = [
            "<script>alert('xss')</script>",
            "javascript:alert(1)",
            '<img src=x onerror=alert(1)>',
        ]
        for payload in xss_payloads:
            resp = client.post("/api/v1/predictions/", json={"symbol": payload, "interval": "1d"}, headers={"X-API-KEY": "test_key"})
            if resp.status_code == 201:
                pid = resp.json()["id"]
                get_resp = client.get(f"/api/v1/predictions/{pid}", headers={"X-API-KEY": "test_key"})
                data = get_resp.json()
                assert "<script>" not in str(data)


class TestMalformedInput:
    def test_empty_json(self, client):
        resp = client.post("/api/v1/predictions/", json={}, headers={"X-API-KEY": "test_key"})
        assert resp.status_code == 422

    def test_invalid_json(self, client):
        resp = client.post("/api/v1/predictions/", content=b"not json", headers={"Content-Type": "application/json", "X-API-KEY": "test_key"})
        assert resp.status_code == 422

    def test_invalid_prediction_type(self, client):
        resp = client.post("/api/v1/predictions/", json={"symbol": "AAPL", "interval": "1d", "prediction_type": "invalid_type"}, headers={"X-API-KEY": "test_key"})
        assert resp.status_code == 422

    def test_oversized_symbol(self, client):
        resp = client.post("/api/v1/predictions/", json={"symbol": "A" * 1000, "interval": "1d"}, headers={"X-API-KEY": "test_key"})
        assert resp.status_code == 422


class TestPathTraversal:
    def test_path_traversal_in_symbol(self, client):
        resp = client.post("/api/v1/predictions/", json={"symbol": "../../../etc/passwd", "interval": "1d"}, headers={"X-API-KEY": "test_key"})
        assert resp.status_code in [400, 422, 201]


class TestSensitiveDataExposure:
    def test_error_no_db_info(self, client):
        resp = client.get("/api/v1/predictions/999999", headers={"X-API-KEY": "test_key"})
        assert resp.status_code == 404
        detail = resp.json().get("detail", "")
        assert "table" not in detail.lower()
        assert "select" not in detail.lower()
        assert "/home/" not in detail

    def test_response_no_secrets(self, client):
        resp = client.post("/api/v1/predictions/", json={"symbol": "AAPL", "interval": "1d"}, headers={"X-API-KEY": "test_key"})
        if resp.status_code == 201:
            data_str = str(resp.json()).lower()
            for field in ["password", "secret", "api_key", "hashed"]:
                assert field not in data_str
