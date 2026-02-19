"""Reset test data before this module to avoid cross-module pollution."""
import pytest


@pytest.fixture(scope="module", autouse=True)
def reset_module_test_data():
    """Reset DB data before this module.
    
    We directly replicate the root conftest setup_test_data logic here,
    but import the SAME engine that the root conftest uses via the app
    dependency override chain.
    """
    from plugins_core.default_core import app
    from app.database import get_db, Base
    from app.database_models import User, Role
    from app.auth import hash_api_key, get_password_hash

    # Get the overridden get_db from the app (set by root conftest)
    db_factory = app.dependency_overrides.get(get_db, get_db)
    db = next(db_factory())
    try:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()

        db.add(Role(id=1, name="admin", description="Administrator",
                     permissions={"can_predict": True, "can_view_logs": True, "can_manage_users": True}))
        db.add(Role(id=2, name="client", description="Client",
                     permissions={"can_predict": True, "can_view_logs": False}))
        db.add(Role(id=3, name="operator", description="Operator",
                     permissions={"can_predict": True, "can_view_logs": True}))
        db.add(Role(id=4, name="provider", description="Provider",
                     permissions={"can_predict": True, "can_set_pricing": True}))
        db.commit()

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
            {"username": "provider_user", "email": "provider@test.com", "api_key": "provider_key", "role_id": 4},
        ]
        for u in test_users:
            db.add(User(
                username=u["username"], email=u["email"],
                hashed_password=get_password_hash("testpass123"),
                hashed_api_key=hash_api_key(u["api_key"]),
                is_active=True, role_id=u["role_id"]
            ))
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture(autouse=True)
def reset_rate_limits_per_test():
    """Clear rate limits and concurrent prediction counters before each test."""
    try:
        import plugins_core.default_core as _core
        _core.rate_limit_store.clear()
        _core._concurrent_predictions.clear()
    except Exception:
        pass
    yield
    try:
        import plugins_core.default_core as _core
        _core.rate_limit_store.clear()
        _core._concurrent_predictions.clear()
    except Exception:
        pass

