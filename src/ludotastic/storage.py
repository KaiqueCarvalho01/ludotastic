"""Match history and statistics, stored with SQLModel."""

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import JSON, Column
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.pool import StaticPool
from sqlmodel import Field, Session, SQLModel, col, create_engine, select

from ludotastic.engine.match import Match

__all__ = ["MatchRecord", "PlayerStats", "Store"]


class MatchRecord(SQLModel, table=True):
    """A finished (or aborted) match, as stored."""

    __tablename__ = "matches"

    id: str = Field(primary_key=True)
    game_id: str = Field(index=True)
    status: str
    seed: int
    created_at: datetime
    finished_at: datetime | None = None
    seats: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    scores: list[float] | None = Field(default=None, sa_column=Column(JSON))
    reason: str | None = None
    turns: int = 0
    history: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))

    @classmethod
    def from_match(cls, match: Match) -> MatchRecord:
        """Snapshot a match."""
        return cls(
            id=match.id,
            game_id=match.game.info.id,
            status=str(match.status),
            seed=match.seed,
            created_at=match.created_at,
            finished_at=match.finished_at or datetime.now(UTC),
            seats=[seat.model_dump(mode="json") for seat in match.seats],
            scores=list(match.outcome.scores) if match.outcome else None,
            reason=match.outcome.reason if match.outcome else match.error,
            turns=match.turn,
            history=[move.model_dump(mode="json") for move in match.history],
        )


class PlayerStats(BaseModel):
    """How one kind of player has done at one game."""

    game_id: str
    group: str
    """The player's statistics label, such as `ai:openai:gpt-6-luna/choice`."""
    played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    score: float = 0.0
    """Total score, so a win is 1 and a two-player draw is 0.5."""

    @property
    def win_rate(self) -> float:
        """Wins per match played."""
        return self.wins / self.played if self.played else 0.0

    @property
    def mean_score(self) -> float:
        """Average score per match played."""
        return self.score / self.played if self.played else 0.0


def _engine(url: str) -> Engine:
    parsed = make_url(url)
    if parsed.get_backend_name() != "sqlite":
        return create_engine(url)
    if parsed.database in {None, "", ":memory:"}:
        # One shared connection, or every thread would see its own empty database.
        return create_engine(
            url, connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    return create_engine(url, connect_args={"check_same_thread": False})


class Store:
    """Saves matches and reads them back."""

    def __init__(self, url: str | Engine) -> None:
        """Connect to the database, creating its tables as needed."""
        self.engine = url if isinstance(url, Engine) else _engine(url)
        SQLModel.metadata.create_all(self.engine)

    def close(self) -> None:
        """Close every database connection."""
        self.engine.dispose()

    def save(self, match: Match) -> MatchRecord:
        """Save a finished match, replacing any earlier copy."""
        record = MatchRecord.from_match(match)
        with Session(self.engine) as session:
            session.merge(record)
            session.commit()
        return record

    def get(self, match_id: str) -> MatchRecord | None:
        """Look a match up by id."""
        with Session(self.engine) as session:
            return session.get(MatchRecord, match_id)

    def recent(
        self, *, game_id: str | None = None, limit: int = 50
    ) -> list[MatchRecord]:
        """The latest matches, newest first."""
        query = (
            select(MatchRecord)
            .order_by(col(MatchRecord.created_at).desc())
            .limit(limit)
        )
        if game_id is not None:
            query = query.where(MatchRecord.game_id == game_id)
        with Session(self.engine) as session:
            return list(session.exec(query).all())

    def stats(self, *, game_id: str | None = None) -> list[PlayerStats]:
        """Wins, draws and losses per game and player group, best first."""
        query = select(MatchRecord).where(MatchRecord.status == "finished")
        if game_id is not None:
            query = query.where(MatchRecord.game_id == game_id)
        table: dict[tuple[str, str], PlayerStats] = {}
        with Session(self.engine) as session:
            records = session.exec(query).all()
        for record in records:
            if record.scores is None:
                continue
            top = max(record.scores)
            tied = all(s == top for s in record.scores)
            for seat, score in zip(record.seats, record.scores, strict=True):
                key = (record.game_id, seat["group"])
                entry = table.setdefault(
                    key, PlayerStats(game_id=record.game_id, group=seat["group"])
                )
                entry.played += 1
                entry.score += score
                if tied:
                    entry.draws += 1
                elif score == top:
                    entry.wins += 1
                else:
                    entry.losses += 1
        by_game: dict[str, list[PlayerStats]] = defaultdict(list)
        for entry in table.values():
            by_game[entry.game_id].append(entry)
        return [
            entry
            for game in sorted(by_game)
            for entry in sorted(by_game[game], key=lambda e: (-e.mean_score, e.group))
        ]
