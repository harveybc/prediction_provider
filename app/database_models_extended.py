"""
Extended database models for the comprehensive AAA prediction marketplace.

This module extends the existing database models with additional tables
for audit logging, financial tracking, and system monitoring as specified
in the design documentation.
"""

from sqlalchemy import (
    Column, 
    Integer, 
    String, 
    DateTime, 
    JSON, 
    ForeignKey, 
    Boolean, 
    Float,
    Text,
    Enum,
    DECIMAL,
    BigInteger
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base
import enum

# Enums for type safety
class UserRole(enum.Enum):
    GUEST = "guest"
    CLIENT = "client"
    EVALUATOR = "evaluator"
    ADMINISTRATOR = "administrator"

class PredictionStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"

class TransactionType(enum.Enum):
    CHARGE = "charge"
    PAYMENT = "payment"
    REFUND = "refund"
    CREDIT = "credit"
    PAYOUT = "payout"

class CreditType(enum.Enum):
    PURCHASED = "purchased"
    EARNED = "earned"
    BONUS = "bonus"
    REFUND = "refund"

class EventType(enum.Enum):
    LOGIN_FAILURE = "login_failure"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    RATE_LIMIT = "rate_limit"
    UNAUTHORIZED_ACCESS = "unauthorized_access"

class Severity(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

# Extended user sessions table
class UserSession(Base):
    __tablename__ = 'user_sessions'
    __table_args__ = {'extend_existing': True}
    
    id = Column(String, primary_key=True, index=True)  # UUID
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    session_token = Column(String, nullable=False, index=True)
    ip_address = Column(String, nullable=False)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    last_activity = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    user = relationship("User", back_populates="sessions")

# Extended predictions table with evaluator support
class PredictionExtended(Base):
    __tablename__ = 'predictions_extended'
    __table_args__ = {'extend_existing': True}
    
    id = Column(String, primary_key=True, index=True)  # UUID
    task_id = Column(String, unique=True, index=True, nullable=False)  # External reference UUID
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)  # Client who requested
    evaluator_id = Column(Integer, ForeignKey('users.id'), nullable=True)  # Evaluator processing
    status = Column(Enum(PredictionStatus), default=PredictionStatus.PENDING, nullable=False, index=True)
    priority = Column(Integer, default=5, nullable=False)
    symbol = Column(String(20), nullable=False)
    prediction_type = Column(String(50), default='short_term', nullable=False)
    datetime_requested = Column(DateTime, nullable=False)
    lookback_ticks = Column(Integer, default=1000, nullable=False)
    predictor_plugin = Column(String(100), default='default_predictor', nullable=False)
    feeder_plugin = Column(String(100), default='default_feeder', nullable=False)
    pipeline_plugin = Column(String(100), default='default_pipeline', nullable=False)
    interval = Column(String(10), default='1h', nullable=False)
    prediction_horizon = Column(Integer, default=6, nullable=False)
    request_params = Column(JSON, nullable=True)
    result = Column(JSON, nullable=True)
    result_hash = Column(String(64), nullable=True)  # SHA-256 hash
    result_confidence = Column(Float, nullable=True)
    processing_metadata = Column(JSON, nullable=True)
    cost_estimate = Column(DECIMAL(10, 2), nullable=True)
    actual_cost = Column(DECIMAL(10, 2), nullable=True)
    claimed_at = Column(DateTime, nullable=True)
    started_processing_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime, nullable=True)
    timeout_at = Column(DateTime, nullable=True)
    
    client = relationship("User", foreign_keys=[user_id], back_populates="client_predictions")
    evaluator = relationship("User", foreign_keys=[evaluator_id], back_populates="evaluator_predictions")
    files = relationship("PredictionFile", back_populates="prediction")
    transactions = relationship("Transaction", back_populates="prediction")

# Prediction files table for storing result files
class PredictionFile(Base):
    __tablename__ = 'prediction_files'
    __table_args__ = {'extend_existing': True}
    
    id = Column(String, primary_key=True, index=True)  # UUID
    prediction_id = Column(String, ForeignKey('predictions_extended.id'), nullable=False)
    file_type = Column(String(50), nullable=False)  # input_data, result_csv, metadata, plot, log
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    file_hash = Column(String(64), nullable=False)  # SHA-256
    mime_type = Column(String(100), nullable=False)
    encryption_key = Column(String(255), nullable=True)  # Encrypted
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime, nullable=True)
    
    prediction = relationship("PredictionExtended", back_populates="files")

# Financial transactions table
class Transaction(Base):
    __tablename__ = 'transactions'
    __table_args__ = {'extend_existing': True}
    
    id = Column(String, primary_key=True, index=True)  # UUID
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    prediction_id = Column(String, ForeignKey('predictions_extended.id'), nullable=True)
    transaction_type = Column(Enum(TransactionType), nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False)
    currency = Column(String(3), default='USD', nullable=False)
    description = Column(Text, nullable=True)
    payment_method = Column(String(100), nullable=True)
    payment_reference = Column(String(255), nullable=True)
    status = Column(String(20), default='pending', nullable=False)
    processing_fee = Column(DECIMAL(10, 2), nullable=True)
    tax_amount = Column(DECIMAL(10, 2), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="transactions")
    prediction = relationship("PredictionExtended", back_populates="transactions")

# Credits management table
class Credit(Base):
    __tablename__ = 'credits'
    __table_args__ = {'extend_existing': True}
    
    id = Column(String, primary_key=True, index=True)  # UUID
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    credit_type = Column(Enum(CreditType), nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False)
    currency = Column(String(3), default='USD', nullable=False)
    source_transaction_id = Column(String, ForeignKey('transactions.id'), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    used_amount = Column(DECIMAL(10, 2), default=0.00, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    user = relationship("User", back_populates="credits")
    source_transaction = relationship("Transaction")

# Invoices table
class Invoice(Base):
    __tablename__ = 'invoices'
    __table_args__ = {'extend_existing': True}
    
    id = Column(String, primary_key=True, index=True)  # UUID
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    invoice_number = Column(String(50), unique=True, nullable=False)
    billing_period_start = Column(DateTime, nullable=False)
    billing_period_end = Column(DateTime, nullable=False)
    subtotal = Column(DECIMAL(10, 2), nullable=False)
    tax_amount = Column(DECIMAL(10, 2), nullable=False)
    total_amount = Column(DECIMAL(10, 2), nullable=False)
    currency = Column(String(3), default='USD', nullable=False)
    status = Column(String(20), default='draft', nullable=False)
    payment_due_date = Column(DateTime, nullable=False)
    pdf_path = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    paid_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="invoices")

# Enhanced audit log table
class AuditLogExtended(Base):
    __tablename__ = 'audit_log_extended'
    __table_args__ = {'extend_existing': True}
    
    id = Column(String, primary_key=True, index=True)  # UUID
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    session_id = Column(String, ForeignKey('user_sessions.id'), nullable=True)
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(255), nullable=True)
    endpoint = Column(String(255), nullable=False, index=True)
    method = Column(String(10), nullable=False)
    parameters = Column(JSON, nullable=True)
    request_body_hash = Column(String(64), nullable=True)  # SHA-256
    response_status = Column(Integer, nullable=False)
    response_body_hash = Column(String(64), nullable=True)  # SHA-256
    ip_address = Column(String(45), nullable=False)  # IPv6 support
    user_agent = Column(Text, nullable=True)
    processing_time = Column(Float, nullable=False)  # milliseconds
    success = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)
    risk_score = Column(Float, nullable=True)
    compliance_flags = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    correlation_id = Column(String(255), nullable=True, index=True)
    
    user = relationship("User")
    session = relationship("UserSession")

# Security events table
class SecurityEvent(Base):
    __tablename__ = 'security_events'
    __table_args__ = {'extend_existing': True}
    
    id = Column(String, primary_key=True, index=True)  # UUID
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    event_type = Column(Enum(EventType), nullable=False)
    severity = Column(Enum(Severity), nullable=False)
    description = Column(Text, nullable=False)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=False)
    user_agent = Column(Text, nullable=True)
    action_taken = Column(String(255), nullable=True)
    investigated = Column(Boolean, default=False, nullable=False)
    resolved = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    
    user = relationship("User")

# Compliance reports table
class ComplianceReport(Base):
    __tablename__ = 'compliance_reports'
    __table_args__ = {'extend_existing': True}
    
    id = Column(String, primary_key=True, index=True)  # UUID
    report_type = Column(String(50), nullable=False)  # sox, gdpr, pci_dss, custom
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    generated_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    report_data = Column(JSON, nullable=False)
    file_path = Column(String(500), nullable=True)
    status = Column(String(20), default='generating', nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    generator = relationship("User")

# System metrics table
class SystemMetric(Base):
    __tablename__ = 'system_metrics'
    __table_args__ = {'extend_existing': True}
    
    id = Column(String, primary_key=True, index=True)  # UUID
    metric_name = Column(String(100), nullable=False, index=True)
    metric_value = Column(Float, nullable=False)
    metric_unit = Column(String(20), nullable=True)
    tags = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

# Performance metrics table
class PerformanceMetric(Base):
    __tablename__ = 'performance_metrics'
    __table_args__ = {'extend_existing': True}
    
    id = Column(String, primary_key=True, index=True)  # UUID
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)  # For evaluators
    prediction_id = Column(String, ForeignKey('predictions_extended.id'), nullable=True)
    processing_time = Column(Float, nullable=False)  # Total processing duration
    data_fetch_time = Column(Float, nullable=True)  # Data retrieval duration
    model_inference_time = Column(Float, nullable=True)  # Model execution duration
    result_quality_score = Column(Float, nullable=True)  # Quality assessment score
    resource_usage = Column(JSON, nullable=True)  # CPU/memory usage
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    
    user = relationship("User")
    prediction = relationship("PredictionExtended")

# Update the User model to include new relationships
def extend_user_model():
    """Add new relationships to the existing User model"""
    User.sessions = relationship("UserSession", back_populates="user")
    User.client_predictions = relationship("PredictionExtended", foreign_keys="PredictionExtended.user_id", back_populates="client")
    User.evaluator_predictions = relationship("PredictionExtended", foreign_keys="PredictionExtended.evaluator_id", back_populates="evaluator")
    User.transactions = relationship("Transaction", back_populates="user")
    User.credits = relationship("Credit", back_populates="user")
    User.invoices = relationship("Invoice", back_populates="user")

# Add new fields to existing User model
class UserExtended(Base):
    __tablename__ = 'users_extended'
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.CLIENT, nullable=False)
    api_key = Column(String(64), unique=True, index=True, nullable=True)
    api_key_expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=False, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    subscription_tier = Column(String(20), default='basic', nullable=False)
    billing_address = Column(JSON, nullable=True)
    tax_id = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    last_login = Column(DateTime, nullable=True)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    account_locked_until = Column(DateTime, nullable=True)
    two_factor_enabled = Column(Boolean, default=False, nullable=False)
    two_factor_secret = Column(String(255), nullable=True)  # Encrypted
