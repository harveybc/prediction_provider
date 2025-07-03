#!/usr/bin/env python3
"""
Database models for the Prediction Provider system using SQLAlchemy.
"""

from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date

Base = declarative_base()

class Prediction(Base):
    __tablename__ = 'predictions'

    id = Column(Integer, primary_key=True)
    task_id = Column(String, unique=True, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = Column(String, nullable=False, default='pending')
    prediction_type = Column(String, nullable=True)
    prediction = Column(JSON, nullable=True)
    uncertainty = Column(JSON, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'task_id': self.task_id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'status': self.status,
            'prediction_type': self.prediction_type,
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
