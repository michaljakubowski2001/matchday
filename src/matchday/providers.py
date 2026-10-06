"""Where fixtures and results come from.

Both providers return the same plain records, so the sync code and the tests
never depend on the external API.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

import httpx


@dataclass(frozen=True)
class Fixture:
    external_id: str
    competition: str
    home_team: str
    away_team: str
    kickoff: datetime
    status: str
    home_score: int | None
    away_score: int | None


class Provider(Protocol):
    def fixtures(self, date_from: datetime, date_to: datetime) -> list[Fixture]: ...


class FootballDataProvider:
    """football-data.org API v4. The free plan allows 10 requests per minute."""

    base_url = "https://api.football-data.org/v4"

    def __init__(self, token: str, competitions: list[str], client: httpx.Client | None = None):
        if not token:
            raise ValueError("MATCHDAY_FOOTBALL_DATA_TOKEN is required for the football-data provider")
        self.competitions = competitions
        self.client = client or httpx.Client(base_url=self.base_url, timeout=20)
        self.headers = {"X-Auth-Token": token}

    def fixtures(self, date_from: datetime, date_to: datetime) -> list[Fixture]:
        result = []
        for code in self.competitions:
            response = self.client.get(
                f"/competitions/{code}/matches",
                params={"dateFrom": date_from.date().isoformat(), "dateTo": date_to.date().isoformat()},
                headers=self.headers,
            )
            response.raise_for_status()
            result += [parse_football_data(code, match) for match in response.json()["matches"]]
        return result


def parse_football_data(competition: str, match: dict) -> Fixture:
    full_time = match["score"]["fullTime"]
    return Fixture(
        external_id=f"fd-{match['id']}",
        competition=competition,
        home_team=match["homeTeam"].get("shortName") or match["homeTeam"]["name"],
        away_team=match["awayTeam"].get("shortName") or match["awayTeam"]["name"],
        kickoff=datetime.fromisoformat(match["utcDate"].replace("Z", "+00:00")),
        status=match["status"],
        home_score=full_time["home"],
        away_score=full_time["away"],
    )


class FakeProvider:
    """Deterministic fixtures around `now`: results in the past, matches to predict ahead."""

    TEAMS = [
        ("Arsenal", "Chelsea"),
        ("Liverpool", "Man City"),
        ("Real Madrid", "Barcelona"),
        ("Bayern", "Dortmund"),
        ("Inter", "Milan"),
        ("PSG", "Marseille"),
    ]

    def __init__(self, now: datetime | None = None):
        self.now = (now or datetime.now(UTC)).replace(minute=0, second=0, microsecond=0)

    def fixtures(self, date_from: datetime, date_to: datetime) -> list[Fixture]:
        fixtures = []
        for i, (home, away) in enumerate(self.TEAMS):
            kickoff = self.now + timedelta(days=i - 2, hours=2)
            played = kickoff < self.now
            fixtures.append(
                Fixture(
                    external_id=f"fake-{i}",
                    competition="CL" if i % 2 else "PL",
                    home_team=home,
                    away_team=away,
                    kickoff=kickoff,
                    status="FINISHED" if played else "TIMED",
                    home_score=(i + 1) % 3 if played else None,
                    away_score=i % 2 if played else None,
                )
            )
        return [f for f in fixtures if date_from <= f.kickoff <= date_to]
