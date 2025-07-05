#!/usr/bin/env python3
"""
Database initialization script for the Prediction Provider system.
Creates tables and inserts default roles and admin user.
"""

import os
import sys
from datetime import datetime, timezone

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database_models import Role, User
from app.database import Base, engine, SessionLocal
from app.config import DEFAULT_VALUES

def get_password_hash(password: str) -> str:
    """Simple password hashing for initialization"""
    import hashlib
    return hashlib.sha256(password.encode()).hexdigest()

def create_database(database_url: str = None):
    """Create database tables and insert default data"""
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Create session
    db = SessionLocal()
    
    try:
        # Create default roles if they don't exist
        roles_data = [
            {
                "name": "admin",
                "description": "System administrator with full access",
                "permissions": {
                    "can_predict": True,
                    "can_manage_users": True,
                    "can_view_logs": True,
                    "can_manage_system": True,
                    "can_access_admin_endpoints": True
                }
            },
            {
                "name": "client",
                "description": "Regular client user",
                "permissions": {
                    "can_predict": True,
                    "can_manage_users": False,
                    "can_view_logs": False,
                    "can_manage_system": False,
                    "can_access_admin_endpoints": False
                }
            },
            {
                "name": "operator",
                "description": "System operator with monitoring access",
                "permissions": {
                    "can_predict": False,
                    "can_manage_users": False,
                    "can_view_logs": True,
                    "can_manage_system": False,
                    "can_access_admin_endpoints": True
                }
            }
        ]
        
        for role_data in roles_data:
            existing_role = db.query(Role).filter(Role.name == role_data["name"]).first()
            if not existing_role:
                role = Role(
                    name=role_data["name"],
                    description=role_data["description"],
                    permissions=role_data["permissions"]
                )
                db.add(role)
                print(f"Created role: {role_data['name']}")
        
        # Create default admin user if it doesn't exist
        admin_role = db.query(Role).filter(Role.name == "admin").first()
        if admin_role:
            existing_admin = db.query(User).filter(User.username == "admin").first()
            if not existing_admin:
                admin_user = User(
                    username="admin",
                    email="admin@example.com",
                    hashed_password=get_password_hash("admin123"),
                    role_id=admin_role.id,
                    is_active=True  # Admin is active by default
                )
                db.add(admin_user)
                print("Created default admin user (username: admin, password: admin123)")
        
        # Commit all changes
        db.commit()
        print("Database initialization completed successfully!")
        
    except Exception as e:
        print(f"Error during database initialization: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    create_database()
