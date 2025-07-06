#!/usr/bin/env python3
"""Debug test to check what's causing the hanging issue"""

import os
import sys

# Remove existing test database
if os.path.exists("test.db"):
    os.remove("test.db")

try:
    print("1. Importing FastAPI...")
    from fastapi import FastAPI
    print("✅ FastAPI imported")
    
    print("2. Importing database modules...")
    from app.database import Base, engine, get_db
    from app.database_models import User, Role
    print("✅ Database modules imported")
    
    print("3. Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("✅ Tables created")
    
    print("4. Importing auth modules...")
    from app.auth import get_password_hash, hash_api_key
    print("✅ Auth modules imported")
    
    print("5. Importing plugins_core...")
    from plugins_core.default_core import app
    print("✅ plugins_core imported")
    
    print("6. Creating test client...")
    from fastapi.testclient import TestClient
    client = TestClient(app)
    print("✅ Test client created")
    
    print("7. Testing health endpoint...")
    response = client.get("/health")
    print(f"✅ Health endpoint response: {response.status_code}")
    
    print("8. Setting up test database...")
    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    # Create roles
    admin_role = Role(
        name="admin", 
        description="Administrator",
        permissions={"can_predict": True, "can_view_logs": True, "can_manage_users": True}
    )
    client_role = Role(
        name="client", 
        description="Client",
        permissions={"can_predict": True, "can_view_logs": False}
    )
    
    db.add(admin_role)
    db.add(client_role)
    db.commit()
    
    # Create admin user
    admin_user = User(
        username="admin_user",
        email="admin@test.com",
        hashed_password=get_password_hash("testpass123"),
        hashed_api_key=hash_api_key("admin_key"),
        is_active=True,
        role_id=admin_role.id
    )
    db.add(admin_user)
    db.commit()
    db.close()
    
    print("✅ Test database setup complete")
    
    print("9. Testing admin endpoint...")
    
    # Override database dependency
    def override_get_db():
        try:
            db = SessionLocal()
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    
    response = client.get("/api/v1/admin/users", headers={"X-API-KEY": "admin_key"})
    print(f"✅ Admin endpoint response: {response.status_code}")
    if response.status_code != 200:
        print(f"❌ Response content: {response.text}")
    else:
        print(f"✅ Response: {response.json()}")
    
    print("10. Testing user creation...")
    response = client.post(
        "/api/v1/admin/users",
        json={
            "username": "test_user",
            "email": "test@example.com",
            "role": "client"
        },
        headers={"X-API-KEY": "admin_key"}
    )
    print(f"✅ User creation response: {response.status_code}")
    if response.status_code == 201:
        data = response.json()
        print(f"✅ User created with API key: {'api_key' in data}")
        if 'api_key' in data:
            print(f"✅ API key returned: {data['api_key'][:10]}...")
        else:
            print(f"❌ No API key in response: {list(data.keys())}")
    else:
        print(f"❌ User creation failed: {response.text}")

except Exception as e:
    import traceback
    print(f"❌ Error: {e}")
    print(f"❌ Traceback: {traceback.format_exc()}")
finally:
    # Cleanup
    if os.path.exists("test.db"):
        os.remove("test.db")
