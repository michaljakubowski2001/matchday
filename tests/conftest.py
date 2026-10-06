import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

os.environ.setdefault("MATCHDAY_SECRET_KEY", "test-secret")
os.environ.setdefault(
    "MATCHDAY_DATABASE_URL", "postgresql+psycopg://matchday:matchday@localhost:5432/matchday_test"
)

from matchday.config import get_settings  # noqa: E402
from matchday.db import get_engine  # noqa: E402
from matchday.models import Match  # noqa: E402
from matchday.web import create_app  # noqa: E402

TABLES = "predictions, memberships, leagues, matches, users"


@pytest.fixture(scope="session", autouse=True)
def schema() -> None:
    """Build the test database from the migrations, so they are tested too."""
    config = Config("alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")


@pytest.fixture
def db() -> Iterator[Session]:
    with sessionmaker(get_engine(), expire_on_commit=False)() as session:
        yield session
    with get_engine().begin() as connection:
        connection.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))


@pytest.fixture
def client(db: Session) -> TestClient:
    return TestClient(create_app(get_settings()), follow_redirects=False)


@pytest.fixture
def make_match(db: Session):
    def make(hours_from_now: float, home_score: int | None = None, away_score: int | None = None) -> Match:
        kickoff = datetime.now(UTC) + timedelta(hours=hours_from_now)
        match = Match(
            external_id=f"t-{kickoff.timestamp()}-{home_score}-{away_score}",
            competition="PL",
            home_team="Home",
            away_team="Away",
            kickoff=kickoff,
            status="FINISHED" if home_score is not None else "TIMED",
            home_score=home_score,
            away_score=away_score,
        )
        db.add(match)
        db.commit()
        return match

    return make


@pytest.fixture
def register(client: TestClient):
    def register(username: str, password: str = "correct-horse") -> None:
        response = client.post("/register", data={"username": username, "password": password})
        assert response.status_code == 303, response.text

    return register
