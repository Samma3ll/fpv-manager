"""Database connection and session management."""

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


# Engine and session will be initialized lazily
engine = None
AsyncSessionLocal = None


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


def get_engine():
    """Get or create the async engine (lazy initialization)."""
    global engine
    if engine is None:
        engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            future=True,
            pool_pre_ping=True,
            pool_size=20,
            max_overflow=10,
        )
    return engine


def get_session_factory():
    """Get or create the async session factory (lazy initialization)."""
    global AsyncSessionLocal
    if AsyncSessionLocal is None:
        engine = get_engine()
        AsyncSessionLocal = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return AsyncSessionLocal


async def get_db_session() -> AsyncSession:
    """Dependency to get database session for FastAPI routes."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


async def init_db() -> None:
    """Initialize database tables if using direct creation (not migrations).

    Checks if Alembic migration tracking table exists. If it does,
    migrations are being used and table creation is skipped.
    If not, creates all tables for development convenience.
    """
    from sqlalchemy import inspect

    engine = get_engine()

    # Check if alembic_version table exists (indicates migrations are in use)
    async with engine.begin() as conn:
        has_alembic_version = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).has_table("alembic_version")
        )

        if has_alembic_version:
            # Migrations table exists - skip create_all
            return

        # Create all tables
        await conn.run_sync(Base.metadata.create_all)


async def drop_db() -> None:
    """Drop all database tables (development only)."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
