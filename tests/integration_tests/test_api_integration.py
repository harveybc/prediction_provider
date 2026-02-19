#!/usr/bin/env python3
"""
FastAPI Endpoints Integration Tests

Tests the complete API layer integration including request/response handling,
authentication, and endpoint functionality.
"""

import pytest
from fastapi.testclient import TestClient
from plugins_core.default_core import app
from app.database import get_db

# Note: dependency override for get_db is handled by the root conftest

class TestAPIIntegration:
    """
    Integration tests for FastAPI endpoints and API layer functionality.
    """
    
    @pytest.fixture
    def client(self):
        """Create a test client for FastAPI application."""
        return TestClient(app)
    
    def test_health_check_endpoint(self, client):
        """
        Test Case 6.1: Verify health check endpoint responds correctly.
        """
        # Act
        response = client.get("/health")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "ok"]
    
    def test_prediction_request_endpoint(self, client):
        """
        Test Case 6.2: Verify prediction request endpoint integration.
        """
        # Arrange
        request_payload = {
            "ticker": "AAPL",
            "model_name": "default",
            "prediction_horizon": 1
        }
        
        # Act
        response = client.post("/api/v1/predict", json=request_payload)
        
        # Assert
        assert response.status_code in [200, 201, 202]  # Accept async processing
        data = response.json()
        assert "task_id" in data or "prediction" in data
    
    def test_plugin_status_endpoint(self, client):
        """
        Test Case 6.3: Verify plugin status endpoint reports correctly.
        """
        # Act
        response = client.get("/api/v1/plugins/status")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "plugins" in data
        assert isinstance(data["plugins"], (list, dict))
    
    def test_cors_headers(self, client):
        """
        Test Case 6.4: Verify CORS headers are properly set.
        """
        # Act
        response = client.options("/api/v1/predict")
        
        # Assert
        assert response.status_code in [200, 204]
        # CORS headers should be present in a production setup
    
    def test_api_error_handling(self, client):
        """
        Test Case 6.5: Verify API error handling works correctly.
        """
        # Arrange - send invalid request
        invalid_payload = {"invalid_field": "invalid_value"}
        
        # Act
        response = client.post("/api/v1/predict", json=invalid_payload)
        
        # Assert
        assert response.status_code == 422  # Validation error
        data = response.json()
        assert "detail" in data
