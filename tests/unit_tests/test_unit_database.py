import unittest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Assuming database models and utilities are in these paths
from app.database_models import Base, User, Role, PredictionJob, ApiLog, TimeSeriesData
from app.database_utilities import get_db_session, create_all_tables

class TestUnitDatabase(unittest.TestCase):
    """
    Unit tests for database utility functions.
    
    These tests verify the database session handling and table creation logic.
    The actual database connection is mocked to ensure tests are fast and isolated.
    """

    @patch('app.database_utilities.create_engine')
    def test_create_all_tables(self, mock_create_engine):
        """
        Test that the create_all_tables function invokes the SQLAlchemy metadata creation.
        """
        # Arrange: Mock the engine and its `connect` method
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        
        # Act: Call the function to create tables
        create_all_tables("sqlite:///:memory:")

        # Assert: Verify that the `create_all` method was called on the Base metadata
        mock_create_engine.assert_called_once_with("sqlite:///:memory:")
        Base.metadata.create_all.assert_called_once_with(bind=mock_engine)

    @patch('app.database_utilities.create_engine')
    @patch('app.database_utilities.sessionmaker')
    def test_get_db_session(self, mock_sessionmaker, mock_create_engine):
        """
        Test the database session generator.
        """
        # Arrange: Mock the engine and session factory
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        mock_session_factory = MagicMock()
        mock_sessionmaker.return_value = mock_session_factory
        mock_session = MagicMock()
        mock_session_factory.return_value = mock_session

        # Act: Call the session generator
        db_gen = get_db_session("sqlite:///:memory:")
        session = next(db_gen)

        # Assert: Verify the session was created and closed correctly
        mock_create_engine.assert_called_once_with("sqlite:///:memory:")
        mock_sessionmaker.assert_called_once_with(autocommit=False, autoflush=False, bind=mock_engine)
        self.assertEqual(session, mock_session)
        
        # Verify the session is closed after the `yield`
        with self.assertRaises(StopIteration):
            next(db_gen)
        mock_session.close.assert_called_once()

if __name__ == '__main__':
    unittest.main()
