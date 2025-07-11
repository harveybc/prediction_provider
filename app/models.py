#!/usr/bin/env python3
"""
Database models for the Prediction Provider system using SQLAlchemy.
"""

from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date
from app.database import Base

# Use the Base from database module

class Prediction(Base):
    __tablename__ = 'predictions'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True)
    task_id = Column(String, unique=True, nullable=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    status = Column(String, nullable=False, default='pending')
    symbol = Column(String, nullable=True)
    interval = Column(String, nullable=True)
    predictor_plugin = Column(String, nullable=True)
    feeder_plugin = Column(String, nullable=True)
    pipeline_plugin = Column(String, nullable=True)
    prediction_type = Column(String, nullable=True)
    ticker = Column(String, nullable=True)
    result = Column(JSON, nullable=True)
    prediction = Column(JSON, nullable=True)
    uncertainty = Column(JSON, nullable=True)
    
    # Relationship to User model
    user = relationship("User", back_populates="prediction_models")

    def to_dict(self):
        return {
            'id': self.id,
            'task_id': self.task_id,
            'user_id': self.user_id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'status': self.status,
            'symbol': self.symbol,
            'interval': self.interval,
            'predictor_plugin': self.predictor_plugin,
            'feeder_plugin': self.feeder_plugin,
            'pipeline_plugin': self.pipeline_plugin,
            'prediction_type': self.prediction_type,
            'ticker': self.ticker,
            'result': self.result,
            'prediction': self.prediction,
            'uncertainty': self.uncertainty
        }

def create_database_engine(database_url):
    """Create and return database engine."""
    engine = create_engine(database_url, echo=False)
    return engine

def create_tables(engine):
    """Create all tables in the database."""
    Base.metadata.create_all(engine)

def get_session(engine):
    """Create and return a new session."""
    Session = sessionmaker(bind=engine)
    return Session()

class PredictionRequest(BaseModel):
    ticker: str
    model_name: str = "default_model"
    start_date: Optional[date] = None
    end_date: Optional[date] = None
