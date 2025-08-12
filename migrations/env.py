from __future__ import annotations

import os
from logging.config import fileConfig

from sqlalchemy import pool
from alembic import context

from flask import current_app
from app.db import db

config = context.config

fileConfig(config.config_file_name)

# Use Flask-SQLAlchemy metadata
target_metadata = db.metadata


def get_url() -> str:
    # Prefer Flask app config set via Flask-SQLAlchemy
    url = current_app.config.get("SQLALCHEMY_DATABASE_URI")
    if url:
        return url
    # Fallback to envs
    url = os.getenv("DATABASE_URL_DIRECT") or os.getenv("DATABASE_URL")
    if url:
        s = url.strip()
        if s.lower().startswith("psql "):
            s = s[5:].strip()
        if s.startswith("'") and s.endswith("'"):
            s = s[1:-1]
        if s.startswith("postgresql://"):
            s = "postgresql+psycopg://" + s[len("postgresql://") :]
        return s
    return "sqlite+pysqlite:///linkerhero.sqlite3"


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()
    connectable = db.engine

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

