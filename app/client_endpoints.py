"""
Client API endpoints for the decentralized prediction marketplace.

This module implements the client-facing endpoints for prediction requests,
status checking, and result retrieval as specified in the design documentation.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, validator, field_validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, timezone, timedelta
import uuid
import logging
import hashlib
import json

from app.database import get_db
from app.database_models import User, PredictionJob
from app.auth import get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter(tags=["client"])

# Pydantic models for client endpoints

class PredictionRequest(BaseModel):
    symbol: str = Field(..., pattern="^[A-Z]{3,6}$", description="Financial instrument symbol")
    prediction_type: str = Field(..., pattern="^(short_term|long_term|custom)$")
    datetime_requested: datetime = Field(..., description="Target prediction timestamp")
    lookback_ticks: int = Field(1000, ge=100, le=5000, description="Historical data points required")
    predictor_plugin: str = Field("default_predictor", description="Model plugin to use")
    feeder_plugin: str = Field("default_feeder", description="Data feeder plugin")
    pipeline_plugin: str = Field("default_pipeline", description="Pipeline plugin")
    interval: str = Field("1h", pattern="^(1h|1d|1w|1M)$")
    prediction_horizon: int = Field(6, ge=1, le=24, description="Number of future predictions")
    priority: int = Field(5, ge=1, le=10, description="Request priority level")
    max_cost: Optional[float] = Field(None, ge=0, description="Maximum acceptable cost")
    notification_webhook: Optional[str] = Field(None, description="Webhook URL for notifications")
    custom_parameters: Optional[Dict[str, Any]] = Field(None, description="Additional parameters")

    @field_validator('datetime_requested')
    def validate_datetime_requested(cls, v):
        if v < datetime.now(timezone.utc):
            raise ValueError('datetime_requested must be in the future')
        return v

class PredictionResponse(BaseModel):
    id: str
    task_id: str
    status: str
    estimated_completion: Optional[datetime]
    estimated_cost: float
    queue_position: int
    priority: int
    created_at: datetime

class ProgressInfo(BaseModel):
    percentage: int = Field(ge=0, le=100)
    current_step: str
    estimated_remaining: int = Field(description="Estimated remaining time in seconds")

class EvaluatorInfo(BaseModel):
    evaluator_id: Optional[str]
    username: Optional[str]
    reputation_score: Optional[float]

class CostInfo(BaseModel):
    estimated_cost: float
    actual_cost: Optional[float]
    currency: str = "USD"

class PredictionResult(BaseModel):
    predictions: List[float]
    uncertainties: List[float]
    confidence_intervals: Dict[str, List[float]]
    model_metadata: Dict[str, Any]
    download_links: Dict[str, str]

class DetailedPredictionResponse(BaseModel):
    id: str
    task_id: str
    status: str
    symbol: str
    prediction_type: str
    datetime_requested: datetime
    priority: int
    progress: Optional[ProgressInfo]
    evaluator_info: Optional[EvaluatorInfo]
    cost_info: CostInfo
    result: Optional[PredictionResult]
    created_at: datetime
    claimed_at: Optional[datetime]
    completed_at: Optional[datetime]
    expires_at: Optional[datetime]

class PredictionSummary(BaseModel):
    id: str
    task_id: str
    status: str
    symbol: str
    prediction_type: str
    estimated_cost: float
    actual_cost: Optional[float]
    created_at: datetime
    completed_at: Optional[datetime]

class PredictionListResponse(BaseModel):
    predictions: List[PredictionSummary]
    total_count: int
    page: int
    pages: int
    has_next: bool
    has_prev: bool

class PredictionUpdate(BaseModel):
    priority: Optional[int] = Field(None, ge=1, le=10)
    max_cost: Optional[float] = Field(None, ge=0)
    notification_webhook: Optional[str] = None

# Helper functions

def calculate_estimated_cost(request: PredictionRequest) -> float:
    """Calculate estimated cost for a prediction request"""
    base_costs = {
        "short_term": 5.00,
        "long_term": 12.00,
        "custom": 8.00
    }
    
    base_cost = base_costs.get(request.prediction_type, 8.00)
    
    # Apply complexity multipliers
    complexity_multiplier = 1.0
    
    if request.prediction_horizon > 10:
        complexity_multiplier += 0.2
    if request.lookback_ticks > 2000:
        complexity_multiplier += 0.1
    if "premium" in request.feeder_plugin:
        complexity_multiplier += 0.3
    if "transformer" in request.predictor_plugin or "ensemble" in request.predictor_plugin:
        complexity_multiplier += 0.5
    
    # Priority multiplier
    if request.priority > 7:
        complexity_multiplier += 0.25
    
    return round(base_cost * complexity_multiplier, 2)

def calculate_queue_position(db: Session, priority: int, created_at: datetime) -> int:
    """Calculate position in queue based on priority and creation time"""
    # Count pending requests with higher priority or same priority but earlier creation
    higher_priority = db.query(PredictionJob).filter(
        PredictionJob.status == "pending",
        PredictionJob.request_payload.op('->>')('priority').cast(db.Integer) > priority
    ).count()
    
    same_priority_earlier = db.query(PredictionJob).filter(
        PredictionJob.status == "pending",
        PredictionJob.request_payload.op('->>')('priority').cast(db.Integer) == priority,
        PredictionJob.created_at < created_at
    ).count()
    
    return higher_priority + same_priority_earlier + 1

def generate_download_links(prediction_id: str) -> Dict[str, str]:
    """Generate download links for prediction results"""
    base_url = "/api/v1/predictions"
    return {
        "csv_results": f"{base_url}/{prediction_id}/download/results.csv",
        "plot_image": f"{base_url}/{prediction_id}/download/plot.png",
        "metadata": f"{base_url}/{prediction_id}/download/metadata.json"
    }

# API Endpoints

@router.post("/predict", response_model=PredictionResponse)
async def create_prediction(
    request: PredictionRequest,
    current_user: User = Depends(require_role(["client", "administrator"])),
    db: Session = Depends(get_db)
):
    """Submit new prediction request with comprehensive validation"""
    
    # Check user's active prediction limits
    active_predictions = db.query(PredictionJob).filter(
        PredictionJob.user_id == current_user.id,
        PredictionJob.status.in_(["pending", "processing"])
    ).count()
    
    max_concurrent = 5  # Default limit, would be based on subscription tier
    if active_predictions >= max_concurrent:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Maximum concurrent predictions ({max_concurrent}) exceeded"
        )
    
    # Calculate estimated cost
    estimated_cost = calculate_estimated_cost(request)
    
    # Check if cost exceeds user's maximum
    if request.max_cost and estimated_cost > request.max_cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Estimated cost ({estimated_cost}) exceeds maximum ({request.max_cost})"
        )
    
    # Create prediction job
    prediction_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())
    
    # Prepare request payload
    request_payload = {
        "symbol": request.symbol,
        "prediction_type": request.prediction_type,
        "datetime_requested": request.datetime_requested.isoformat(),
        "lookback_ticks": request.lookback_ticks,
        "predictor_plugin": request.predictor_plugin,
        "feeder_plugin": request.feeder_plugin,
        "pipeline_plugin": request.pipeline_plugin,
        "interval": request.interval,
        "prediction_horizon": request.prediction_horizon,
        "priority": request.priority,
        "max_cost": request.max_cost,
        "notification_webhook": request.notification_webhook,
        "custom_parameters": request.custom_parameters,
        "estimated_cost": estimated_cost
    }
    
    # Create database record
    prediction_job = PredictionJob(
        id=prediction_id,
        user_id=current_user.id,
        ticker=request.symbol,
        model_name=request.predictor_plugin,
        status="pending",
        request_payload=request_payload,
        created_at=datetime.now(timezone.utc)
    )
    
    db.add(prediction_job)
    db.commit()
    db.refresh(prediction_job)
    
    # Calculate queue position
    queue_position = calculate_queue_position(db, request.priority, prediction_job.created_at)
    
    # Estimate completion time based on queue position
    avg_processing_time = 5  # minutes
    estimated_completion = prediction_job.created_at + timedelta(
        minutes=queue_position * avg_processing_time
    )
    
    logger.info(f"Created prediction request {prediction_id} for user {current_user.username}")
    
    return PredictionResponse(
        id=prediction_id,
        task_id=task_id,
        status="pending",
        estimated_completion=estimated_completion,
        estimated_cost=estimated_cost,
        queue_position=queue_position,
        priority=request.priority,
        created_at=prediction_job.created_at
    )

@router.get("/predictions/{id}", response_model=DetailedPredictionResponse)
async def get_prediction(
    id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get detailed prediction status and results"""
    
    # Find prediction job
    prediction_job = db.query(PredictionJob).filter(PredictionJob.id == id).first()
    
    if not prediction_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prediction not found"
        )
    
    # Check permissions (clients can only see their own, admins can see all)
    if (current_user.role.name == "client" and prediction_job.user_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this prediction"
        )
    
    request_payload = prediction_job.request_payload or {}
    
    # Build progress information
    progress = None
    if prediction_job.status == "processing":
        progress = ProgressInfo(
            percentage=request_payload.get("progress_percentage", 65),
            current_step=request_payload.get("current_step", "model_inference"),
            estimated_remaining=request_payload.get("estimated_remaining", 30)
        )
    
    # Build evaluator information
    evaluator_info = None
    claimed_by = request_payload.get("claimed_by")
    if claimed_by:
        evaluator = db.query(User).filter(User.id == claimed_by).first()
        if evaluator:
            evaluator_info = EvaluatorInfo(
                evaluator_id=str(evaluator.id),
                username=evaluator.username,
                reputation_score=4.8  # Placeholder
            )
    
    # Build cost information
    cost_info = CostInfo(
        estimated_cost=request_payload.get("estimated_cost", 0.0),
        actual_cost=request_payload.get("actual_cost"),
        currency="USD"
    )
    
    # Build result information
    result = None
    if prediction_job.status == "completed" and prediction_job.result:
        result_data = prediction_job.result
        result = PredictionResult(
            predictions=result_data.get("predictions", []),
            uncertainties=result_data.get("uncertainties", []),
            confidence_intervals=result_data.get("confidence_intervals", {}),
            model_metadata=result_data.get("model_metadata", {}),
            download_links=generate_download_links(id)
        )
    
    # Parse timestamps
    claimed_at = None
    claimed_at_str = request_payload.get("claimed_at")
    if claimed_at_str:
        claimed_at = datetime.fromisoformat(claimed_at_str.replace('Z', '+00:00'))
    
    expires_at = prediction_job.created_at + timedelta(hours=24)  # 24 hour expiry
    
    return DetailedPredictionResponse(
        id=prediction_job.id,
        task_id=prediction_job.id,
        status=prediction_job.status,
        symbol=prediction_job.ticker,
        prediction_type=request_payload.get("prediction_type", "short_term"),
        datetime_requested=datetime.fromisoformat(
            request_payload.get("datetime_requested", prediction_job.created_at.isoformat())
        ),
        priority=request_payload.get("priority", 5),
        progress=progress,
        evaluator_info=evaluator_info,
        cost_info=cost_info,
        result=result,
        created_at=prediction_job.created_at,
        claimed_at=claimed_at,
        completed_at=prediction_job.completed_at,
        expires_at=expires_at
    )

@router.get("/predictions/", response_model=PredictionListResponse)
async def list_predictions(
    status: Optional[str] = Query(None, pattern="^(pending|processing|completed|failed|cancelled)$"),
    symbol: Optional[str] = Query(None),
    prediction_type: Optional[str] = Query(None, pattern="^(short_term|long_term|custom)$"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort: str = Query("created_at", pattern="^(created_at|completed_at|priority|cost)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List user's prediction requests with filtering and pagination"""
    
    # Build base query
    query = db.query(PredictionJob)
    
    # Apply user filter (clients see only their own, admins see all)
    if current_user.role.name == "client":
        query = query.filter(PredictionJob.user_id == current_user.id)
    
    # Apply filters
    if status:
        query = query.filter(PredictionJob.status == status)
    
    if symbol:
        query = query.filter(PredictionJob.ticker == symbol)
    
    if prediction_type:
        query = query.filter(
            PredictionJob.request_payload.op('->>')('prediction_type') == prediction_type
        )
    
    if start_date:
        query = query.filter(PredictionJob.created_at >= start_date)
    
    if end_date:
        query = query.filter(PredictionJob.created_at <= end_date)
    
    # Apply sorting
    if sort == "created_at":
        sort_column = PredictionJob.created_at
    elif sort == "completed_at":
        sort_column = PredictionJob.completed_at
    elif sort == "priority":
        sort_column = PredictionJob.request_payload.op('->>')('priority').cast(db.Integer)
    elif sort == "cost":
        sort_column = PredictionJob.request_payload.op('->>')('estimated_cost').cast(db.Float)
    else:
        sort_column = PredictionJob.created_at
    
    if order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())
    
    # Get total count
    total_count = query.count()
    
    # Apply pagination
    predictions = query.offset(offset).limit(limit).all()
    
    # Convert to response format
    prediction_summaries = []
    for job in predictions:
        request_payload = job.request_payload or {}
        
        summary = PredictionSummary(
            id=job.id,
            task_id=job.id,
            status=job.status,
            symbol=job.ticker,
            prediction_type=request_payload.get("prediction_type", "short_term"),
            estimated_cost=request_payload.get("estimated_cost", 0.0),
            actual_cost=request_payload.get("actual_cost"),
            created_at=job.created_at,
            completed_at=job.completed_at
        )
        prediction_summaries.append(summary)
    
    # Calculate pagination info
    page = (offset // limit) + 1
    pages = (total_count + limit - 1) // limit
    has_next = offset + limit < total_count
    has_prev = offset > 0
    
    return PredictionListResponse(
        predictions=prediction_summaries,
        total_count=total_count,
        page=page,
        pages=pages,
        has_next=has_next,
        has_prev=has_prev
    )

@router.put("/predictions/{id}", response_model=DetailedPredictionResponse)
async def update_prediction(
    id: str,
    update_data: PredictionUpdate,
    current_user: User = Depends(require_role(["client", "administrator"])),
    db: Session = Depends(get_db)
):
    """Update prediction request (limited fields)"""
    
    # Find prediction job
    prediction_job = db.query(PredictionJob).filter(PredictionJob.id == id).first()
    
    if not prediction_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prediction not found"
        )
    
    # Check permissions
    if (current_user.role.name == "client" and prediction_job.user_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this prediction"
        )
    
    # Only allow updates for pending requests
    if prediction_job.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Can only update pending predictions"
        )
    
    # Update allowed fields
    request_payload = prediction_job.request_payload or {}
    updated = False
    
    if update_data.priority is not None:
        request_payload["priority"] = update_data.priority
        updated = True
    
    if update_data.max_cost is not None:
        request_payload["max_cost"] = update_data.max_cost
        updated = True
    
    if update_data.notification_webhook is not None:
        request_payload["notification_webhook"] = update_data.notification_webhook
        updated = True
    
    if updated:
        prediction_job.request_payload = request_payload
        db.commit()
        db.refresh(prediction_job)
    
    # Return updated prediction details
    return await get_prediction(id, current_user, db)

@router.delete("/predictions/{id}")
async def cancel_prediction(
    id: str,
    current_user: User = Depends(require_role(["client", "administrator"])),
    db: Session = Depends(get_db)
):
    """Cancel pending prediction request"""
    
    # Find prediction job
    prediction_job = db.query(PredictionJob).filter(PredictionJob.id == id).first()
    
    if not prediction_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prediction not found"
        )
    
    # Check permissions
    if (current_user.role.name == "client" and prediction_job.user_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this prediction"
        )
    
    # Only allow cancellation of pending requests
    if prediction_job.status not in ["pending"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Can only cancel pending predictions"
        )
    
    # Update status to cancelled
    prediction_job.status = "cancelled"
    prediction_job.completed_at = datetime.now(timezone.utc)
    
    # Add cancellation info to request payload
    request_payload = prediction_job.request_payload or {}
    request_payload.update({
        "cancelled_by": current_user.id,
        "cancelled_at": datetime.now(timezone.utc).isoformat(),
        "cancellation_reason": "user_requested"
    })
    prediction_job.request_payload = request_payload
    
    db.commit()
    
    # Calculate refund amount (if applicable)
    estimated_cost = request_payload.get("estimated_cost", 0.0)
    refund_amount = estimated_cost  # Full refund for pending requests
    
    logger.info(f"Cancelled prediction {id} for user {current_user.username}")
    
    return {
        "success": True,
        "message": "Prediction cancelled successfully",
        "refund_amount": refund_amount,
        "currency": "USD"
    }

@router.get("/predictions/{id}/download/{file_type}")
async def download_prediction_file(
    id: str,
    file_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Download prediction result files"""
    
    # Validate file type
    allowed_types = ["results.csv", "plot.png", "metadata.json", "logs.txt"]
    if file_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_types)}"
        )
    
    # Find prediction job
    prediction_job = db.query(PredictionJob).filter(PredictionJob.id == id).first()
    
    if not prediction_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prediction not found"
        )
    
    # Check permissions
    if (current_user.role.name == "client" and prediction_job.user_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this prediction"
        )
    
    # Check if prediction is completed
    if prediction_job.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Prediction must be completed to download files"
        )
    
    # For now, return a placeholder response
    # In production, this would stream the actual file
    return {
        "message": f"Download endpoint for {file_type}",
        "prediction_id": id,
        "file_type": file_type,
        "download_url": f"/api/v1/predictions/{id}/download/{file_type}",
        "note": "This endpoint would stream the actual file in production"
    }
