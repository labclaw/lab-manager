"""Alembic migration environment."""

from sqlalchemy import create_engine
from sqlmodel import SQLModel

from alembic import context
from lab_manager.config import get_settings

# Import all models so they register with SQLModel.metadata
from lab_manager.models import *  # noqa: F401, F403

target_metadata = SQLModel.metadata


def run_migrations_online():
    settings = get_settings()
    engine = create_engine(settings.database_url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
