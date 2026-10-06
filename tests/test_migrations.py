from alembic import command
from alembic.config import Config


def test_models_and_migrations_match():
    """Fails when a model changes without a new migration (alembic check)."""
    command.check(Config("alembic.ini"))
