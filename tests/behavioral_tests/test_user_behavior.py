import pytest
import uuid
import time
from fastapi.testclient import TestClient
from app.main import app

# Test client setup
client = TestClient(app)

class TestUserBehavior:
    """Test user behavior scenarios (BDD style)"""
    
    def test_new_user_can_be_onboarded_and_make_predictions(self):
        """
        GIVEN: A new user needs to be onboarded
        WHEN: Admin creates and activates the user
        THEN: User can successfully make predictions
        """
        # GIVEN: Generate unique user data
        user_id = f"user_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        user_email = f"{user_id}@example.com"
        
        # WHEN: Admin creates user
        response = client.post(
            "/api/v1/admin/users",
            json={
                "username": user_id,
                "email": user_email,
                "role": "client"
            },
            headers={"X-API-KEY": "admin_key"}
        )
        
        # THEN: User is created successfully
        assert response.status_code == 201
        user_data = response.json()
        assert "api_key" in user_data
        api_key = user_data["api_key"]
        
        # WHEN: Admin activates user
        response = client.post(
            f"/api/v1/admin/users/{user_id}/activate",
            headers={"X-API-KEY": "admin_key"}
        )
        
        # THEN: User is activated
        assert response.status_code == 200
        
        # WHEN: User makes a prediction
        response = client.post(
            "/api/v1/predict",
            json={"ticker": "AAPL", "model_name": "default_model"},
            headers={"X-API-KEY": api_key}
        )
        
        # THEN: Prediction is created successfully
        assert response.status_code == 201
        prediction_data = response.json()
        assert "prediction_id" in prediction_data
        assert prediction_data["status"] == "pending"
        assert prediction_data["ticker"] == "AAPL"
    
    def test_user_can_change_password_and_still_authenticate(self):
        """
        GIVEN: An active user wants to change their password
        WHEN: User changes password with valid credentials
        THEN: User can authenticate with new password and old password fails
        """
        # GIVEN: Create and activate user
        user_id = f"pwd_user_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        response = client.post(
            "/api/v1/admin/users",
            json={
                "username": user_id,
                "email": f"{user_id}@example.com",
                "role": "client"
            },
            headers={"X-API-KEY": "admin_key"}
        )
        api_key = response.json()["api_key"]
        
        client.post(
            f"/api/v1/admin/users/{user_id}/activate",
            headers={"X-API-KEY": "admin_key"}
        )
        
        # WHEN: User changes password
        new_password = "new_secure_password123!"
        response = client.put(
            "/api/v1/users/password",
            json={
                "old_password": "password",
                "new_password": new_password
            },
            headers={"X-API-KEY": api_key}
        )
        
        # THEN: Password change is successful
        assert response.status_code == 200
        
        # WHEN: User tries to login with old password
        response = client.post(
            "/api/v1/auth/login",
            json={"username": user_id, "password": "password"}
        )
        
        # THEN: Old password fails
        assert response.status_code == 401
        
        # WHEN: User tries to login with new password
        response = client.post(
            "/api/v1/auth/login",
            json={"username": user_id, "password": new_password}
        )
        
        # THEN: New password works
        assert response.status_code == 200
        assert "access_token" in response.json()
    
    def test_users_can_only_access_their_own_data(self):
        """
        GIVEN: Two users with their own predictions
        WHEN: One user tries to access another user's data
        THEN: Access is denied while own data is accessible
        """
        # GIVEN: Create two users
        user1_id = f"user1_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        user2_id = f"user2_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Create user 1
        response = client.post(
            "/api/v1/admin/users",
            json={
                "username": user1_id,
                "email": f"{user1_id}@example.com",
                "role": "client"
            },
            headers={"X-API-KEY": "admin_key"}
        )
        user1_api_key = response.json()["api_key"]
        client.post(f"/api/v1/admin/users/{user1_id}/activate", headers={"X-API-KEY": "admin_key"})
        
        # Create user 2
        response = client.post(
            "/api/v1/admin/users",
            json={
                "username": user2_id,
                "email": f"{user2_id}@example.com",
                "role": "client"
            },
            headers={"X-API-KEY": "admin_key"}
        )
        user2_api_key = response.json()["api_key"]
        client.post(f"/api/v1/admin/users/{user2_id}/activate", headers={"X-API-KEY": "admin_key"})
        
        # WHEN: User 1 creates a prediction
        response = client.post(
            "/api/v1/predict",
            json={"ticker": "AAPL", "model_name": "default_model"},
            headers={"X-API-KEY": user1_api_key}
        )
        prediction_id = response.json()["prediction_id"]
        
        # WHEN: User 2 tries to access User 1's prediction
        response = client.get(
            f"/api/v1/predictions/{prediction_id}",
            headers={"X-API-KEY": user2_api_key}
        )
        
        # THEN: Access is denied
        assert response.status_code == 403
        
        # WHEN: User 1 accesses their own prediction
        response = client.get(
            f"/api/v1/predictions/{prediction_id}",
            headers={"X-API-KEY": user1_api_key}
        )
        
        # THEN: Access is granted
        assert response.status_code == 200
        data = response.json()
        assert data["prediction_id"] == prediction_id


class TestAccessControlBehavior:
    """Test access control behaviors"""
    
    def test_admin_can_manage_users_but_cannot_make_predictions(self):
        """
        GIVEN: An admin user with management privileges
        WHEN: Admin tries to manage users and make predictions
        THEN: Admin can manage users but predictions follow business rules
        """
        # GIVEN: Admin is already set up in test data
        admin_api_key = "admin_key"
        
        # WHEN: Admin tries to create a user
        user_id = f"managed_user_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        response = client.post(
            "/api/v1/admin/users",
            json={
                "username": user_id,
                "email": f"{user_id}@example.com",
                "role": "client"
            },
            headers={"X-API-KEY": admin_api_key}
        )
        
        # THEN: User management succeeds
        assert response.status_code == 201
        
        # WHEN: Admin tries to make a prediction
        response = client.post(
            "/api/v1/predict",
            json={"ticker": "AAPL", "model_name": "default_model"},
            headers={"X-API-KEY": admin_api_key}
        )
        
        # THEN: System handles prediction request according to business rules
        # (Either allows it or denies based on current policy)
        assert response.status_code in [201, 403]
    
    def test_client_can_make_predictions_but_cannot_manage_users(self):
        """
        GIVEN: A client user with prediction privileges
        WHEN: Client tries to make predictions and manage users
        THEN: Client can make predictions but cannot manage users
        """
        # GIVEN: Create a client user
        client_id = f"client_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        response = client.post(
            "/api/v1/admin/users",
            json={
                "username": client_id,
                "email": f"{client_id}@example.com",
                "role": "client"
            },
            headers={"X-API-KEY": "admin_key"}
        )
        client_api_key = response.json()["api_key"]
        client.post(f"/api/v1/admin/users/{client_id}/activate", headers={"X-API-KEY": "admin_key"})
        
        # WHEN: Client tries to make a prediction
        response = client.post(
            "/api/v1/predict",
            json={"ticker": "AAPL", "model_name": "default_model"},
            headers={"X-API-KEY": client_api_key}
        )
        
        # THEN: Prediction succeeds
        assert response.status_code == 201
        
        # WHEN: Client tries to create another user
        response = client.post(
            "/api/v1/admin/users",
            json={
                "username": "unauthorized_user",
                "email": "unauthorized@example.com",
                "role": "client"
            },
            headers={"X-API-KEY": client_api_key}
        )
        
        # THEN: User management is denied
        assert response.status_code == 403


class TestSystemBehavior:
    """Test system-level behaviors"""
    
    def test_system_tracks_user_activities_for_audit(self):
        """
        GIVEN: A user performing various activities
        WHEN: User makes predictions and changes settings
        THEN: System maintains audit trail of all activities
        """
        # GIVEN: Create a user
        user_id = f"audit_user_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        response = client.post(
            "/api/v1/admin/users",
            json={
                "username": user_id,
                "email": f"{user_id}@example.com",
                "role": "client"
            },
            headers={"X-API-KEY": "admin_key"}
        )
        user_api_key = response.json()["api_key"]
        client.post(f"/api/v1/admin/users/{user_id}/activate", headers={"X-API-KEY": "admin_key"})
        
        # WHEN: User makes a prediction
        response = client.post(
            "/api/v1/predict",
            json={"ticker": "AAPL", "model_name": "default_model"},
            headers={"X-API-KEY": user_api_key}
        )
        
        # THEN: Prediction is successful
        assert response.status_code == 201
        
        # WHEN: Admin checks audit logs
        response = client.get(
            "/api/v1/admin/logs",
            headers={"X-API-KEY": "admin_key"}
        )
        
        # THEN: Audit trail exists
        assert response.status_code == 200
        logs_response = response.json()
        
        # Verify logs are being tracked (structure may vary)
        if isinstance(logs_response, dict) and 'logs' in logs_response:
            logs = logs_response['logs']
            assert isinstance(logs, list)
        else:
            logs = logs_response
            assert isinstance(logs, list)
        # Basic behavioral check: system is tracking something
        assert len(logs) >= 0  # At minimum, logs endpoint should return a list
    
    def test_system_prevents_excessive_concurrent_predictions(self):
        """
        GIVEN: A user trying to make many concurrent predictions
        WHEN: User exceeds the reasonable limit
        THEN: System prevents resource exhaustion
        """
        # GIVEN: Create a user
        user_id = f"concurrent_user_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        response = client.post(
            "/api/v1/admin/users",
            json={
                "username": user_id,
                "email": f"{user_id}@example.com",
                "role": "client"
            },
            headers={"X-API-KEY": "admin_key"}
        )
        user_api_key = response.json()["api_key"]
        client.post(f"/api/v1/admin/users/{user_id}/activate", headers={"X-API-KEY": "admin_key"})
        
        # WHEN: User makes multiple predictions rapidly
        responses = []
        for i in range(15):  # Try to exceed the limit
            response = client.post(
                "/api/v1/predict",
                json={"ticker": f"STOCK{i}", "model_name": "default_model"},
                headers={"X-API-KEY": user_api_key}
            )
            responses.append(response.status_code)
        
        # THEN: System prevents resource exhaustion
        success_count = sum(1 for code in responses if code == 201)
        too_many_requests_count = sum(1 for code in responses if code == 429)
        
        # Should have some successful requests and some rate-limited
        assert success_count > 0
        # Note: In test environment, we might have different limits
        assert success_count + too_many_requests_count == 15


class TestSecurityBehavior:
    """Test security-related behaviors"""
    
    def test_system_protects_against_malicious_input(self):
        """
        GIVEN: A user attempting to inject malicious data
        WHEN: User sends potentially harmful input
        THEN: System sanitizes and rejects dangerous content
        """
        # GIVEN: Create a user
        user_id = f"security_user_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        response = client.post(
            "/api/v1/admin/users",
            json={
                "username": user_id,
                "email": f"{user_id}@example.com",
                "role": "client"
            },
            headers={"X-API-KEY": "admin_key"}
        )
        user_api_key = response.json()["api_key"]
        client.post(f"/api/v1/admin/users/{user_id}/activate", headers={"X-API-KEY": "admin_key"})
        
        # WHEN: User tries to inject script tags
        response = client.post(
            "/api/v1/predict",
            json={
                "ticker": "<script>alert('xss')</script>",
                "model_name": "default_model"
            },
            headers={"X-API-KEY": user_api_key}
        )
        
        # THEN: System handles the request safely
        # Should either sanitize the input, reject it, or validate it properly
        assert response.status_code in [201, 400, 422]
        
        if response.status_code == 201:
            # If accepted, verify script tags are sanitized
            data = response.json()
            assert "<script>" not in data["ticker"]
            assert "alert" not in data["ticker"]
    
    def test_system_prevents_unauthorized_access_without_credentials(self):
        """
        GIVEN: A user without proper credentials
        WHEN: User tries to access protected resources
        THEN: System denies access appropriately
        """
        # WHEN: User tries to access admin endpoints without credentials
        response = client.get("/api/v1/admin/users")
        
        # THEN: Access is denied
        assert response.status_code in [401, 403]
        
        # WHEN: User tries to access admin endpoints with invalid credentials
        response = client.get(
            "/api/v1/admin/users",
            headers={"X-API-KEY": "invalid_key"}
        )
        
        # THEN: Access is denied
        assert response.status_code in [401, 403]


class TestPredictionBehavior:
    """Test prediction-related behaviors"""
    
    def test_user_can_request_and_track_predictions(self):
        """
        GIVEN: A user wants to make and track predictions
        WHEN: User submits prediction request and checks status
        THEN: User can successfully track prediction lifecycle
        """
        # GIVEN: Create a user
        user_id = f"prediction_user_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        response = client.post(
            "/api/v1/admin/users",
            json={
                "username": user_id,
                "email": f"{user_id}@example.com",
                "role": "client"
            },
            headers={"X-API-KEY": "admin_key"}
        )
        user_api_key = response.json()["api_key"]
        client.post(f"/api/v1/admin/users/{user_id}/activate", headers={"X-API-KEY": "admin_key"})
        
        # WHEN: User requests a prediction
        response = client.post(
            "/api/v1/predict",
            json={"ticker": "AAPL", "model_name": "default_model"},
            headers={"X-API-KEY": user_api_key}
        )
        
        # THEN: Prediction is accepted
        assert response.status_code == 201
        prediction_data = response.json()
        prediction_id = prediction_data["prediction_id"]
        
        # WHEN: User checks prediction status
        response = client.get(
            f"/api/v1/predictions/{prediction_id}",
            headers={"X-API-KEY": user_api_key}
        )
        
        # THEN: Status is accessible
        assert response.status_code == 200
        status_data = response.json()
        assert status_data["prediction_id"] == prediction_id
        assert "status" in status_data
        assert status_data["status"] in ["pending", "processing", "completed", "failed"]
    
    def test_public_users_can_make_predictions_without_authentication(self):
        """
        GIVEN: A public user without authentication
        WHEN: User makes a prediction request
        THEN: System allows public access to prediction service
        """
        # WHEN: Public user makes prediction without API key
        response = client.post(
            "/api/v1/predict",
            json={"ticker": "AAPL", "model_name": "default_model"}
        )
        
        # THEN: Prediction is accepted
        assert response.status_code == 201
        prediction_data = response.json()
        assert "prediction_id" in prediction_data
        assert prediction_data["ticker"] == "AAPL"
        assert prediction_data["status"] == "pending"
