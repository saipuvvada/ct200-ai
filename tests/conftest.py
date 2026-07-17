import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.base import Base
import app.models  # Ensure all models are imported before create_all

from sqlalchemy.pool import StaticPool

@pytest.fixture(name="db_session")
def db_session_fixture():
    """
    Creates an isolated in-memory SQLite database for testing,
    binds it to the Base model metadata, and yields a DB session.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    )
    
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(name="client")
def client_fixture(db_session):
    """
    FastAPI TestClient fixture that overrides get_db dependency
    to use the isolated testing DB session.
    """
    from fastapi.testclient import TestClient
    from app.main import app
    from app.database.session import get_db

    app.dependency_overrides[get_db] = lambda: db_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
