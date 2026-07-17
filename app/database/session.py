import os
from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.config import settings

# Parse the database URL and ensure parent directories exist (especially for SQLite files)
db_url = settings.DATABASE_URL
if db_url.startswith("sqlite:///"):
    db_path_str = db_url.replace("sqlite:///", "")
    # Handle absolute vs relative paths
    db_path = Path(db_path_str)
    if not db_path.is_absolute():
        # Relative to current working directory
        db_path = Path.cwd() / db_path
    
    # Create the directory containing the SQLite database if it does not exist
    os.makedirs(db_path.parent, exist_ok=True)

# Create SQLAlchemy engine
# For SQLite, check_same_thread=False allows FastAPI threads to access the DB concurrently
connect_args = {"check_same_thread": False} if db_url.startswith("sqlite://") else {}

engine = create_engine(
    db_url,
    connect_args=connect_args,
    echo=settings.DEBUG
)

# Sessionmaker for generating database sessions
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

def get_db() -> Generator[Session, None, None]:
    """
    Dependency injection helper to retrieve database session.
    Yields session and closes it after the request completes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
