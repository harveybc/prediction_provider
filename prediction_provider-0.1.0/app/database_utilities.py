from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database_models import Base

def get_db_session(db_uri: str):
    """Generator function to get a database session."""
    engine = create_engine(db_uri)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_all_tables(db_uri: str):
    """Creates all tables in the database."""
    engine = create_engine(db_uri)
    Base.metadata.create_all(bind=engine)
