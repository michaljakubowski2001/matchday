from dataclasses import replace
from datetime import UTC, datetime

from sqlalchemy import func, select

from matchday.models import Match
from matchday.providers import FakeProvider
from matchday.sync import sync_matches

NOW = datetime.now(UTC)


class Fixed:
    def __init__(self, fixtures):
        self._fixtures = fixtures

    def fixtures(self, date_from, date_to):
        return self._fixtures


def test_sync_is_idempotent(db):
    provider = FakeProvider(NOW)
    first = sync_matches(db, provider, NOW)
    second = sync_matches(db, provider, NOW)
    assert first["created"] == first["fetched"] > 0
    assert second == {"fetched": first["fetched"], "created": 0, "updated": 0}
    assert db.scalar(select(func.count(Match.id))) == first["fetched"]


def test_sync_updates_result_of_existing_match(db):
    fixture = FakeProvider(NOW).fixtures(NOW.replace(year=2000), NOW.replace(year=2100))[-1]
    sync_matches(db, Fixed([fixture]), NOW)
    finished = replace(fixture, status="FINISHED", home_score=4, away_score=0)
    assert sync_matches(db, Fixed([finished]), NOW)["updated"] == 1
    match = db.scalar(select(Match).where(Match.external_id == fixture.external_id))
    db.refresh(match)
    assert (match.status, match.home_score, match.away_score) == ("FINISHED", 4, 0)
