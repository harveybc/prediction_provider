from sqlalchemy import (
    Column, 
    Integer, 
    String, 
    DateTime, 
    JSON, 
    ForeignKey, 
    Boolean, 
    Float,
    PrimaryKeyConstraint,
    Text
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base

class User(Base):
    __tablename__ = 'users'
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    hashed_api_key = Column(String, nullable=True)
    is_active = Column(Boolean, default=False, nullable=False)  # Requires activation
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_login = Column(DateTime, nullable=True)
    role_id = Column(Integer, ForeignKey('roles.id'), nullable=False)
    
    role = relationship("Role")
    predictions = relationship("PredictionJob", back_populates="requester")
    prediction_models = relationship("Prediction", back_populates="user")
    api_logs = relationship("ApiLog", back_populates="user")

class Role(Base):
    __tablename__ = 'roles'
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    permissions = Column(JSON, nullable=False)  # e.g., {"can_predict": true, "can_view_logs": false}
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

class PredictionJob(Base):
    __tablename__ = 'prediction_jobs'
    __table_args__ = {'extend_existing': True}
    id = Column(String, primary_key=True, index=True) # Using request UUID as string
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    ticker = Column(String, nullable=False)
    model_name = Column(String, nullable=False)
    status = Column(String, nullable=False, default='pending', index=True)
    request_payload = Column(JSON, nullable=False)
    result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    processing_time_ms = Column(Float, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime, nullable=True)
    
    requester = relationship("User", back_populates="predictions")

class ApiLog(Base):
    __tablename__ = 'api_logs'
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True) # Nullable for failed authentication
    ip_address = Column(String, nullable=False)
    user_agent = Column(String, nullable=True)
    endpoint = Column(String, nullable=False, index=True)
    method = Column(String, nullable=False)
    request_payload = Column(JSON, nullable=True)
    request_timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    response_status_code = Column(Integer, nullable=False)
    response_time_ms = Column(Float, nullable=False)
    response_size_bytes = Column(Integer, nullable=True)
    
    user = relationship("User", back_populates="api_logs")

class TimeSeriesData(Base):
    __tablename__ = 'time_series_data'
    ticker = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Integer, nullable=False)
    
    __table_args__ = (
        PrimaryKeyConstraint('ticker', 'timestamp'),
        {'extend_existing': True}
    )

class SystemConfiguration(Base):
    __tablename__ = 'system_configuration'
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True, nullable=False)
    value = Column(JSON, nullable=False)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    updated_by = Column(Integer, ForeignKey('users.id'), nullable=True)

class UserSession(Base):
    __tablename__ = 'user_sessions'
    __table_args__ = {'extend_existing': True}
    id = Column(String, primary_key=True, index=True)  # Session token
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    ip_address = Column(String, nullable=False)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_activity = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    user = relationship("User")
