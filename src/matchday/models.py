from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from matchday.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class League(Base):
    __tablename__ = "leagues"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    invite_code: Mapped[str] = mapped_column(String(16), unique=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    members: Mapped[list[Membership]] = relationship(back_populates="league")


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("league_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    league: Mapped[League] = relationship(back_populates="members")
    user: Mapped[User] = relationship()


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Identifier at the data provider, so repeated syncs update instead of duplicating.
    external_id: Mapped[str] = mapped_column(String(64), unique=True)
    competition: Mapped[str] = mapped_column(String(8))
    home_team: Mapped[str] = mapped_column(String(64))
    away_team: Mapped[str] = mapped_column(String(64))
    kickoff: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(16))
    home_score: Mapped[int | None]
    away_score: Mapped[int | None]

    @property
    def finished(self) -> bool:
        return self.status == "FINISHED" and self.home_score is not None and self.away_score is not None


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (UniqueConstraint("user_id", "match_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"))
    home_score: Mapped[int]
    away_score: Mapped[int]
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    match: Mapped[Match] = relationship()
