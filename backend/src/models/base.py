"""Database base configuration for SQLAlchemy models."""

from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import sqlite_vec

try:
    from .. import config
except ImportError:  # Compatibility for legacy top-level imports like `from models import ...`
    import config  # type: ignore

# Database URL configuration
# Production: PostgreSQL via DATABASE_URL environment variable
# Local: SQLite fallback for development
DATABASE_URL = config.DATABASE_URL

# Engine configuration based on database type
if DATABASE_URL.startswith("postgresql://"):
    # PostgreSQL configuration with connection pool
    engine = create_engine(DATABASE_URL, pool_size=20, max_overflow=30, pool_timeout=60)
else:
    # SQLite configuration (local development + Fly.io production)
    # Use StaticPool to share a single connection and avoid pool exhaustion
    # This is safe for SQLite with check_same_thread=False
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},  # Needed for SQLite
        poolclass=StaticPool,
    )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create declarative base
Base = declarative_base()


# Load sqlite-vec extension for SQLite databases (Linux only)
@event.listens_for(engine, "connect")
def _load_sqlite_extensions(dbapi_conn, connection_record):
    """Load sqlite-vec extension for vector search support.

    Note: This requires enable_load_extension support (Linux/macOS with custom Python build).
    Falls back silently on platforms that don't support it (e.g., macOS system Python).
    """
    try:
        dbapi_conn.enable_load_extension(True)
        sqlite_vec.load(dbapi_conn)
        dbapi_conn.enable_load_extension(False)
    except AttributeError:
        import warnings
        warnings.warn(
            "sqlite-vec extension NOT loaded — enable_load_extension() unavailable. "
            "Vector search will fall back to ALL posts (slower). "
            "Use Homebrew Python (python3.13) or Docker for full hybrid retrieval.",
            RuntimeWarning,
            stacklevel=2,
        )
