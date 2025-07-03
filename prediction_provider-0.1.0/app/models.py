#!/usr/bin/env python3
"""
Database models for the Prediction Provider system using SQLAlchemy.
"""

from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Prediction(Base):
    __tablename__ = 'predictions'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = Column(String, nullable=False, default='pending')
    prediction_data = Column(JSON, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'status': self.status,
            'prediction_data': self.prediction_data
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
