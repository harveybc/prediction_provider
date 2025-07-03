import pytest
from unittest.mock import Mock, patch

# Corrected import path
from app.pipeline_plugins.default_pipeline import DefaultPipeline

@pytest.fixture
def mock_feeder_predictor():
    """Provides mock feeder and predictor plugins."""
    mock_feeder = Mock()
    mock_predictor = Mock()
    mock_feeder.get_data.return_value = "some_processed_data"
    mock_predictor.predict.return_value = (123.45, 0.5)
    return mock_feeder, mock_predictor

@pytest.fixture
def pipeline(mock_feeder_predictor):
    """Provides a DefaultPipeline instance with mocked dependencies."""
    feeder, predictor = mock_feeder_predictor
    return DefaultPipeline(feeder=feeder, predictor=predictor)

def test_pipeline_run_for_long_term(pipeline, mock_feeder_predictor):
    """
    Tests the pipeline's run method for a long-term prediction.
    It should call its dependencies with the correct parameters.
    """
    feeder, predictor = mock_feeder_predictor
    request_params = {
        "prediction_type": "long_term",
        "datetime": "2025-01-01T00:00:00Z"
    }

    result = pipeline.run(request_params)

    # Verify feeder was called with long-term window size
    feeder.get_data.assert_called_once_with(
        datetime="2025-01-01T00:00:00Z",
        window_size=288, # As per REFERENCE.md
        prediction_type="long_term"
    )

    # Verify predictor was configured for long-term model and then used
    predictor.load_model.assert_called_once_with("long_term")
    predictor.predict.assert_called_once_with("some_processed_data")

    # Verify the final result
    assert result == (123.45, 0.5)

def test_pipeline_run_for_short_term(pipeline, mock_feeder_predictor):
    """
    Tests the pipeline's run method for a short-term prediction.
    """
    feeder, predictor = mock_feeder_predictor
    request_params = {
        "prediction_type": "short_term",
        "datetime": "2025-01-01T00:00:00Z"
    }

    pipeline.run(request_params)

    # Verify feeder was called with short-term window size
    feeder.get_data.assert_called_once_with(
        datetime="2025-01-01T00:00:00Z",
        window_size=128, # As per REFERENCE.md
        prediction_type="short_term"
    )
    predictor.load_model.assert_called_once_with("short_term")
    predictor.predict.assert_called_once_with("some_processed_data")

def test_pipeline_propagates_exceptions_from_feeder(mock_feeder_predictor):
    """
    Tests that if the feeder fails, the pipeline raises the same exception.
    """
    feeder, predictor = mock_feeder_predictor
    feeder.get_data.side_effect = ValueError("Feeder failed")

    pipeline = DefaultPipeline(feeder=feeder, predictor=predictor)

    with pytest.raises(ValueError, match="Feeder failed"):
        pipeline.run({"prediction_type": "short_term", "datetime": "2025-01-01T00:00:00Z"})

def test_pipeline_propagates_exceptions_from_predictor(mock_feeder_predictor):
    """
    Tests that if the predictor fails, the pipeline raises the same exception.
    """
    feeder, predictor = mock_feeder_predictor
    predictor.predict.side_effect = RuntimeError("Predictor failed")

    pipeline = DefaultPipeline(feeder=feeder, predictor=predictor)

    with pytest.raises(RuntimeError, match="Predictor failed"):
        pipeline.run({"prediction_type": "short_term", "datetime": "2025-01-01T00:00:00Z"})
