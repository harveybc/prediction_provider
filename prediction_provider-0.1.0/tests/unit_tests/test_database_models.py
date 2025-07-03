import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Prediction, Base

# Use an in-memory SQLite database for testing the models
engine = create_engine("sqlite:///:memory:")
Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    """Provides a clean database session for each test."""
    Base.metadata.create_all(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)

def test_prediction_model_creation(db_session):
    """
    Tests the creation of a Prediction record in the database.
    """
    task_id = "test-task-123"
    new_prediction = Prediction(
        task_id=task_id,
        status="PENDING",
        prediction_type="long_term"
    )

    db_session.add(new_prediction)
    db_session.commit()

    # Retrieve the record to verify it was saved correctly
    retrieved = db_session.query(Prediction).filter_by(task_id=task_id).one()

    assert retrieved.task_id == task_id
    assert retrieved.status == "PENDING"
    assert retrieved.prediction is None
    assert retrieved.uncertainty is None
    assert retrieved.prediction_type == "long_term"

def test_prediction_model_update(db_session):
    """
    Tests updating an existing Prediction record, for example,
    from PENDING to COMPLETED status.
    """
    task_id = "test-task-456"
    # Initial record
    prediction = Prediction(task_id=task_id, status="PENDING")
    db_session.add(prediction)
    db_session.commit()

    # Update the record
    prediction.status = "COMPLETED"
    prediction.prediction = 150.75
    prediction.uncertainty = 0.8
    db_session.commit()

    # Retrieve and verify the update
    updated_record = db_session.query(Prediction).filter_by(task_id=task_id).one()

    assert updated_record.status == "COMPLETED"
    assert updated_record.prediction == 150.75
    assert updated_record.uncertainty == 0.8
