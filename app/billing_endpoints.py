"""
Billing and Provider endpoints for the prediction marketplace.
Implements provider pricing, billing records, and spend/earnings views.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import logging

from app.database import get_db
from app.database_models import User, Role, BillingRecord, ProviderPricing, PredictionJob
from app.auth import get_current_user, require_role, require_admin

logger = logging.getLogger(__name__)
router = APIRouter(tags=["billing"])

# --- Pydantic Models ---

class PricingCreate(BaseModel):
    model_name: str = Field(..., min_length=1, max_length=100)
    price_per_request: float = Field(..., ge=0)
    currency: str = Field("USD", pattern=r"^[A-Z]{3}$")

class PricingResponse(BaseModel):
    id: int
    provider_id: int
    model_name: str
    price_per_request: float
    currency: str
    is_active: bool

class BillingResponse(BaseModel):
    id: int
    client_id: int
    provider_id: int
    prediction_id: Optional[str]
    cost: float
    currency: str
    timestamp: datetime

class EarningsSummary(BaseModel):
    total_earnings: float
    currency: str
    total_requests: int
    period_days: int

class SpendSummary(BaseModel):
    total_spent: float
    currency: str
    total_requests: int
    period_days: int

# --- Provider Endpoints ---

@router.post("/provider/pricing", response_model=PricingResponse, status_code=201)
async def set_pricing(
    data: PricingCreate,
    current_user: User = Depends(require_role(["provider", "administrator", "admin"])),
    db: Session = Depends(get_db)
):
    """Set pricing for a model (Provider/Admin only)"""
    # Deactivate existing pricing for same model
    existing = db.query(ProviderPricing).filter(
        ProviderPricing.provider_id == current_user.id,
        ProviderPricing.model_name == data.model_name,
        ProviderPricing.is_active == True
    ).all()
    for p in existing:
        p.is_active = False
    
    pricing = ProviderPricing(
        provider_id=current_user.id,
        model_name=data.model_name,
        price_per_request=data.price_per_request,
        currency=data.currency,
        is_active=True
    )
    db.add(pricing)
    db.commit()
    
    # Re-query to get the auto-generated id
    created = db.query(ProviderPricing).filter(
        ProviderPricing.provider_id == current_user.id,
        ProviderPricing.model_name == data.model_name,
        ProviderPricing.is_active == True
    ).first()
    
    return PricingResponse(
        id=created.id if created else 0, provider_id=current_user.id,
        model_name=data.model_name, price_per_request=data.price_per_request,
        currency=data.currency, is_active=True
    )

@router.get("/provider/pricing", response_model=List[PricingResponse])
async def get_my_pricing(
    current_user: User = Depends(require_role(["provider", "administrator", "admin"])),
    db: Session = Depends(get_db)
):
    """Get my active pricing (Provider/Admin)"""
    pricing = db.query(ProviderPricing).filter(
        ProviderPricing.provider_id == current_user.id,
        ProviderPricing.is_active == True
    ).all()
    return [PricingResponse(
        id=p.id, provider_id=p.provider_id, model_name=p.model_name,
        price_per_request=p.price_per_request, currency=p.currency, is_active=p.is_active
    ) for p in pricing]

@router.get("/provider/earnings", response_model=EarningsSummary)
async def get_earnings(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(require_role(["provider", "administrator", "admin"])),
    db: Session = Depends(get_db)
):
    """Get provider earnings summary"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    records = db.query(BillingRecord).filter(
        BillingRecord.provider_id == current_user.id,
        BillingRecord.timestamp >= cutoff
    ).all()
    
    return EarningsSummary(
        total_earnings=sum(r.cost for r in records),
        currency="USD",
        total_requests=len(records),
        period_days=days
    )

# --- Client Endpoints ---

@router.get("/client/spend", response_model=SpendSummary)
async def get_spend(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(require_role(["client", "administrator", "admin"])),
    db: Session = Depends(get_db)
):
    """Get client spend summary"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    records = db.query(BillingRecord).filter(
        BillingRecord.client_id == current_user.id,
        BillingRecord.timestamp >= cutoff
    ).all()
    
    return SpendSummary(
        total_spent=sum(r.cost for r in records),
        currency="USD",
        total_requests=len(records),
        period_days=days
    )

@router.get("/client/billing", response_model=List[BillingResponse])
async def get_my_billing(
    limit: int = Query(50, ge=1, le=500),
    current_user: User = Depends(require_role(["client", "administrator", "admin"])),
    db: Session = Depends(get_db)
):
    """Get client billing history"""
    records = db.query(BillingRecord).filter(
        BillingRecord.client_id == current_user.id
    ).order_by(BillingRecord.timestamp.desc()).limit(limit).all()
    
    return [BillingResponse(
        id=r.id, client_id=r.client_id, provider_id=r.provider_id,
        prediction_id=r.prediction_id, cost=r.cost, currency=r.currency,
        timestamp=r.timestamp
    ) for r in records]

# --- Admin Endpoints ---

@router.get("/admin/billing", response_model=List[BillingResponse])
async def get_all_billing(
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get all billing records (Admin only)"""
    records = db.query(BillingRecord).order_by(BillingRecord.timestamp.desc()).limit(limit).all()
    return [BillingResponse(
        id=r.id, client_id=r.client_id, provider_id=r.provider_id,
        prediction_id=r.prediction_id, cost=r.cost, currency=r.currency,
        timestamp=r.timestamp
    ) for r in records]

@router.get("/admin/billing/summary")
async def billing_summary(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get billing summary (Admin only)"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    records = db.query(BillingRecord).filter(BillingRecord.timestamp >= cutoff).all()
    
    total_revenue = sum(r.cost for r in records)
    unique_clients = len(set(r.client_id for r in records))
    unique_providers = len(set(r.provider_id for r in records))
    
    return {
        "total_revenue": total_revenue,
        "total_transactions": len(records),
        "unique_clients": unique_clients,
        "unique_providers": unique_providers,
        "period_days": days,
        "currency": "USD"
    }

@router.get("/admin/pricing", response_model=List[PricingResponse])
async def get_all_pricing(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get all pricing (Admin only)"""
    pricing = db.query(ProviderPricing).filter(ProviderPricing.is_active == True).all()
    return [PricingResponse(
        id=p.id, provider_id=p.provider_id, model_name=p.model_name,
        price_per_request=p.price_per_request, currency=p.currency, is_active=p.is_active
    ) for p in pricing]
