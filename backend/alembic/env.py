"""Alembic environment configuration."""

import sys
from pathlib import Path

# Add the backend directory to Python path so 'app' can be imported
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from logging.config import fileConfig

from alembic import context

# this is the Alembic Config object, which provides
# the values of the alembic.ini file in Python format.
# for Python 3.12+, use SQLAlchemy 2.0 style URLs
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
from app.core.database import Base
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    from app.core.config import settings
    
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = settings.database_url

    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with async support.

    In this scenario we need to create an async Engine
    and associate a connection with the context.

    """
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine
    from app.core.config import settings
    
    async def do_run_migrations():
        # Create async engine for asyncpg driver
        engine = create_async_engine(
            settings.database_url,
            echo=False,
            future=True,
        )

        async with engine.begin() as connection:
            # Run migrations in a sync context within the async connection
            def run_migrations_sync(sync_conn):
                context.configure(
                    connection=sync_conn,
                    target_metadata=target_metadata
                )
                with context.begin_transaction():
                    context.run_migrations()
            
            await connection.run_sync(run_migrations_sync)

    asyncio.run(do_run_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
