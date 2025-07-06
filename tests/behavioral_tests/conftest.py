import warnings
# Suppress all warnings for behavioral tests
warnings.filterwarnings("ignore")

import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture(scope="module")
def behavioral_client():
    """Client for behavioral tests with proper configuration"""
    with TestClient(app) as client:
        yield client

@pytest.fixture(autouse=True)
def setup_behavioral_test_environment():
    """Set up environment for behavioral tests"""
    # Clear any rate limiting between tests
    try:
        client = TestClient(app)
        client.post("/test/reset-rate-limit")
    except:
        pass  # Ignore if endpoint doesn't exist
