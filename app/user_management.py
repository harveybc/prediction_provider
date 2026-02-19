from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import uuid
import logging
import time
from app.database import get_db
from app.database_models import User, Role, ApiLog, PredictionJob
from app.auth import (
    get_current_user, 
    require_admin, 
    require_admin_or_operator,
    authenticate_user,
    get_password_hash,
    verify_password,
    create_access_token,
    generate_api_key,
    hash_api_key
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Pydantic models
class UserCreate(BaseModel):
    username: str
    email: str = Field(..., pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    role: str = "client"

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    role: str
    created_at: datetime
    api_key: Optional[str] = None  # Only returned on user creation

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class ApiKeyResponse(BaseModel):
    api_key: str
    expires_in_days: int = 90

class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str

class UsageStats(BaseModel):
    total_requests: int
    total_predictions: int
    total_processing_time_ms: float
    cost_estimate: float

class LogEntry(BaseModel):
    id: int
    request_id: str
    user_id: Optional[int]
    ip_address: str
    endpoint: str
    method: str
    request_timestamp: datetime
    response_status_code: int
    response_time_ms: float
    request_payload: Optional[dict] = None

class LogsResponse(BaseModel):
    logs: List[LogEntry]
    total: int

# Authentication endpoints
@router.post("/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """User login with username and password"""
    user = authenticate_user(db, request.username, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is not active",
        )
    
    # Update last login
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    
    # Create access token
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/auth/api-key", response_model=ApiKeyResponse)
async def get_api_key(request: LoginRequest, db: Session = Depends(get_db)):
    """Get API key for authentication"""
    user = authenticate_user(db, request.username, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is not active",
        )
    
    # Generate new API key
    api_key = generate_api_key()
    user.hashed_api_key = hash_api_key(api_key)
    db.commit()
    
    return {"api_key": api_key, "expires_in_days": 90}

@router.post("/auth/regenerate-key", response_model=ApiKeyResponse)
async def regenerate_api_key(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Regenerate API key"""
    api_key = generate_api_key()
    current_user.hashed_api_key = hash_api_key(api_key)
    db.commit()
    
    return {"api_key": api_key, "expires_in_days": 90}

# User management endpoints
@router.post("/admin/users", response_model=UserResponse, status_code=201)
async def create_user(user_data: UserCreate, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Create a new user (Admin only)"""
    # Check if username already exists
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        )
    
    # Check if email already exists
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists",
        )
    
    # Get role
    role = db.query(Role).filter(Role.name == user_data.role).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role '{user_data.role}' does not exist",
        )
    
    # Create user with default password
    default_password = "password"  # Should be randomly generated and sent via email
    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(default_password),
        role_id=role.id,
        is_active=False  # Requires activation
    )
    
    # Generate API key for the new user
    api_key = generate_api_key()
    user.hashed_api_key = hash_api_key(api_key)
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        role=user.role.name,
        created_at=user.created_at,
        api_key=api_key
    )

@router.post("/admin/users/{username}/activate")
async def activate_user(username: str, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Activate a user (Admin only)"""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    user.is_active = True
    db.commit()
    
    return {"message": f"User {username} activated successfully"}

@router.post("/admin/users/{username}/deactivate")
async def deactivate_user(username: str, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Deactivate a user (Admin only)"""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    user.is_active = False
    db.commit()
    
    return {"message": f"User {username} deactivated successfully"}

@router.get("/admin/users", response_model=List[UserResponse])
async def list_users(current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """List all users (Admin only)"""
    users = db.query(User).all()
    return [
        UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
            role=user.role.name,
            created_at=user.created_at
        )
        for user in users
    ]

# User profile endpoints
@router.get("/users/profile", response_model=UserResponse)
async def get_profile(current_user: User = Depends(get_current_user)):
    """Get current user profile"""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        is_active=current_user.is_active,
        role=current_user.role.name,
        created_at=current_user.created_at
    )

@router.put("/users/password")
async def change_password(request: PasswordChangeRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Change user password"""
    if not verify_password(request.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid old password",
        )
    
    current_user.hashed_password = get_password_hash(request.new_password)
    db.commit()
    
    return {"message": "Password changed successfully"}

# Logging and monitoring endpoints
@router.get("/admin/logs", response_model=LogsResponse)
async def get_logs(
    user: Optional[str] = None,
    endpoint: Optional[str] = None,
    hours: int = 24,
    current_user: User = Depends(require_admin_or_operator),
    db: Session = Depends(get_db)
):
    """Get system logs (Admin/Operator only)"""
    query = db.query(ApiLog)
    
    if user:
        user_obj = db.query(User).filter(User.username == user).first()
        if user_obj:
            query = query.filter(ApiLog.user_id == user_obj.id)
    
    if endpoint:
        query = query.filter(ApiLog.endpoint == endpoint)
    
    # Filter by time
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    query = query.filter(ApiLog.request_timestamp >= cutoff_time)
    
    logs = query.order_by(ApiLog.request_timestamp.desc()).limit(1000).all()
    
    return LogsResponse(
        logs=[
            LogEntry(
                id=log.id,
                request_id=log.request_id,
                user_id=log.user_id,
                ip_address=log.ip_address,
                endpoint=log.endpoint,
                method=log.method,
                request_timestamp=log.request_timestamp,
                response_status_code=log.response_status_code,
                response_time_ms=log.response_time_ms,
                request_payload=log.request_payload
            )
            for log in logs
        ],
        total=len(logs)
    )

@router.get("/admin/usage/{username}", response_model=UsageStats)
async def get_usage_stats(
    username: str,
    days: int = 30,
    current_user: User = Depends(require_admin_or_operator),
    db: Session = Depends(get_db)
):
    """Get usage statistics for a user (Admin/Operator only)"""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Calculate usage stats
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Get API logs for the user
    logs = db.query(ApiLog).filter(
        ApiLog.user_id == user.id,
        ApiLog.request_timestamp >= cutoff_time
    ).all()
    
    # Get predictions for the user
    predictions = db.query(PredictionJob).filter(
        PredictionJob.user_id == user.id,
        PredictionJob.created_at >= cutoff_time
    ).all()
    
    total_requests = len(logs)
    total_predictions = len(predictions)
    total_processing_time = sum(p.processing_time_ms or 0 for p in predictions)
    
    # Simple cost calculation (would be more complex in real system)
    cost_per_prediction = 0.10  # $0.10 per prediction
    cost_estimate = total_predictions * cost_per_prediction
    
    return UsageStats(
        total_requests=total_requests,
        total_predictions=total_predictions,
        total_processing_time_ms=total_processing_time,
        cost_estimate=cost_estimate
    )

# Request logging middleware would be added to the main app
async def log_request(request: Request, call_next):
    """Middleware to log all requests"""
    start_time = time.time()
    request_id = str(uuid.uuid4())
    
    # Process request
    response = await call_next(request)
    
    # Calculate response time
    process_time = (time.time() - start_time) * 1000  # Convert to milliseconds
    
    # Log the request (would be done in background task)
    # This is a simplified version - in production, use proper async logging
    
    return response
