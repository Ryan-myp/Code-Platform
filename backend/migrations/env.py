"""Alembic Config object."""
import os
from configparser import ConfigParser

from alembic import context

# 加载 alembic.ini
here = os.path.dirname(os.path.abspath(__file__))
config = ConfigParser()
config.read(os.path.join(here, "alembic.ini"))

target_metadata = None


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy_url")
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
    import sqlite3
    from alembic.migration import MigrationContext
    from sqlalchemy import engine_from_config, pool

    connectable = engine_from_config(
        config.get_section(config.get_ini_section("alembic", {})),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
