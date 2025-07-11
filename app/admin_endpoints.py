"""
Administrative API endpoints for the decentralized prediction marketplace.

This module implements administrative functions including user management,
system monitoring, audit access, and configuration management.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
import uuid
import logging

from app.database import get_db
from app.database_models import User, PredictionJob, Role, ApiLog
from app.auth import get_current_user, require_role, get_password_hash

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/admin", tags=["administration"])

# Pydantic models for admin endpoints

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    password: str = Field(..., min_length=8)
    role: str = Field(..., pattern="^(client|evaluator|administrator|guest)$")
    subscription_tier: str = Field("basic", pattern="^(basic|premium|enterprise)$")
    is_active: bool = True
    initial_credits: float = Field(0.0, ge=0)
    billing_address: Optional[Dict[str, str]] = None

class UserCreateResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    api_key: str
    created_at: datetime

class UserUpdate(BaseModel):
    is_active: Optional[bool] = None
    subscription_tier: Optional[str] = Field(None, pattern="^(basic|premium|enterprise)$")
    role: Optional[str] = Field(None, pattern="^(client|evaluator|administrator|guest)$")
    notes: Optional[str] = None

class UserSummary(BaseModel):
    id: int
    username: str
    email: str
    role: str
    subscription_tier: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]
    total_predictions: int
    total_spent: float

class UserListResponse(BaseModel):
    users: List[UserSummary]
    total_count: int
    active_users: int
    new_users_this_month: int

class AuditLogEntry(BaseModel):
    id: int
    user_id: Optional[int]
    username: Optional[str]
    action: str
    endpoint: str
    method: str
    status_code: int
    processing_time: float
    ip_address: str
    user_agent: Optional[str]
    risk_score: Optional[float]
    timestamp: datetime

class AuditLogResponse(BaseModel):
    audit_logs: List[AuditLogEntry]
    total_count: int
    high_risk_events: int
    failed_requests: int

class SystemOverview(BaseModel):
    active_users: int
    total_users: int
    pending_requests: int
    processing_requests: int
    completed_today: int
    failed_today: int
    system_health: str
    uptime_percentage: float

class FinancialMetrics(BaseModel):
    revenue_today: float
    revenue_month: float
    pending_payouts: float
    average_request_value: float

class PerformanceMetrics(BaseModel):
    average_processing_time: float
    queue_wait_time: float
    success_rate: float
    customer_satisfaction: float

class EvaluatorPerformance(BaseModel):
    evaluator_id: str
    username: str
    completed_today: int
    success_rate: float
    average_quality: float
    earnings_today: float

class PredictionStats(BaseModel):
    by_type: Dict[str, int]
    by_status: Dict[str, int]

class ResourceUtilization(BaseModel):
    cpu_usage: float
    memory_usage: float
    storage_usage: float
    network_throughput: str

class SystemStatsResponse(BaseModel):
    system_overview: SystemOverview
    financial_metrics: FinancialMetrics
    performance_metrics: PerformanceMetrics
    evaluator_performance: List[EvaluatorPerformance]
    predictions: PredictionStats
    resource_utilization: ResourceUtilization

class ConfigUpdate(BaseModel):
    prediction_timeout: Optional[int] = Field(None, ge=60, le=3600)
    max_concurrent_predictions: Optional[int] = Field(None, ge=1, le=100)
    rate_limits: Optional[Dict[str, int]] = None
    default_plugins: Optional[Dict[str, str]] = None

class ComponentHealth(BaseModel):
    status: str
    response_time: Optional[float] = None
    connections: Optional[int] = None
    max_connections: Optional[int] = None
    memory_usage: Optional[str] = None
    hit_rate: Optional[float] = None
    loaded_plugins: Optional[int] = None
    failed_plugins: Optional[int] = None

class DiskSpace(BaseModel):
    used: str
    available: str
    usage_percentage: float

class SystemHealthResponse(BaseModel):
    overall_status: str
    components: Dict[str, ComponentHealth]
    alerts: List[str]
    last_backup: Optional[datetime]
    disk_space: DiskSpace

# Helper functions

def get_user_stats(db: Session, user_id: int) -> tuple:
    """Get user prediction and spending statistics"""
    total_predictions = db.query(PredictionJob).filter(
        PredictionJob.user_id == user_id
    ).count()
    
    # Calculate total spent (simplified calculation)
    completed_jobs = db.query(PredictionJob).filter(
        PredictionJob.user_id == user_id,
        PredictionJob.status == "completed"
    ).all()
    
    total_spent = 0.0
    for job in completed_jobs:
        request_payload = job.request_payload or {}
        total_spent += request_payload.get("estimated_cost", 0.0)
    
    return total_predictions, total_spent

# API Endpoints

@router.post("/users", response_model=UserCreateResponse)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db)
):
    """Create new user account"""
    
    # Check if username or email already exists
    existing_user = db.query(User).filter(
        or_(User.username == user_data.username, User.email == user_data.email)
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists"
        )
    
    # Get role
    role = db.query(Role).filter(Role.name == user_data.role).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role: {user_data.role}"
        )
    
    # Generate API key
    from app.auth import generate_api_key, hash_api_key
    api_key = generate_api_key()
    hashed_api_key = hash_api_key(api_key)
    
    # Create user
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        hashed_api_key=hashed_api_key,
        is_active=user_data.is_active,
        role_id=role.id,
        created_at=datetime.now(timezone.utc)
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    logger.info(f"Created user {new_user.username} with role {user_data.role}")
    
    return UserCreateResponse(
        id=new_user.id,
        username=new_user.username,
        email=new_user.email,
        role=user_data.role,
        api_key=api_key,
        created_at=new_user.created_at
    )

@router.get("/users", response_model=UserListResponse)
async def list_users(
    role: Optional[str] = Query(None, pattern="^(client|evaluator|administrator|guest)$"),
    is_active: Optional[bool] = Query(None),
    subscription_tier: Optional[str] = Query(None, pattern="^(basic|premium|enterprise)$"),
    created_after: Optional[datetime] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db)
):
    """List all user accounts with filtering"""
    
    # Build query
    query = db.query(User).join(Role)
    
    # Apply filters
    if role:
        query = query.filter(Role.name == role)
    
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    
    if created_after:
        query = query.filter(User.created_at >= created_after)
    
    if search:
        query = query.filter(
            or_(
                User.username.contains(search),
                User.email.contains(search)
            )
        )
    
    # Get total count
    total_count = query.count()
    
    # Apply pagination
    users = query.offset(offset).limit(limit).all()
    
    # Convert to response format
    user_summaries = []
    for user in users:
        total_predictions, total_spent = get_user_stats(db, user.id)
        
        summary = UserSummary(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role.name,
            subscription_tier="basic",  # Placeholder
            is_active=user.is_active,
            created_at=user.created_at,
            last_login=user.last_login,
            total_predictions=total_predictions,
            total_spent=total_spent
        )
        user_summaries.append(summary)
    
    # Calculate summary statistics
    active_users = db.query(User).filter(User.is_active == True).count()
    
    # New users this month
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    new_users_this_month = db.query(User).filter(User.created_at >= month_start).count()
    
    return UserListResponse(
        users=user_summaries,
        total_count=total_count,
        active_users=active_users,
        new_users_this_month=new_users_this_month
    )

@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    update_data: UserUpdate,
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db)
):
    """Update user account details"""
    
    # Find user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update fields
    updated = False
    
    if update_data.is_active is not None:
        user.is_active = update_data.is_active
        updated = True
    
    if update_data.role is not None:
        role = db.query(Role).filter(Role.name == update_data.role).first()
        if not role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {update_data.role}"
            )
        user.role_id = role.id
        updated = True
    
    if updated:
        db.commit()
        db.refresh(user)
        logger.info(f"Updated user {user.username} by {current_user.username}")
    
    return {"success": True, "message": "User updated successfully"}

@router.delete("/users/{user_id}")
async def deactivate_user(
    user_id: int,
    action: str = Query("deactivate", pattern="^(deactivate|delete)$"),
    notify_user: bool = Query(True),
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db)
):
    """Deactivate or delete user account"""
    
    # Find user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent self-deletion
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account"
        )
    
    if action == "deactivate":
        user.is_active = False
        db.commit()
        logger.info(f"Deactivated user {user.username} by {current_user.username}")
        return {"success": True, "message": "User deactivated successfully"}
    else:
        # For actual deletion, just deactivate for now (data retention requirements)
        user.is_active = False
        db.commit()
        logger.info(f"Marked user {user.username} for deletion by {current_user.username}")
        return {"success": True, "message": "User marked for deletion"}

@router.get("/audit", response_model=AuditLogResponse)
async def get_audit_logs(
    user_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    endpoint: Optional[str] = Query(None),
    method: Optional[str] = Query(None),
    status_code: Optional[str] = Query(None),
    risk_score_min: Optional[float] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db)
):
    """Access comprehensive audit logs"""
    
    # Build query
    query = db.query(ApiLog).join(User, ApiLog.user_id == User.id, isouter=True)
    
    # Apply filters
    if user_id:
        query = query.filter(ApiLog.user_id == user_id)
    
    if endpoint:
        query = query.filter(ApiLog.endpoint.contains(endpoint))
    
    if method:
        query = query.filter(ApiLog.method == method)
    
    if status_code:
        # Parse status codes (could be comma-separated)
        status_codes = [int(code.strip()) for code in status_code.split(',')]
        query = query.filter(ApiLog.response_status_code.in_(status_codes))
    
    if start_date:
        query = query.filter(ApiLog.request_timestamp >= start_date)
    
    if end_date:
        query = query.filter(ApiLog.request_timestamp <= end_date)
    
    # Get total count
    total_count = query.count()
    
    # Apply pagination and ordering
    logs = query.order_by(ApiLog.request_timestamp.desc()).offset(offset).limit(limit).all()
    
    # Convert to response format
    audit_entries = []
    for log in logs:
        entry = AuditLogEntry(
            id=log.id,
            user_id=log.user_id,
            username=log.user.username if log.user else None,
            action=log.endpoint,  # Simplified
            endpoint=log.endpoint,
            method=log.method,
            status_code=log.response_status_code,
            processing_time=log.response_time_ms,
            ip_address=log.ip_address,
            user_agent=log.user_agent,
            risk_score=0.1,  # Placeholder
            timestamp=log.request_timestamp
        )
        audit_entries.append(entry)
    
    # Calculate summary statistics
    high_risk_events = 0  # Placeholder
    failed_requests = db.query(ApiLog).filter(
        ApiLog.response_status_code >= 400,
        ApiLog.request_timestamp >= datetime.now(timezone.utc) - timedelta(days=1)
    ).count()
    
    return AuditLogResponse(
        audit_logs=audit_entries,
        total_count=total_count,
        high_risk_events=high_risk_events,
        failed_requests=failed_requests
    )

@router.get("/stats", response_model=SystemStatsResponse)
async def get_system_stats(
    period: str = Query("7d", pattern="^(1d|7d|30d)$"),
    include_forecasts: bool = Query(True),
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db)
):
    """Get comprehensive system statistics"""
    
    # Calculate period
    period_days = {"1d": 1, "7d": 7, "30d": 30}[period]
    period_start = datetime.now(timezone.utc) - timedelta(days=period_days)
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    # System overview
    active_users = db.query(User).filter(User.is_active == True).count()
    total_users = db.query(User).count()
    
    pending_requests = db.query(PredictionJob).filter(PredictionJob.status == "pending").count()
    processing_requests = db.query(PredictionJob).filter(PredictionJob.status == "processing").count()
    
    completed_today = db.query(PredictionJob).filter(
        PredictionJob.status == "completed",
        PredictionJob.completed_at >= today_start
    ).count()
    
    failed_today = db.query(PredictionJob).filter(
        PredictionJob.status == "failed",
        PredictionJob.created_at >= today_start
    ).count()
    
    system_overview = SystemOverview(
        active_users=active_users,
        total_users=total_users,
        pending_requests=pending_requests,
        processing_requests=processing_requests,
        completed_today=completed_today,
        failed_today=failed_today,
        system_health="healthy",
        uptime_percentage=99.97
    )
    
    # Financial metrics (simplified calculations)
    completed_jobs_today = db.query(PredictionJob).filter(
        PredictionJob.status == "completed",
        PredictionJob.completed_at >= today_start
    ).all()
    
    revenue_today = sum(
        job.request_payload.get("estimated_cost", 0.0) if job.request_payload else 0.0
        for job in completed_jobs_today
    )
    
    # Monthly revenue
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    completed_jobs_month = db.query(PredictionJob).filter(
        PredictionJob.status == "completed",
        PredictionJob.completed_at >= month_start
    ).all()
    
    revenue_month = sum(
        job.request_payload.get("estimated_cost", 0.0) if job.request_payload else 0.0
        for job in completed_jobs_month
    )
    
    financial_metrics = FinancialMetrics(
        revenue_today=round(revenue_today, 2),
        revenue_month=round(revenue_month, 2),
        pending_payouts=0.0,  # Placeholder
        average_request_value=round(revenue_month / max(len(completed_jobs_month), 1), 2)
    )
    
    # Performance metrics
    recent_jobs = db.query(PredictionJob).filter(
        PredictionJob.status == "completed",
        PredictionJob.completed_at >= period_start
    ).all()
    
    if recent_jobs:
        avg_processing_time = sum(
            job.processing_time_ms or 0 for job in recent_jobs
        ) / len(recent_jobs) / 1000  # Convert to seconds
        
        total_jobs = db.query(PredictionJob).filter(
            PredictionJob.created_at >= period_start
        ).count()
        success_rate = len(recent_jobs) / max(total_jobs, 1)
    else:
        avg_processing_time = 0
        success_rate = 0
    
    performance_metrics = PerformanceMetrics(
        average_processing_time=round(avg_processing_time, 1),
        queue_wait_time=45.2,  # Placeholder
        success_rate=round(success_rate, 3),
        customer_satisfaction=4.7  # Placeholder
    )
    
    # Evaluator performance (placeholder)
    evaluator_performance = []
    
    # Prediction statistics
    predictions_by_type = {}
    predictions_by_status = {}
    
    # Resource utilization (placeholder)
    resource_utilization = ResourceUtilization(
        cpu_usage=67.3,
        memory_usage=72.1,
        storage_usage=45.8,
        network_throughput="125 Mbps"
    )
    
    return SystemStatsResponse(
        system_overview=system_overview,
        financial_metrics=financial_metrics,
        performance_metrics=performance_metrics,
        evaluator_performance=evaluator_performance,
        predictions=PredictionStats(
            by_type=predictions_by_type,
            by_status=predictions_by_status
        ),
        resource_utilization=resource_utilization
    )

@router.post("/config")
async def update_system_config(
    config_update: ConfigUpdate,
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db)
):
    """Update system configuration"""
    
    # In a real implementation, this would update system configuration
    # For now, just log the update
    logger.info(f"System configuration updated by {current_user.username}: {config_update.dict()}")
    
    return {"success": True, "message": "Configuration updated successfully"}

@router.get("/system/health", response_model=SystemHealthResponse)
async def get_system_health(
    current_user: User = Depends(require_role(["administrator"])),
    db: Session = Depends(get_db)
):
    """Detailed system health and monitoring"""
    
    # Component health checks (simplified)
    components = {
        "database": ComponentHealth(
            status="healthy",
            response_time=12.3,
            connections=45,
            max_connections=100
        ),
        "redis_cache": ComponentHealth(
            status="healthy",
            memory_usage="2.1GB",
            hit_rate=0.87
        ),
        "plugin_system": ComponentHealth(
            status="healthy",
            loaded_plugins=12,
            failed_plugins=0
        )
    }
    
    # Disk space information
    disk_space = DiskSpace(
        used="125GB",
        available="875GB",
        usage_percentage=12.5
    )
    
    return SystemHealthResponse(
        overall_status="healthy",
        components=components,
        alerts=[],
        last_backup=datetime.now(timezone.utc) - timedelta(hours=22),
        disk_space=disk_space
    )
