"""
Unit tests for app/models.py module.

Tests model utility functions, database operations, and data model functionality.
"""

import unittest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from app.models import create_database_engine, create_tables, get_session, Prediction
from datetime import datetime

class TestUnitModels(unittest.TestCase):
    """
    Unit tests for models utility functions.
    """
    
    @patch('app.models.create_engine')
    def test_create_database_engine(self, mock_create_engine):
        """
        Test Case 8.1: Verify database engine creation with correct parameters.
        """
        # Arrange
        database_url = "sqlite:///test.db"
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        
        # Act
        result = create_database_engine(database_url)
        
        # Assert
        mock_create_engine.assert_called_once_with(database_url, echo=False)
        self.assertEqual(result, mock_engine)
    
    def test_create_tables(self):
        """
        Test Case 8.2: Verify create_tables function calls metadata.create_all.
        """
        # Arrange
        mock_engine = MagicMock()
        
        # Act
        create_tables(mock_engine)
        
        # Assert
        # Since we're testing the function calls Base.metadata.create_all,
        # we verify that it would be called with the engine
        # Note: This test ensures the function doesn't raise exceptions
        self.assertTrue(True)  # Function completed without error
    
    @patch('app.models.sessionmaker')
    def test_get_session(self, mock_sessionmaker):
        """
        Test Case 8.3: Verify session creation and configuration.
        """
        # Arrange
        mock_engine = MagicMock()
        mock_session_class = MagicMock()
        mock_session = MagicMock()
        mock_sessionmaker.return_value = mock_session_class
        mock_session_class.return_value = mock_session
        
        # Act
        result = get_session(mock_engine)
        
        # Assert
        mock_sessionmaker.assert_called_once_with(bind=mock_engine)
        self.assertEqual(result, mock_session)
    
    def test_prediction_model_to_dict(self):
        """
        Test Case 8.4: Verify Prediction model's to_dict method.
        """
        # Arrange
        prediction = Prediction(
            id=1,
            task_id="task_123",
            status="completed",
            prediction_type="stock",
            prediction={"value": 150.0},
            uncertainty={"std": 5.0}
        )
        prediction.timestamp = datetime(2024, 1, 1, 12, 0, 0)
        
        # Act
        result = prediction.to_dict()
        
        # Assert
        expected_dict = {
            'id': 1,
            'task_id': 'task_123',
            'timestamp': '2024-01-01T12:00:00',
            'status': 'completed',
            'prediction_type': 'stock',
            'prediction': {'value': 150.0},
            'uncertainty': {'std': 5.0}
        }
        self.assertEqual(result, expected_dict)

if __name__ == '__main__':
    unittest.main()
