from sqlalchemy import (
    Column, 
    Integer, 
    String, 
    DateTime, 
    JSON, 
    ForeignKey, 
    Boolean, 
    Float,
    PrimaryKeyConstraint
)
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime, timezone

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_api_key = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    role_id = Column(Integer, ForeignKey('roles.id'), nullable=False)
    
    role = relationship("Role")
    predictions = relationship("PredictionJob", back_populates="requester")
    api_logs = relationship("ApiLog", back_populates="user")

class Role(Base):
    __tablename__ = 'roles'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    permissions = Column(JSON, nullable=False)  # e.g., {"can_predict": true, "can_view_logs": false}

class PredictionJob(Base):
    __tablename__ = 'prediction_jobs'
    id = Column(String, primary_key=True, index=True) # Using request UUID as string
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    status = Column(String, nullable=False, default='pending', index=True)
    request_payload = Column(JSON, nullable=False)
    result = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    requester = relationship("User", back_populates="predictions")

class ApiLog(Base):
    __tablename__ = 'api_logs'
    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True) # Nullable for failed authentication
    ip_address = Column(String, nullable=False)
    endpoint = Column(String, nullable=False, index=True)
    method = Column(String, nullable=False)
    request_timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    response_status_code = Column(Integer, nullable=False)
    response_time_ms = Column(Float, nullable=False)
    
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
    )
