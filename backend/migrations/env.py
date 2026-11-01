import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.models  # noqa: F401 - register model metadata
from app.core.config import Settings
from app.core.database import Base, create_database_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
settings = Settings()
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_database_engine(settings.database_url)
    with engine.connect() as connection:
        is_sqlite = connection.dialect.name == "sqlite"
        if is_sqlite:
            # SQLite table rebuilds can fail when existing child rows reference the table.
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.commit()
        try:
            context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
            with context.begin_transaction():
                context.run_migrations()
        finally:
            if is_sqlite:
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
                connection.commit()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
