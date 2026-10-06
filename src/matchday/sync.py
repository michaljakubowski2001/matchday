from dataclasses import asdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from matchday.config import Settings
from matchday.models import Match
from matchday.providers import FakeProvider, FootballDataProvider, Provider


def provider_from_settings(settings: Settings) -> Provider:
    if settings.provider == "football-data":
        return FootballDataProvider(settings.football_data_token, settings.competitions)
    if settings.provider == "fake":
        return FakeProvider()
    raise ValueError(f"Unknown provider: {settings.provider}")


def sync_matches(session: Session, provider: Provider, now: datetime | None = None) -> dict[str, int]:
    """Upsert fixtures from a week ago to two weeks ahead. Safe to run repeatedly."""
    now = now or datetime.now(UTC)
    fixtures = provider.fixtures(now - timedelta(days=7), now + timedelta(days=14))
    ids = [fixture.external_id for fixture in fixtures]
    query = select(Match).where(Match.external_id.in_(ids))
    existing = {match.external_id: match for match in session.scalars(query)}
    created = updated = 0
    for fixture in fixtures:
        values = asdict(fixture)
        match = existing.get(fixture.external_id)
        if match is None:
            session.add(Match(**values))
            created += 1
        elif any(getattr(match, key) != value for key, value in values.items()):
            for key, value in values.items():
                setattr(match, key, value)
            updated += 1
    session.commit()
    return {"fetched": len(fixtures), "created": created, "updated": updated}
