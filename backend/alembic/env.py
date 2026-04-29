"""
Alembic ortamı — sync engine (asyncpg URL otomatik dönüştürülür).
Çalıştırma: backend klasöründe  alembic upgrade head
"""
from __future__ import annotations

import os
import re
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool, create_engine

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def get_sync_database_url() -> str:
    raw = os.environ.get(
        "DATABASE_URL",
        config.get_main_option("sqlalchemy.url") or "",
    )
    if not raw:
        raise RuntimeError("DATABASE_URL ortam değişkeni veya alembic.ini sqlalchemy.url gerekli")
    # asyncpg / psycopg async soneklerini kaldır
    url = re.sub(r"\+asyncpg|\+psycopg", "", raw, count=1)
    if url.startswith("postgresql+asyncpg"):
        url = url.replace("postgresql+asyncpg", "postgresql", 1)
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=get_sync_database_url(),
        target_metadata=None,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(get_sync_database_url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
