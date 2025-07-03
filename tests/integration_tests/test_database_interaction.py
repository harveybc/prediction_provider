import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, inspect
from app.models import Base, User, TimeSeriesData  # Assuming models are in app.models
from app.main import create_database_and_tables
import unittest

DATABASE_URL = "sqlite+aiosqlite:///:memory:"
# Use an in-memory SQLite database for testing
TEST_DB_URL = "sqlite:///:memory:"

@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="module")
async def test_db():
    engine = create_async_engine(DATABASE_URL, echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_database_lifecycle(test_db):
    # The fixture itself tests the lifecycle.
    # We can add an explicit check to ensure tables were created.
    engine = test_db
    async with engine.connect() as conn:
        result = await conn.run_sync(
            lambda sync_conn: sync_conn.dialect.has_table(sync_conn, "time_series_data")
        )
        assert result is True

@pytest.mark.asyncio
async def test_data_persistence_and_retrieval(test_db):
    engine = test_db
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as session:
        async with session.begin():
            # Create a dummy data entry
            dummy_data = TimeSeriesData(
                ticker="AAPL",
                timestamp=1672531200,
                open=150.0,
                high=155.0,
                low=149.0,
                close=154.5,
                volume=1000000
            )
            session.add(dummy_data)

    async with AsyncSessionLocal() as session:
        # Retrieve the data
        result = await session.get(TimeSeriesData, ("AAPL", 1672531200))
        assert result is not None
        assert result.ticker == "AAPL"
        assert result.close == 154.5

class TestDatabaseInteraction(unittest.TestCase):
    """
    Integration tests for database interactions.
    
    These tests verify the database lifecycle (creation/teardown) and
    basic data persistence and retrieval, ensuring the database layer
    works as expected.
    """

    def setUp(self):
        """Create a fresh in-memory database for each test."""
        self.engine = create_engine(TEST_DB_URL)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def tearDown(self):
        """Drop all tables after each test."""
        Base.metadata.drop_all(self.engine)

    def test_database_lifecycle(self):
        """
        Test Case 3.1: Verify database and table creation.
        """
        # The setUp method already creates the tables.
        # We inspect the database to confirm they exist.
        inspector = inspect(self.engine)
        tables = inspector.get_table_names()
        self.assertIn("users", tables)
        self.assertIn("time_series_data", tables)

    def test_data_persistence_and_retrieval(self):
        """
        Test Case 3.2: Ensure data can be written to and read from the database.
        """
        # Arrange: Create a new user record
        session = self.SessionLocal()
        new_user = User(username="testuser", email="test@example.com", hashed_password="abc")
        session.add(new_user)
        session.commit()
        session.refresh(new_user)

        # Act: Retrieve the user from the database
        retrieved_user = session.query(User).filter(User.username == "testuser").first()

        # Assert: Verify the retrieved data matches the original data
        self.assertIsNotNone(retrieved_user)
        self.assertEqual(retrieved_user.email, "test@example.com")
        
        session.close()

if __name__ == '__main__':
    unittest.main()
