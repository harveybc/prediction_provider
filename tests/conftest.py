import warnings
# Suppress warnings before any other imports
warnings.filterwarnings("ignore", category=DeprecationWarning, module="multiprocessing")
warnings.filterwarnings("ignore", category=PendingDeprecationWarning, module="multipart")
warnings.filterwarnings("ignore", category=PendingDeprecationWarning, message="Please use `import python_multipart` instead.")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="pkg_resources")
warnings.filterwarnings("ignore", category=DeprecationWarning, message="pkg_resources is deprecated as an API.*")

import sys
import os
import multiprocessing

# Set multiprocessing start method to avoid fork issues
if multiprocessing.get_start_method(allow_none=True) is None:
    multiprocessing.set_start_method('spawn', force=True)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from plugins_core.default_core import app
from app.database import Base, get_db
from app.database_models import User, Role
from app.auth import hash_api_key, get_password_hash

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


Base.metadata.create_all(bind=engine)

def setup_test_data():
    """Setup test users and roles for testing"""
    db = TestingSessionLocal()
    try:
        # Clear existing data
        db.query(User).delete()
        db.query(Role).delete()
        
        # Create roles
        admin_role = Role(id=1, name="admin", description="Administrator", permissions={"can_predict": True, "can_view_logs": True, "can_manage_users": True})
        client_role = Role(id=2, name="client", description="Client", permissions={"can_predict": True, "can_view_logs": False})
        operator_role = Role(id=3, name="operator", description="Operator", permissions={"can_predict": True, "can_view_logs": True})
        
        db.add(admin_role)
        db.add(client_role)
        db.add(operator_role)
        db.commit()
        
        # Create test users with specific API keys
        test_users = [
            {"username": "admin_user", "email": "admin@test.com", "api_key": "admin_key", "role_id": 1},
            {"username": "test_user", "email": "test@test.com", "api_key": "test_key", "role_id": 2},
            {"username": "client_user", "email": "client@test.com", "api_key": "client_key", "role_id": 2},
            {"username": "operator_user", "email": "operator@test.com", "api_key": "operator_key", "role_id": 3},
            {"username": "user_key", "email": "user@test.com", "api_key": "user_key", "role_id": 2},
            {"username": "client1", "email": "client1@test.com", "api_key": "client1_key", "role_id": 2},
            {"username": "client2", "email": "client2@test.com", "api_key": "client2_key", "role_id": 2},
            {"username": "audit_user", "email": "audit@test.com", "api_key": "audit_user_key", "role_id": 2},
            {"username": "billing_user", "email": "billing@test.com", "api_key": "billing_user_key", "role_id": 2},
            {"username": "integrity_user", "email": "integrity@test.com", "api_key": "integrity_user_key", "role_id": 2},
            {"username": "data_user", "email": "data@test.com", "api_key": "data_user_key", "role_id": 2},
        ]
        
        for user_data in test_users:
            user = User(
                username=user_data["username"],
                email=user_data["email"],
                hashed_password=get_password_hash("testpass123"),
                hashed_api_key=hash_api_key(user_data["api_key"]),
                is_active=True,
                role_id=user_data["role_id"]
            )
            db.add(user)
        
        db.commit()
    finally:
        db.close()

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Setup test database with required data before running any tests"""
    setup_test_data()
    yield
    # Cleanup after all tests
    try:
        os.remove("test.db")
    except FileNotFoundError:
        pass

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture(scope="module")
def test_client():
    """Alias for client fixture to match test expectations."""
    with TestClient(app) as c:
        yield c

@pytest.fixture
def db_session():
    """Create a database session for testing."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
