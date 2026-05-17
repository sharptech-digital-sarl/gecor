from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
from urllib.parse import unquote
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.database import Base
from app.core.config import settings
from app.models import *  # Import all models

# this is the Alembic Config object
config = context.config

# Override sqlalchemy.url with settings if available
# Use attributes to bypass ConfigParser interpolation issues with special characters
# SQLAlchemy will handle URL decoding automatically, but we store it as-is
# Note: If DATABASE_URL has encoding issues, we'll use a direct URL construction
try:
    db_url = getattr(settings, 'DATABASE_URL', None)
    if db_url:
        config.attributes['sqlalchemy.url'] = db_url
except (AttributeError, UnicodeDecodeError, UnicodeError):
    # Fallback: construct URL directly to avoid encoding issues
    # Using Docker Compose credentials: fpi-admin / Fpi-c05b6q#
    # URL-encode the # as %23
    fallback_url = "postgresql://fpi-admin:Fpi-c05b6q%23@localhost:5432/fpi_connect"
    config.attributes['sqlalchemy.url'] = fallback_url

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.attributes.get("sqlalchemy.url") or config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Use the URL from attributes if available, otherwise from config
    url = config.attributes.get("sqlalchemy.url") or config.get_main_option("sqlalchemy.url")
    connectable = engine_from_config(
        {"sqlalchemy.url": url},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

