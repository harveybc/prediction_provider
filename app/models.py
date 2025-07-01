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
    target_datetime = Column(DateTime, nullable=False)
    batch_size = Column(Integer, default=32)
    features = Column(Text, nullable=True)  # JSON string of required features
    status = Column(String(50), default='pending')  # pending, processing, completed, failed
    results = Column(Text, nullable=True)  # JSON string of predictions
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """Convert model to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'model_path': self.model_path,
            'target_datetime': self.target_datetime.isoformat() if self.target_datetime else None,
            'batch_size': self.batch_size,
            'features': json.loads(self.features) if self.features else None,
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

def get_db_session():
    """Get a database session for the current thread."""
    # This assumes a global engine is available
    # In practice, you might want to pass the database URL or engine
    engine = create_database_engine("sqlite:///prediction_provider.db")
    session_maker = get_session_maker(engine)
    return session_maker()

def get_db_path():
    """Get the path to the database file."""
    return "prediction_provider.db"

def create_database():
    """Create the database and all tables."""
    db_path = get_db_path()
    database_url = f"sqlite:///{db_path}"
    engine = create_database_engine(database_url)
    create_tables(engine)
    return engine
