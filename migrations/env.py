from logging.config import fileConfig

from alembic import context

import matchday.models  # noqa: F401  (registers the tables on Base.metadata)
from matchday.db import Base, get_engine

if context.config.config_file_name is not None:
    fileConfig(context.config.config_file_name)


def run_migrations() -> None:
    with get_engine().connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise SystemExit("Offline migrations are not supported; run against a database.")
run_migrations()
