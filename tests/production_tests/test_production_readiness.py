import pytest
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app
from app.database_models import User, Role, ApiLog
from app.database import get_db
from app.auth import get_password_hash
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import time

# Test client setup
client = TestClient(app)

class TestUserManagement:
    """Test complete user management workflows"""
    
    def test_user_registration_workflow(self):
        """
        Test complete user registration workflow:
        1. Admin creates user
        2. User gets activated
        3. User can login and get API key
        4. User can make authenticated requests
        """
        # Admin creates user
        response = client.post(
            "/api/v1/admin/users",
            json={
                "username": "testuser",
                "email": "test@example.com", 
                "role": "client"
            },
            headers={"X-API-KEY": "admin_key"}
        )
        assert response.status_code == 201
        
        # User should not be able to login before activation
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "password"}
        )
        assert response.status_code == 401
        
        # Admin activates user
        response = client.post(
            "/api/v1/admin/users/testuser/activate",
            headers={"X-API-KEY": "admin_key"}
        )
        assert response.status_code == 200
        
        # User can now login
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "password"}
        )
        assert response.status_code == 200
        assert "access_token" in response.json()
    
    def test_password_change_security(self):
        """Test secure password change workflow"""
        # Create and activate user
        user_api_key = self._create_test_user("pwduser", "client")
        
        # User changes password
        response = client.put(
            "/api/v1/users/password",
            json={
                "old_password": "password",
                "new_password": "new_secure_password123!"
            },
            headers={"X-API-KEY": user_api_key}
        )
        assert response.status_code == 200
        
        # Old password should not work
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "pwduser", "password": "password"}
        )
        assert response.status_code == 401
        
        # New password should work
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "pwduser", "password": "new_secure_password123!"}
        )
        assert response.status_code == 200
    
    def test_role_based_access_control(self):
        """Test role-based access control enforcement"""
        # Create users with different roles
        self._create_test_user("client_user", "client")
        self._create_test_user("admin_user", "admin")
        self._create_test_user("operator_user", "operator")
        
        # Client should not access admin endpoints
        response = client.get(
            "/api/v1/admin/users",
            headers={"X-API-KEY": "client_key"}
        )
        assert response.status_code == 403
        
        # Admin should access admin endpoints
        response = client.get(
            "/api/v1/admin/users",
            headers={"X-API-KEY": "admin_key"}
        )
        assert response.status_code == 200
        
        # Operator should access monitoring endpoints
        response = client.get(
            "/api/v1/admin/logs",
            headers={"X-API-KEY": "operator_key"}
        )
        assert response.status_code == 200
    
    def test_user_data_isolation(self):
        """Test that users can only access their own data"""
        # Create two client users
        self._create_test_user("client1", "client")
        self._create_test_user("client2", "client")
        
        # Client1 makes prediction
        response = client.post(
            "/api/v1/predict",
            json={"ticker": "AAPL", "model_name": "default_model"},
            headers={"X-API-KEY": "client1_key"}
        )
        assert response.status_code == 200
        prediction_id = response.json()["prediction_id"]
        
        # Client2 should not access Client1's prediction
        response = client.get(
            f"/api/v1/predictions/{prediction_id}",
            headers={"X-API-KEY": "client2_key"}
        )
        assert response.status_code == 404
        
        # Client1 should access their own prediction
        response = client.get(
            f"/api/v1/predictions/{prediction_id}",
            headers={"X-API-KEY": "client1_key"}
        )
        assert response.status_code == 200
    
    def _create_test_user(self, username, role):
        """Helper to create and activate test user"""
        # Create user
        response = client.post(
            "/api/v1/admin/users",
            json={
                "username": username,
                "email": f"{username}@example.com",
                "role": role
            },
            headers={"X-API-KEY": "admin_key"}
        )
        
        # Get the API key from the response
        user_data = response.json()
        api_key = user_data["api_key"]
        
        # Activate user
        client.post(
            f"/api/v1/admin/users/{username}/activate",
            headers={"X-API-KEY": "admin_key"}
        )
        
        return api_key


class TestAuditLogging:
    """Test comprehensive audit logging for billing and compliance"""
    
    def test_prediction_request_logging(self):
        """Test that all prediction requests are logged with complete details"""
        # Create test user
        self._create_test_user("audit_user", "client")
        
        # Make prediction request
        response = client.post(
            "/api/v1/predict",
            json={"ticker": "AAPL", "model_name": "default_model"},
            headers={"X-API-KEY": "audit_user_key"}
        )
        assert response.status_code == 200
        
        # Check audit log
        response = client.get(
            "/api/v1/admin/logs?user=audit_user",
            headers={"X-API-KEY": "admin_key"}
        )
        assert response.status_code == 200
        
        logs = response.json()["logs"]
        assert len(logs) > 0
        
        # Verify log contains required fields for billing
        prediction_log = next(log for log in logs if log["endpoint"] == "/api/v1/predict")
        assert "user_id" in prediction_log
        assert "request_timestamp" in prediction_log
        assert "response_time_ms" in prediction_log
        assert "request_payload" in prediction_log
        assert "ip_address" in prediction_log
    
    def test_authentication_attempt_logging(self):
        """Test that authentication attempts are logged"""
        # Valid login attempt
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "valid_user", "password": "valid_password"}
        )
        
        # Invalid login attempt
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "invalid_user", "password": "invalid_password"}
        )
        
        # Check logs include both attempts
        response = client.get(
            "/api/v1/admin/logs?endpoint=/api/v1/auth/login",
            headers={"X-API-KEY": "admin_key"}
        )
        assert response.status_code == 200
        
        logs = response.json()["logs"]
        assert len(logs) >= 2  # At least the two attempts above
    
    def test_usage_statistics_calculation(self):
        """Test usage statistics calculation for billing"""
        # Create test user
        self._create_test_user("billing_user", "client")
        
        # Make multiple requests
        for i in range(5):
            client.post(
                "/api/v1/predict",
                json={"ticker": f"STOCK{i}", "model_name": "default_model"},
                headers={"X-API-KEY": "billing_user_key"}
            )
        
        # Get usage statistics
        response = client.get(
            "/api/v1/admin/usage/billing_user",
            headers={"X-API-KEY": "admin_key"}
        )
        assert response.status_code == 200
        
        usage = response.json()
        assert usage["total_requests"] == 5
        assert usage["total_predictions"] == 5
        assert "total_processing_time_ms" in usage
        assert "cost_estimate" in usage
    
    def test_audit_trail_integrity(self):
        """Test that audit trail cannot be tampered with"""
        # Create test user
        self._create_test_user("integrity_user", "client")
        
        # Make request
        response = client.post(
            "/api/v1/predict",
            json={"ticker": "AAPL", "model_name": "default_model"},
            headers={"X-API-KEY": "integrity_user_key"}
        )
        
        # Try to delete audit log (should fail)
        response = client.delete(
            "/api/v1/admin/logs/1",
            headers={"X-API-KEY": "admin_key"}
        )
        assert response.status_code == 405  # Method not allowed
        
        # Try to modify audit log (should fail)
        response = client.put(
            "/api/v1/admin/logs/1",
            json={"modified": "data"},
            headers={"X-API-KEY": "admin_key"}
        )
        assert response.status_code == 405  # Method not allowed
    
    def _create_test_user(self, username, role):
        """Helper to create and activate test user"""
        response = client.post(
            "/api/v1/admin/users",
            json={
                "username": username,
                "email": f"{username}@example.com",
                "role": role
            },
            headers={"X-API-KEY": "admin_key"}
        )
        
        user_data = response.json()
        api_key = user_data["api_key"]
        
        client.post(
            f"/api/v1/admin/users/{username}/activate",
            headers={"X-API-KEY": "admin_key"}
        )
        
        return api_key


class TestPerformanceScalability:
    """Test system performance and scalability"""
    
    def test_concurrent_prediction_limits(self):
        """Test maximum concurrent predictions enforcement"""
        # Create test user
        self._create_test_user("perf_user", "client")
        
        # Create more concurrent requests than allowed
        import threading
        import queue
        
        results = queue.Queue()
        
        def make_request():
            response = client.post(
                "/api/v1/predict",
                json={"ticker": "AAPL", "model_name": "default_model"},
                headers={"X-API-KEY": "perf_user_key"}
            )
            results.put(response.status_code)
        
        # Start many concurrent requests
        threads = []
        for i in range(15):  # More than max_concurrent_predictions (10)
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Check results
        status_codes = []
        while not results.empty():
            status_codes.append(results.get())
        
        # Should have some 429 (Too Many Requests) responses
        assert 429 in status_codes
        assert 200 in status_codes  # Some should succeed
    
    def test_prediction_timeout_handling(self):
        """Test prediction timeout behavior"""
        # Create test user
        self._create_test_user("timeout_user", "client")
        
        # Make request that will timeout
        start_time = time.time()
        response = client.post(
            "/api/v1/predict",
            json={"ticker": "SLOW_STOCK", "model_name": "slow_model"},
            headers={"X-API-KEY": "timeout_user_key"}
        )
        end_time = time.time()
        
        # Should timeout within reasonable time
        assert end_time - start_time < 310  # prediction_timeout + buffer
        
        if response.status_code == 408:  # Timeout
            assert "timeout" in response.json()["detail"].lower()
    
    def test_database_connection_pool(self):
        """Test database connection pool under load"""
        # Create test user
        self._create_test_user("db_user", "client")
        
        # Make many concurrent database requests
        def make_db_request():
            response = client.get(
                "/api/v1/predictions/",
                headers={"X-API-KEY": "db_user_key"}
            )
            return response.status_code
        
        import concurrent.futures
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(make_db_request) for _ in range(50)]
            results = [future.result() for future in futures]
        
        # All requests should succeed (no connection pool exhaustion)
        assert all(status == 200 for status in results)
    
    def test_memory_usage_monitoring(self):
        """Test memory usage during heavy load"""
        import psutil
        import os
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Create test user
        self._create_test_user("memory_user", "client")
        
        # Make many requests
        for i in range(100):
            client.post(
                "/api/v1/predict",
                json={"ticker": f"STOCK{i}", "model_name": "default_model"},
                headers={"X-API-KEY": "memory_user_key"}
            )
        
        # Check memory usage
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 100MB for 100 requests)
        assert memory_increase < 100 * 1024 * 1024  # 100MB
    
    def _create_test_user(self, username, role):
        """Helper to create and activate test user"""
        client.post(
            "/api/v1/admin/users",
            json={
                "username": username,
                "email": f"{username}@example.com",
                "role": role
            },
            headers={"X-API-KEY": "admin_key"}
        )
        
        client.post(
            f"/api/v1/admin/users/{username}/activate",
            headers={"X-API-KEY": "admin_key"}
        )


class TestSecurityVulnerabilities:
    """Test security vulnerabilities and protections"""
    
    def test_sql_injection_prevention(self):
        """Test SQL injection prevention"""
        # Try SQL injection in username
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin'; DROP TABLE users; --", "password": "password"}
        )
        # Should not crash the system
        assert response.status_code in [400, 401]
    
    def test_xss_prevention(self):
        """Test XSS prevention in inputs"""
        # Try XSS in ticker symbol
        response = client.post(
            "/api/v1/predict",
            json={"ticker": "<script>alert('XSS')</script>", "model_name": "default_model"},
            headers={"X-API-KEY": "test_key"}
        )
        # Should sanitize input
        assert response.status_code == 400  # Bad request due to invalid ticker
    
    def test_brute_force_protection(self):
        """Test brute force login protection"""
        # Make many failed login attempts
        for i in range(10):
            response = client.post(
                "/api/v1/auth/login",
                json={"username": "test_user", "password": "wrong_password"}
            )
        
        # Should be rate limited
        assert response.status_code == 429  # Too many requests
    
    def test_privilege_escalation_prevention(self):
        """Test privilege escalation prevention"""
        # Create regular user
        self._create_test_user("regular_user", "client")
        
        # Try to access admin endpoint
        response = client.get(
            "/api/v1/admin/users",
            headers={"X-API-KEY": "regular_user_key"}
        )
        assert response.status_code == 403  # Forbidden
        
        # Try to modify own role
        response = client.put(
            "/api/v1/users/profile",
            json={"role": "admin"},
            headers={"X-API-KEY": "regular_user_key"}
        )
        assert response.status_code == 403  # Should not allow role change
    
    def _create_test_user(self, username, role):
        """Helper to create and activate test user"""
        client.post(
            "/api/v1/admin/users",
            json={
                "username": username,
                "email": f"{username}@example.com",
                "role": role
            },
            headers={"X-API-KEY": "admin_key"}
        )
        
        client.post(
            f"/api/v1/admin/users/{username}/activate",
            headers={"X-API-KEY": "admin_key"}
        )


class TestDataIntegrity:
    """Test data integrity and consistency"""
    
    def test_prediction_data_consistency(self):
        """Test that prediction data remains consistent"""
        # Create test user
        self._create_test_user("data_user", "client")
        
        # Make prediction request
        response = client.post(
            "/api/v1/predict",
            json={"ticker": "AAPL", "model_name": "default_model"},
            headers={"X-API-KEY": "data_user_key"}
        )
        prediction_id = response.json()["prediction_id"]
        
        # Get prediction multiple times
        responses = []
        for i in range(5):
            response = client.get(
                f"/api/v1/predictions/{prediction_id}",
                headers={"X-API-KEY": "data_user_key"}
            )
            responses.append(response.json())
        
        # All responses should be identical
        for i in range(1, len(responses)):
            assert responses[i]["id"] == responses[0]["id"]
            assert responses[i]["status"] == responses[0]["status"]
            assert responses[i]["ticker"] == responses[0]["ticker"]
    
    def test_database_transaction_integrity(self):
        """Test database transaction atomicity"""
        # This test would require more complex setup to simulate
        # transaction failures, but the structure shows the intent
        pass
    
    def test_concurrent_data_access(self):
        """Test data consistency under concurrent access"""
        # Create test user
        self._create_test_user("concurrent_user", "client")
        
        # Make prediction
        response = client.post(
            "/api/v1/predict",
            json={"ticker": "AAPL", "model_name": "default_model"},
            headers={"X-API-KEY": "concurrent_user_key"}
        )
        prediction_id = response.json()["prediction_id"]
        
        # Access prediction concurrently
        import threading
        results = []
        
        def get_prediction():
            response = client.get(
                f"/api/v1/predictions/{prediction_id}",
                headers={"X-API-KEY": "concurrent_user_key"}
            )
            results.append(response.json())
        
        threads = []
        for i in range(10):
            thread = threading.Thread(target=get_prediction)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # All results should be consistent
        assert all(result["id"] == results[0]["id"] for result in results)
    
    def _create_test_user(self, username, role):
        """Helper to create and activate test user"""
        client.post(
            "/api/v1/admin/users",
            json={
                "username": username,
                "email": f"{username}@example.com",
                "role": role
            },
            headers={"X-API-KEY": "admin_key"}
        )
        
        client.post(
            f"/api/v1/admin/users/{username}/activate",
            headers={"X-API-KEY": "admin_key"}
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
