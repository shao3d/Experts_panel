"""Database initialization and session management."""

import os
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import Table, Column, Integer, Boolean, Text, TIMESTAMP, ForeignKey, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from .base import Base, engine


# Define comment_group_drift table (created via SQL migration)
comment_group_drift = Table(
    'comment_group_drift',
    Base.metadata,
    Column('id', Integer, primary_key=True),
    Column('post_id', Integer, ForeignKey('posts.post_id'), nullable=False, unique=True),
    Column('has_drift', Boolean, nullable=False, default=False),
    Column('drift_topics', Text),  # JSON
    Column('analyzed_at', TIMESTAMP, nullable=False),
    Column('analyzed_by', Text, nullable=False),
    Column('expert_id', Text),  # Expert identifier for multi-expert support
    extend_existing=True
)


def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    """Enable foreign key support in SQLite."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def init_db():
    """Initialize database with all tables."""
    # Import all models to register them with Base
    from . import Post, Link, Comment

    # Enable foreign keys for SQLite
    event.listen(engine, "connect", enable_sqlite_foreign_keys)

    # Create all tables
    Base.metadata.create_all(bind=engine)
    print("Database initialized successfully!")


def drop_db():
    """Drop all tables (use with caution!)."""
    Base.metadata.drop_all(bind=engine)
    print("All tables dropped!")


def reset_db():
    """Reset database by dropping and recreating all tables."""
    drop_db()
    init_db()
    print("Database reset complete!")


# Async support for future use
DATABASE_URL_ASYNC = "sqlite+aiosqlite:///data/experts.db"

async_engine = create_async_engine(
    DATABASE_URL_ASYNC,
    echo=False,
    poolclass=NullPool,  # Recommended for SQLite
)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager for database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_async_db():
    """Initialize database asynchronously."""
    async with async_engine.begin() as conn:
        # Enable foreign keys for SQLite
        await conn.execute("PRAGMA foreign_keys=ON")
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
    print("Async database initialized successfully!")


async def drop_async_db():
    """Drop all tables asynchronously."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    print("All tables dropped (async)!")