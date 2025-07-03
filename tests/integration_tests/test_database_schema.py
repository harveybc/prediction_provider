import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.inspection import inspect
from app.database_models import Base, User, Role, PredictionJob, ApiLog, TimeSeriesData

DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="module")
async def test_engine():
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()

@pytest.mark.asyncio
async def test_all_tables_created(test_engine):
    """Verify that all expected tables are created in the database."""
    async with test_engine.connect() as conn:
        def get_table_names(sync_conn):
            inspector = inspect(sync_conn)
            return inspector.get_table_names()
        
        tables = await conn.run_sync(get_table_names)
        
        expected_tables = {
            'users', 
            'roles', 
            'prediction_jobs', 
            'api_logs', 
            'time_series_data'
        }
        assert set(tables) == expected_tables

@pytest.mark.asyncio
@pytest.mark.parametrize("table_class, expected_columns", [
    (User, ['id', 'username', 'hashed_api_key', 'is_active', 'role_id']),
    (Role, ['id', 'name', 'permissions']),
    (PredictionJob, ['id', 'user_id', 'status', 'request_payload', 'result', 'created_at', 'updated_at']),
    (ApiLog, ['id', 'request_id', 'user_id', 'ip_address', 'endpoint', 'method', 'request_timestamp', 'response_status_code', 'response_time_ms']),
    (TimeSeriesData, ['ticker', 'timestamp', 'open', 'high', 'low', 'close', 'volume'])
])
async def test_table_columns(test_engine, table_class, expected_columns):
    """Verify that each table has the correct columns."""
    inspector = inspect(table_class)
    assert set(c.name for c in inspector.columns) == set(expected_columns)
