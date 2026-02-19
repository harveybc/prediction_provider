"""
Security tests for Prediction Provider billing: accuracy, provider pricing, spend.
"""
import pytest
from fastapi.testclient import TestClient
from plugins_core.default_core import app
from app.database_models import BillingRecord, ProviderPricing, Role
from app.database import Base, engine
from sqlalchemy.orm import sessionmaker
from app.auth import hash_api_key, get_password_hash
from app.database_models import User
from datetime import datetime, timezone


@pytest.fixture(scope="module")
def setup_billing_data():
    """Setup billing test data"""
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        # Ensure provider role exists
        provider_role = db.query(Role).filter(Role.name == "provider").first()
        if not provider_role:
            provider_role = Role(id=4, name="provider", description="Provider", permissions={"can_predict": True, "can_set_pricing": True})
            db.add(provider_role)
            db.commit()
        
        # Create provider user if not exists
        provider = db.query(User).filter(User.username == "provider_user").first()
        if not provider:
            provider = User(
                username="provider_user", email="provider@test.com",
                hashed_password=get_password_hash("testpass123"),
                hashed_api_key=hash_api_key("provider_key"),
                is_active=True, role_id=provider_role.id
            )
            db.add(provider)
            db.commit()
        
        # Add some billing records
        admin = db.query(User).filter(User.username == "admin_user").first()
        client = db.query(User).filter(User.username == "test_user").first()
        
        if admin and client and provider:
            # Add billing record
            record = BillingRecord(
                client_id=client.id, provider_id=provider.id,
                prediction_id=None, cost=5.00, currency="USD",
                timestamp=datetime.now(timezone.utc)
            )
            db.add(record)
            
            # Add provider pricing
            pricing = ProviderPricing(
                provider_id=provider.id, model_name="test_model",
                price_per_request=2.50, currency="USD", is_active=True
            )
            db.add(pricing)
            db.commit()
    except Exception as e:
        db.rollback()
        print(f"Setup error: {e}")
    finally:
        db.close()
    yield


@pytest.fixture
def client(setup_billing_data):
    return TestClient(app)


class TestBillingAccuracy:
    def test_admin_billing_returns_records(self, client):
        resp = client.get("/api/v1/admin/billing", headers={"X-API-KEY": "admin_key"})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_admin_billing_summary(self, client):
        resp = client.get("/api/v1/admin/billing/summary", headers={"X-API-KEY": "admin_key"})
        assert resp.status_code == 200
        data = resp.json()
        assert "total_revenue" in data
        assert "total_transactions" in data
        assert data["currency"] == "USD"

    def test_client_spend_accurate(self, client):
        resp = client.get("/api/v1/client/spend", headers={"X-API-KEY": "test_key"})
        assert resp.status_code == 200
        data = resp.json()
        assert "total_spent" in data
        assert data["total_spent"] >= 0

    def test_client_billing_history(self, client):
        resp = client.get("/api/v1/client/billing", headers={"X-API-KEY": "test_key"})
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestProviderPricing:
    def test_provider_can_set_pricing(self, client):
        resp = client.post("/api/v1/provider/pricing", json={
            "model_name": "new_model", "price_per_request": 3.50, "currency": "USD"
        }, headers={"X-API-KEY": "provider_key"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["price_per_request"] == 3.50

    def test_provider_can_view_pricing(self, client):
        resp = client.get("/api/v1/provider/pricing", headers={"X-API-KEY": "provider_key"})
        assert resp.status_code == 200

    def test_provider_earnings(self, client):
        resp = client.get("/api/v1/provider/earnings", headers={"X-API-KEY": "provider_key"})
        assert resp.status_code == 200
        data = resp.json()
        assert "total_earnings" in data

    def test_client_cannot_set_pricing(self, client):
        resp = client.post("/api/v1/provider/pricing", json={
            "model_name": "hack_model", "price_per_request": 0.01, "currency": "USD"
        }, headers={"X-API-KEY": "test_key"})
        assert resp.status_code == 403

    def test_admin_can_view_all_pricing(self, client):
        resp = client.get("/api/v1/admin/pricing", headers={"X-API-KEY": "admin_key"})
        assert resp.status_code == 200


class TestBillingAccessControl:
    def test_client_cannot_see_admin_billing(self, client):
        resp = client.get("/api/v1/admin/billing", headers={"X-API-KEY": "test_key"})
        assert resp.status_code == 403

    def test_client_cannot_see_admin_summary(self, client):
        resp = client.get("/api/v1/admin/billing/summary", headers={"X-API-KEY": "test_key"})
        assert resp.status_code == 403

    def test_no_auth_billing_rejected(self, client):
        import os
        os.environ["REQUIRE_AUTH"] = "true"
        resp = client.get("/api/v1/client/spend")
        assert resp.status_code in [401, 403]
        os.environ.pop("REQUIRE_AUTH", None)
