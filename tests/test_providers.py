from datetime import UTC, datetime, timedelta

import httpx
import pytest

from matchday.providers import FakeProvider, FootballDataProvider, parse_football_data

FOOTBALL_DATA_MATCH = {
    "id": 537785,
    "utcDate": "2026-10-21T19:00:00Z",
    "status": "FINISHED",
    "homeTeam": {"name": "Arsenal FC", "shortName": "Arsenal"},
    "awayTeam": {"name": "Club Atlético de Madrid", "shortName": None},
    "score": {"fullTime": {"home": 2, "away": 1}},
}


def test_parse_football_data_uses_short_names_and_utc():
    fixture = parse_football_data("CL", FOOTBALL_DATA_MATCH)
    assert fixture.external_id == "fd-537785"
    assert (fixture.home_team, fixture.away_team) == ("Arsenal", "Club Atlético de Madrid")
    assert fixture.kickoff == datetime(2026, 10, 21, 19, tzinfo=UTC)
    assert (fixture.home_score, fixture.away_score) == (2, 1)


def test_football_data_provider_queries_each_competition():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.path, request.headers["X-Auth-Token"]))
        return httpx.Response(200, json={"matches": [FOOTBALL_DATA_MATCH]})

    client = httpx.Client(base_url=FootballDataProvider.base_url, transport=httpx.MockTransport(handler))
    provider = FootballDataProvider("token", ["CL", "PL"], client=client)
    now = datetime.now(UTC)
    fixtures = provider.fixtures(now, now + timedelta(days=1))
    assert [path for path, _ in seen] == ["/v4/competitions/CL/matches", "/v4/competitions/PL/matches"]
    assert {token for _, token in seen} == {"token"}
    assert len(fixtures) == 2


def test_football_data_provider_requires_token():
    with pytest.raises(ValueError, match="TOKEN"):
        FootballDataProvider("", ["CL"])


def test_fake_provider_has_results_and_open_matches():
    now = datetime(2026, 10, 6, 12, tzinfo=UTC)
    fixtures = FakeProvider(now).fixtures(now - timedelta(days=7), now + timedelta(days=14))
    assert any(f.status == "FINISHED" and f.home_score is not None for f in fixtures)
    assert any(f.kickoff > now and f.home_score is None for f in fixtures)
