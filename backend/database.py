"""
Database configuration and session management.

This module sets up SQLAlchemy for SQLite database operations.
Provides database session dependency for FastAPI route handlers.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# SQLite database URL - stored in local file
SQLALCHEMY_DATABASE_URL = "sqlite:///./av_ethics.db"

# Create database engine
# connect_args required for SQLite to work with multiple threads
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

# Create sessionmaker for database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for ORM models
Base = declarative_base()


def get_db():
    """
    Database session dependency for FastAPI.

    Yields a database session and ensures it's closed after use.
    Usage in FastAPI routes:
        @app.get("/items")
        def read_items(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize the database by creating all tables.
    Called on application startup.
    """
    Base.metadata.create_all(bind=engine)
