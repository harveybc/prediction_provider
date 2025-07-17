"""
Evaluator API endpoints for the decentralized prediction marketplace.

This module implements the evaluator workflow endpoints as specified in the 
design documentation, including queue management, request claiming, and result submission.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
import uuid
import logging
import hashlib
import json

from app.database import get_db
from app.database_models import User, PredictionJob, Role
from app.auth import get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/evaluator", tags=["evaluator"])

# Pydantic models for evaluator endpoints

class PendingRequestSummary(BaseModel):
    id: str
    task_id: str
    symbol: str
    prediction_type: str
    datetime_requested: datetime
    lookback_ticks: int
    predictor_plugin: str
    feeder_plugin: str
    pipeline_plugin: str
    interval: str
    prediction_horizon: int
    priority: int
    estimated_payment: float
    estimated_effort: str
    data_complexity: str
    client_tier: str
    created_at: datetime
    expires_at: Optional[datetime]
    requirements: Dict[str, Any]

class PendingRequestsResponse(BaseModel):
    pending_requests: List[PendingRequestSummary]
    total_pending: int
    estimated_queue_time: str
    payment_range: Dict[str, float]

class ClaimRequest(BaseModel):
    estimated_completion: Optional[datetime] = None
    processing_node_info: Optional[Dict[str, Any]] = None

class ClaimResponse(BaseModel):
    success: bool
    request_id: str
    task_id: str
    claimed_at: datetime
    timeout_at: datetime
    expected_payment: float
    processing_details: Dict[str, Any]

class SubmitRequest(BaseModel):
    predictions: List[float]
    uncertainties: List[float]
    confidence_intervals: Dict[str, List[float]]
    model_metadata: Dict[str, Any]
    processing_log: Optional[str] = None
    resource_usage: Optional[Dict[str, Any]] = None
    quality_metrics: Optional[Dict[str, Any]] = None

class SubmitResponse(BaseModel):
    success: bool
    request_id: str
    status: str
    result_hash: str
    completed_at: datetime
    quality_score: float
    payment_amount: float
    bonus_amount: float
    performance_rating: float

class AssignedRequest(BaseModel):
    id: str
    task_id: str
    symbol: str
    status: str
    claimed_at: datetime
    timeout_at: datetime
    progress_percentage: Optional[int] = 0
    expected_payment: float
    time_remaining: int

class AssignedRequestsResponse(BaseModel):
    assigned_requests: List[AssignedRequest]
    total_assigned: int
    total_processing: int
    total_overdue: int

class ReleaseRequest(BaseModel):
    reason: str = Field(..., pattern="^(insufficient_resources|technical_issue|other)$")
    details: Optional[str] = None

class EvaluatorStats(BaseModel):
    performance_summary: Dict[str, Any]
    recent_activity: Dict[str, Any]
    rankings: Optional[Dict[str, Any]] = None

# Helper functions

def calculate_estimated_payment(prediction_job: PredictionJob) -> float:
    """Calculate estimated payment for a prediction request"""
    base_rates = {
        "short_term": 5.00,
        "long_term": 12.00,
        "custom": 8.00
    }
    
    request_payload = prediction_job.request_payload or {}
    prediction_type = request_payload.get("prediction_type", "short_term")
    
    base_rate = base_rates.get(prediction_type, 8.00)
    
    # Apply complexity multipliers
    horizon = request_payload.get("prediction_horizon", 6)
    lookback = request_payload.get("lookback_ticks", 1000)
    
    complexity_multiplier = 1.0
    if horizon > 10:
        complexity_multiplier += 0.2
    if lookback > 2000:
        complexity_multiplier += 0.1
        
    return round(base_rate * complexity_multiplier, 2)

def calculate_effort_estimate(prediction_job: PredictionJob) -> str:
    """Estimate effort level for a prediction request"""
    request_payload = prediction_job.request_payload or {}
    
    horizon = request_payload.get("prediction_horizon", 6)
    lookback = request_payload.get("lookback_ticks", 1000)
    predictor = request_payload.get("predictor_plugin", "default_predictor")
    
    if horizon <= 6 and lookback <= 1000 and "default" in predictor:
        return "low"
    elif horizon <= 12 and lookback <= 2000:
        return "medium"
    else:
        return "high"

def generate_result_hash(result_data: Dict[str, Any]) -> str:
    """Generate SHA-256 hash of result data for integrity"""
    result_json = json.dumps(result_data, sort_keys=True)
    return hashlib.sha256(result_json.encode()).hexdigest()

# API Endpoints

@router.get("/pending", response_model=PendingRequestsResponse)
async def get_pending_requests(
    prediction_type: Optional[str] = Query(None, pattern="^(short_term|long_term|custom)$"),
    symbol: Optional[str] = Query(None),
    min_priority: Optional[int] = Query(None, ge=1, le=10),
    max_priority: Optional[int] = Query(None, ge=1, le=10),
    min_payment: Optional[float] = Query(None, ge=0),
    max_payment: Optional[float] = Query(None, ge=0),
    predictor_plugin: Optional[str] = Query(None),
    sort: Optional[str] = Query("priority", pattern="^(priority|created_at|payment|effort)$"),
    order: Optional[str] = Query("desc", pattern="^(asc|desc)$"),
    limit: Optional[int] = Query(20, ge=1, le=100),
    current_user: User = Depends(require_role(["evaluator", "administrator"])),
    db: Session = Depends(get_db)
):
    """Get list of pending prediction requests available for processing"""
    
    # Build query for pending requests
    query = db.query(PredictionJob).filter(PredictionJob.status == "pending")
    
    # Apply filters
    if prediction_type:
        # Filter by prediction_type in request_payload
        query = query.filter(
            PredictionJob.request_payload.op('->>')('prediction_type') == prediction_type
        )
    
    if symbol:
        query = query.filter(PredictionJob.ticker == symbol)
    
    # Execute query
    pending_jobs = query.limit(limit).all()
    
    # Convert to response format
    pending_requests = []
    for job in pending_jobs:
        request_payload = job.request_payload or {}
        
        estimated_payment = calculate_estimated_payment(job)
        effort_estimate = calculate_effort_estimate(job)
        
        pending_request = PendingRequestSummary(
            id=job.id,
            task_id=job.id,  # Using same ID for now
            symbol=job.ticker,
            prediction_type=request_payload.get("prediction_type", "short_term"),
            datetime_requested=request_payload.get("datetime_requested", job.created_at),
            lookback_ticks=request_payload.get("lookback_ticks", 1000),
            predictor_plugin=request_payload.get("predictor_plugin", "default_predictor"),
            feeder_plugin=request_payload.get("feeder_plugin", "default_feeder"),
            pipeline_plugin=request_payload.get("pipeline_plugin", "default_pipeline"),
            interval=request_payload.get("interval", "1h"),
            prediction_horizon=request_payload.get("prediction_horizon", 6),
            priority=request_payload.get("priority", 5),
            estimated_payment=estimated_payment,
            estimated_effort=effort_estimate,
            data_complexity="standard",
            client_tier="basic",
            created_at=job.created_at,
            expires_at=job.created_at + timedelta(hours=24),  # 24 hour expiry
            requirements={
                "gpu_required": "transformer" in request_payload.get("predictor_plugin", ""),
                "memory_gb": 8 if effort_estimate == "high" else 4,
                "processing_timeout": 300
            }
        )
        pending_requests.append(pending_request)
    
    # Calculate payment range
    payments = [req.estimated_payment for req in pending_requests]
    payment_range = {
        "min": min(payments) if payments else 0.0,
        "max": max(payments) if payments else 0.0,
        "average": sum(payments) / len(payments) if payments else 0.0
    }
    
    return PendingRequestsResponse(
        pending_requests=pending_requests,
        total_pending=len(pending_requests),
        estimated_queue_time="2-5 minutes",
        payment_range=payment_range
    )

@router.post("/claim/{request_id}", response_model=ClaimResponse)
async def claim_request(
    request_id: str,
    claim_data: ClaimRequest,
    current_user: User = Depends(require_role(["evaluator", "administrator"])),
    db: Session = Depends(get_db)
):
    """Claim a pending prediction request for processing"""
    
    # Find the prediction job
    prediction_job = db.query(PredictionJob).filter(
        PredictionJob.id == request_id,
        PredictionJob.status == "pending"
    ).first()
    
    if not prediction_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending request not found or already claimed"
        )
    
    # Check if request has expired
    expiry_time = prediction_job.created_at + timedelta(hours=24)
    if datetime.now(timezone.utc) > expiry_time:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Request has expired"
        )
    
    # Update status to processing and assign evaluator
    prediction_job.status = "processing"
    # Note: We need to add evaluator_id field to PredictionJob model
    
    claimed_at = datetime.now(timezone.utc)
    timeout_at = claimed_at + timedelta(minutes=30)  # 30 minute timeout
    
    # Update job with claim information
    if not prediction_job.request_payload:
        prediction_job.request_payload = {}
    
    prediction_job.request_payload.update({
        "claimed_by": current_user.id,
        "claimed_at": claimed_at.isoformat(),
        "timeout_at": timeout_at.isoformat(),
        "processing_node_info": claim_data.processing_node_info
    })
    
    db.commit()
    
    # Calculate payment and prepare processing details
    estimated_payment = calculate_estimated_payment(prediction_job)
    request_payload = prediction_job.request_payload or {}
    
    processing_details = {
        "symbol": prediction_job.ticker,
        "datetime_requested": request_payload.get("datetime_requested"),
        "lookback_ticks": request_payload.get("lookback_ticks", 1000),
        "interval": request_payload.get("interval", "1h"),
        "prediction_horizon": request_payload.get("prediction_horizon", 6),
        "data_source_config": {
            "provider": "alpha_vantage",
            "api_key_required": False,
            "rate_limit": "5 calls/minute"
        },
        "model_config": {
            "model_path": f"/models/{request_payload.get('predictor_plugin', 'default')}_model.h5",
            "normalization_params": f"/config/{prediction_job.ticker.lower()}_norm.json",
            "feature_columns": 45,
            "sequence_length": 144
        },
        "output_requirements": {
            "format": "json",
            "include_uncertainties": True,
            "include_confidence_intervals": True,
            "include_plots": False
        }
    }
    
    return ClaimResponse(
        success=True,
        request_id=request_id,
        task_id=prediction_job.id,
        claimed_at=claimed_at,
        timeout_at=timeout_at,
        expected_payment=estimated_payment,
        processing_details=processing_details
    )

@router.post("/submit/{request_id}", response_model=SubmitResponse)
async def submit_results(
    request_id: str,
    results: SubmitRequest,
    current_user: User = Depends(require_role(["evaluator", "administrator"])),
    db: Session = Depends(get_db)
):
    """Submit results for a claimed prediction request"""
    
    # Find the prediction job
    prediction_job = db.query(PredictionJob).filter(
        PredictionJob.id == request_id,
        PredictionJob.status == "processing"
    ).first()
    
    if not prediction_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processing request not found"
        )
    
    # Verify the current user claimed this request
    request_payload = prediction_job.request_payload or {}
    if request_payload.get("claimed_by") != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to submit results for this request"
        )
    
    # Check if submission is within timeout
    timeout_str = request_payload.get("timeout_at")
    if timeout_str:
        timeout_at = datetime.fromisoformat(timeout_str.replace('Z', '+00:00'))
        if datetime.now(timezone.utc) > timeout_at:
            raise HTTPException(
                status_code=status.HTTP_408_REQUEST_TIMEOUT,
                detail="Submission timeout exceeded"
            )
    
    # Prepare result data
    completed_at = datetime.now(timezone.utc)
    result_data = {
        "predictions": results.predictions,
        "uncertainties": results.uncertainties,
        "confidence_intervals": results.confidence_intervals,
        "model_metadata": results.model_metadata,
        "processing_log": results.processing_log,
        "resource_usage": results.resource_usage,
        "quality_metrics": results.quality_metrics,
        "completed_at": completed_at.isoformat(),
        "completed_by": current_user.id
    }
    
    # Generate result hash for integrity
    result_hash = generate_result_hash(result_data)
    
    # Update prediction job
    prediction_job.status = "completed"
    prediction_job.result = result_data
    prediction_job.completed_at = completed_at
    prediction_job.processing_time_ms = (completed_at - prediction_job.created_at).total_seconds() * 1000
    
    # Add result hash to payload
    prediction_job.request_payload["result_hash"] = result_hash
    
    db.commit()
    
    # Calculate payment and performance metrics
    estimated_payment = calculate_estimated_payment(prediction_job)
    
    # Simple quality score calculation (would be more complex in production)
    quality_score = min(
        results.quality_metrics.get("model_confidence", 0.8) if results.quality_metrics else 0.8,
        1.0
    )
    
    # Calculate bonus based on quality and speed
    processing_time_minutes = prediction_job.processing_time_ms / (1000 * 60)
    speed_bonus = max(0, (30 - processing_time_minutes) / 30 * 0.1)  # Up to 10% bonus for speed
    quality_bonus = max(0, (quality_score - 0.8) / 0.2 * 0.1)  # Up to 10% bonus for quality
    
    bonus_amount = estimated_payment * (speed_bonus + quality_bonus)
    
    return SubmitResponse(
        success=True,
        request_id=request_id,
        status="completed",
        result_hash=result_hash,
        completed_at=completed_at,
        quality_score=quality_score,
        payment_amount=estimated_payment,
        bonus_amount=bonus_amount,
        performance_rating=min(5.0, 4.0 + quality_score)
    )

@router.get("/assigned", response_model=AssignedRequestsResponse)
async def get_assigned_requests(
    status: Optional[str] = Query(None, pattern="^(processing|overdue)$"),
    include_expired: bool = Query(False),
    current_user: User = Depends(require_role(["evaluator", "administrator"])),
    db: Session = Depends(get_db)
):
    """Get list of requests currently assigned to evaluator"""
    
    # Build query based on user role
    if current_user.role.name == "administrator":
        # Admins can see all assigned requests
        query = db.query(PredictionJob).filter(PredictionJob.status == "processing")
    else:
        # Evaluators can only see their own assigned requests
        query = db.query(PredictionJob).filter(
            PredictionJob.status == "processing",
            PredictionJob.request_payload.op('->>')('claimed_by') == str(current_user.id)
        )
    
    assigned_jobs = query.all()
    
    # Convert to response format
    assigned_requests = []
    current_time = datetime.now(timezone.utc)
    
    for job in assigned_jobs:
        request_payload = job.request_payload or {}
        
        claimed_at_str = request_payload.get("claimed_at")
        timeout_at_str = request_payload.get("timeout_at")
        
        claimed_at = datetime.fromisoformat(claimed_at_str.replace('Z', '+00:00')) if claimed_at_str else job.created_at
        timeout_at = datetime.fromisoformat(timeout_at_str.replace('Z', '+00:00')) if timeout_at_str else claimed_at + timedelta(minutes=30)
        
        time_remaining = max(0, int((timeout_at - current_time).total_seconds()))
        
        assigned_request = AssignedRequest(
            id=job.id,
            task_id=job.id,
            symbol=job.ticker,
            status=job.status,
            claimed_at=claimed_at,
            timeout_at=timeout_at,
            progress_percentage=request_payload.get("progress_percentage", 0),
            expected_payment=calculate_estimated_payment(job),
            time_remaining=time_remaining
        )
        assigned_requests.append(assigned_request)
    
    # Calculate summary statistics
    total_assigned = len(assigned_requests)
    total_processing = len([req for req in assigned_requests if req.status == "processing"])
    total_overdue = len([req for req in assigned_requests if req.time_remaining <= 0])
    
    return AssignedRequestsResponse(
        assigned_requests=assigned_requests,
        total_assigned=total_assigned,
        total_processing=total_processing,
        total_overdue=total_overdue
    )

@router.post("/release/{request_id}")
async def release_request(
    request_id: str,
    release_data: ReleaseRequest,
    current_user: User = Depends(require_role(["evaluator", "administrator"])),
    db: Session = Depends(get_db)
):
    """Release a claimed request back to the queue"""
    
    # Find the prediction job
    prediction_job = db.query(PredictionJob).filter(
        PredictionJob.id == request_id,
        PredictionJob.status == "processing"
    ).first()
    
    if not prediction_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processing request not found"
        )
    
    # Verify the current user claimed this request (unless admin)
    request_payload = prediction_job.request_payload or {}
    if (current_user.role.name != "administrator" and 
        request_payload.get("claimed_by") != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to release this request"
        )
    
    # Release the request back to pending
    prediction_job.status = "pending"
    
    # Update request payload to remove claim information
    if prediction_job.request_payload:
        prediction_job.request_payload.pop("claimed_by", None)
        prediction_job.request_payload.pop("claimed_at", None)
        prediction_job.request_payload.pop("timeout_at", None)
        
        # Add release information
        prediction_job.request_payload["release_history"] = prediction_job.request_payload.get("release_history", [])
        prediction_job.request_payload["release_history"].append({
            "released_by": current_user.id,
            "released_at": datetime.now(timezone.utc).isoformat(),
            "reason": release_data.reason,
            "details": release_data.details
        })
    
    db.commit()
    
    return {"success": True, "message": "Request released back to queue"}

@router.get("/stats", response_model=EvaluatorStats)
async def get_evaluator_stats(
    period: str = Query("7d", pattern="^(7d|30d|90d)$"),
    include_rankings: bool = Query(True),
    current_user: User = Depends(require_role(["evaluator", "administrator"])),
    db: Session = Depends(get_db)
):
    """Get evaluator performance statistics"""
    
    # Parse period
    period_days = {"7d": 7, "30d": 30, "90d": 90}[period]
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=period_days)
    
    # Get evaluator's completed jobs
    user_id_filter = current_user.id
    if current_user.role.name == "administrator":
        # Admins can potentially see all stats, but for now show their own
        pass
    
    completed_jobs = db.query(PredictionJob).filter(
        PredictionJob.status == "completed",
        PredictionJob.completed_at >= cutoff_date,
        PredictionJob.request_payload.op('->>')('completed_by') == str(user_id_filter)
    ).all()
    
    # Calculate performance metrics
    total_completed = len(completed_jobs)
    
    if total_completed > 0:
        processing_times = [job.processing_time_ms or 0 for job in completed_jobs]
        average_processing_time = sum(processing_times) / len(processing_times) / (1000 * 60)  # Convert to minutes
        
        # Calculate estimated earnings
        total_earnings = sum(calculate_estimated_payment(job) for job in completed_jobs)
        
        # Simple quality score (would be calculated from actual result quality in production)
        average_quality_score = 4.5  # Placeholder
        
        success_rate = 0.98  # Placeholder - would calculate from failed vs completed jobs
        current_reputation = 4.8  # Placeholder - would be stored in user profile
    else:
        average_processing_time = 0
        total_earnings = 0
        average_quality_score = 0
        success_rate = 0
        current_reputation = 0
    
    performance_summary = {
        "total_completed": total_completed,
        "success_rate": success_rate,
        "average_processing_time": round(average_processing_time, 1),
        "average_quality_score": average_quality_score,
        "total_earnings": round(total_earnings, 2),
        "current_reputation": current_reputation
    }
    
    # Recent activity (last 7 days)
    recent_cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    recent_jobs = [job for job in completed_jobs if job.completed_at >= recent_cutoff]
    
    recent_activity = {
        "last_7_days": {
            "requests_completed": len(recent_jobs),
            "average_daily_earnings": round(sum(calculate_estimated_payment(job) for job in recent_jobs) / 7, 2),
            "quality_trend": "improving"  # Placeholder
        }
    }
    
    # Rankings (placeholder - would require querying all evaluators)
    rankings = None
    if include_rankings:
        rankings = {
            "quality_rank": 15,
            "speed_rank": 8,
            "reliability_rank": 12,
            "total_evaluators": 247
        }
    
    return EvaluatorStats(
        performance_summary=performance_summary,
        recent_activity=recent_activity,
        rankings=rankings
    )
