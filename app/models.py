#!/usr/bin/env python3
"""
Database models for the Prediction Provider system using SQLAlchemy.
"""

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import json

Base = declarative_base()

class PendingPredictionRequest(Base):
    """
    Table to store prediction requests and their results.
    """
    __tablename__ = 'pending_prediction_requests'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    model_path = Column(String(255), nullable=False)
    target_date = Column(DateTime, nullable=False)
    batch_size = Column(Integer, default=32)
    num_batches = Column(Integer, default=1)
    input_features = Column(Text, nullable=True)  # JSON string of required features
    status = Column(String(50), default='pending')  # pending, processing, completed, error
    results = Column(Text, nullable=True)  # JSON string of predictions
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """Convert model to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'model_path': self.model_path,
            'target_date': self.target_date.isoformat() if self.target_date else None,
            'batch_size': self.batch_size,
            'num_batches': self.num_batches,
            'input_features': json.loads(self.input_features) if self.input_features else None,
            'status': self.status,
            'results': json.loads(self.results) if self.results else None,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

def create_database_engine(database_url):
    """Create and return database engine."""
    engine = create_engine(database_url, echo=False)
    return engine

def create_tables(engine):
    """Create all tables in the database."""
    Base.metadata.create_all(engine)

def get_session_maker(engine):
    """Create and return session maker."""
    return sessionmaker(bind=engine)
