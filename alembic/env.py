"""Alembic migration environment."""

from alembic import context
from sqlalchemy import create_engine, text
from sqlmodel import SQLModel

# Import all models so they register with SQLModel.metadata
from lab_manager.models import *  # noqa: F401, F403
from lab_manager.config import get_settings

target_metadata = SQLModel.metadata

# Schema used for all tables. On managed platforms (e.g. DO App Platform)
# the default user may lack CREATE privilege on the 'public' schema.
# Using a custom schema the app user owns avoids this PG 15+ restriction.
APP_SCHEMA = "labmanager"


def run_migrations_online():
    settings = get_settings()
    engine = create_engine(settings.database_url)
    with engine.connect() as connection:
        # Ensure our custom schema exists and is in the search path.
        connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {APP_SCHEMA}"))
        connection.execute(text(f"SET search_path TO {APP_SCHEMA}, public"))
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=APP_SCHEMA,
        )
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
