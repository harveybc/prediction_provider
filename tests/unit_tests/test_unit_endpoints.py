import pytest
from pydantic import ValidationError
from app.models import PredictionRequest  # Assuming the model is in app.models

def test_valid_prediction_request():
    """
    Tests that a valid dictionary successfully creates a PredictionRequest model.
    """
    valid_data = {
        "ticker": "AAPL",
        "model_name": "default_model",
        "start_date": "2023-01-01",
        "end_date": "2023-12-31"
    }
    try:
        PredictionRequest(**valid_data)
    except ValidationError as e:
        pytest.fail(f"Validation failed unexpectedly: {e}")

def test_invalid_request_missing_ticker():
    """
    Tests that a dictionary missing the required 'ticker' field raises a ValidationError.
    """
    invalid_data = {
        "model_name": "default_model",
        "start_date": "2023-01-01",
        "end_date": "2023-12-31"
    }
    with pytest.raises(ValidationError) as excinfo:
        PredictionRequest(**invalid_data)

    # Check that the error message clearly indicates the missing field
    assert "ticker" in str(excinfo.value)

def test_invalid_request_bad_date_format():
    """
    Tests that a dictionary with an invalid date format raises a ValidationError.
    """
    invalid_data = {
        "ticker": "AAPL",
        "start_date": "not-a-date"
    }
    with pytest.raises(ValidationError) as excinfo:
        PredictionRequest(**invalid_data)

    assert "start_date" in str(excinfo.value)
