"""Database base configuration for SQLAlchemy models."""

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Database URL configuration
# Production: PostgreSQL via DATABASE_URL environment variable
# Local: SQLite fallback for development
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/experts.db")

# Engine configuration based on database type
if DATABASE_URL.startswith("postgresql://"):
    # PostgreSQL configuration with connection pool
    engine = create_engine(
        DATABASE_URL,
        pool_size=20,
        max_overflow=30,
        pool_timeout=60
    )
else:
    # SQLite configuration (local development + Fly.io production)
    # Use StaticPool to share a single connection and avoid pool exhaustion
    # This is safe for SQLite with check_same_thread=False
    from sqlalchemy.pool import StaticPool
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},  # Needed for SQLite
        poolclass=StaticPool
    )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create declarative base
Base = declarative_base()