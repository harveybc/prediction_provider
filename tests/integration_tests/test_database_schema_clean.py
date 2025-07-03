#!/usr/bin/env python3
"""
Integration tests for database schema validation.
"""

import pytest
from sqlalchemy import create_engine, inspect
from app.database_models import Base, User, Role, PredictionJob, ApiLog, TimeSeriesData

class TestDatabaseSchema:
    """Test database schema creation and validation."""
    
    @pytest.fixture
    def test_engine(self):
        """Create a test database engine."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        yield engine
        engine.dispose()
    
    def test_all_tables_created(self, test_engine):
        """Verify that all expected tables are created in the database."""
        inspector = inspect(test_engine)
        table_names = inspector.get_table_names()
        
        expected_tables = {'users', 'roles', 'prediction_jobs', 'api_logs', 'time_series_data'}
        actual_tables = set(table_names)
        
        assert expected_tables.issubset(actual_tables), f"Missing tables: {expected_tables - actual_tables}"
    
    @pytest.mark.parametrize("table_class,expected_columns", [
        (User, ['id', 'username', 'hashed_api_key', 'is_active', 'role_id']),
        (Role, ['id', 'name', 'permissions']),
        (PredictionJob, ['id', 'user_id', 'status', 'request_payload', 'result', 'created_at', 'updated_at']),
        (ApiLog, ['id', 'request_id', 'user_id', 'ip_address', 'endpoint', 'method', 'request_timestamp', 'response_status_code', 'response_time_ms']),
        (TimeSeriesData, ['ticker', 'timestamp', 'open', 'high', 'low', 'close', 'volume'])
    ])
    def test_table_columns(self, test_engine, table_class, expected_columns):
        """Verify that each table has the expected columns."""
        inspector = inspect(test_engine)
        columns = inspector.get_columns(table_class.__tablename__)
        column_names = [col['name'] for col in columns]
        
        for expected_col in expected_columns:
            assert expected_col in column_names, f"Missing column '{expected_col}' in table '{table_class.__tablename__}'"
