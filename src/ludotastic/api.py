"""The REST API."""

from typing import Annotated, Any, cast

from annotated_types import MinLen
from fastapi import APIRouter, Body, Depends, FastAPI, HTTPException, Request, status
from pydantic import BaseModel

from ludotastic.engine.game import Game, GameInfo
from ludotastic.engine.match import Match, MatchStatus, MoveRecord, SeatInfo
from ludotastic.service import MatchService, PlayerSpec, bot_names
from ludotastic.storage import MatchRecord, PlayerStats

__all__ = ["create_router"]


class GameDetails(BaseModel):
    """A game, as the API describes it."""

    info: GameInfo
    rules: str
    bots: list[str]
    state_schema: dict[str, Any]
    action_schema: dict[str, Any]


class NewMatch(BaseModel):
    """What it takes to start a match."""

    game_id: str
    players: Annotated[list[PlayerSpec], MinLen(1)]
    seed: int | None = None


class MatchView(BaseModel):
    """A live match."""

    id: str
    game_id: str
    status: MatchStatus
    seed: int
    turn: int
    seats: list[SeatInfo]
    to_move: list[int]
    """Seats being waited on right now."""
    state: dict[str, Any]
    legal_actions: dict[int, list[dict[str, Any]]]
    """Legal actions for every seat being waited on."""
    history: list[MoveRecord]
    scores: list[float] | None
    reason: str | None

    @classmethod
    def of(cls, match: Match) -> MatchView:
        """Describe a match."""
        game: Game[Any, Any] = match.game
        thinking = sorted(match.thinking)
        return cls(
            id=match.id,
            game_id=game.info.id,
            status=match.status,
            seed=match.seed,
            turn=match.turn,
            seats=match.seats,
            to_move=thinking,
            state=match.state.model_dump(mode="json"),
            legal_actions={
                seat: [
                    a.model_dump(mode="json")
                    for a in game.legal_actions(match.state, seat)
                ]
                for seat in thinking
            },
            history=match.history,
            scores=list(match.outcome.scores) if match.outcome else None,
            reason=match.outcome.reason if match.outcome else match.error,
        )


def _service(request: Request) -> MatchService:
    return cast("MatchService", request.app.state.service)


type Service = Annotated[MatchService, Depends(_service)]


def _live(service: MatchService, match_id: str) -> Match:
    match = service.get(match_id)
    if match is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No live match with that id")
    return match


def create_router() -> APIRouter:  # noqa: C901
    """Build the API routes; they expect `app.state.service` to be set."""
    router = APIRouter(prefix="/api", tags=["ludotastic"])

    @router.get("/games")
    def list_games(service: Service) -> list[GameInfo]:
        """Every installed game."""
        return [service.games[game_id].info for game_id in service.games]

    @router.get("/games/{game_id}")
    def get_game(service: Service, game_id: str) -> GameDetails:
        """One game in detail, including the JSON schemas of its state and actions."""
        try:
            game_type = service.games[game_id]
        except KeyError:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown game") from None
        game = game_type()
        return GameDetails(
            info=game.info,
            rules=game.rules,
            bots=bot_names(game),
            state_schema=game.state_type.model_json_schema(),
            action_schema=game.action_type.model_json_schema(),
        )

    @router.post("/matches", status_code=status.HTTP_201_CREATED)
    async def create_match(service: Service, body: NewMatch) -> MatchView:
        """Start a match; it runs in the background."""
        try:
            match = service.create(body.game_id, body.players, seed=body.seed)
        except KeyError:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown game") from None
        except ValueError as e:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from None
        return MatchView.of(match)

    @router.get("/matches")
    async def list_live_matches(service: Service) -> list[MatchView]:
        """Matches being played right now."""
        return [MatchView.of(m) for m in service.live()]

    @router.get("/matches/{match_id}")
    async def get_match(service: Service, match_id: str) -> MatchView:
        """A live match."""
        return MatchView.of(_live(service, match_id))

    @router.post("/matches/{match_id}/seats/{seat}/action")
    async def submit_action(
        service: Service,
        match_id: str,
        seat: int,
        action: Annotated[dict[str, Any], Body()],
    ) -> MatchView:
        """Act for a human seat."""
        match = _live(service, match_id)
        if not 0 <= seat < len(match.players):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No such seat")
        try:
            match.submit(seat, action)
        except TypeError as e:
            raise HTTPException(status.HTTP_403_FORBIDDEN, str(e)) from None
        except ValueError as e:
            raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from None
        return MatchView.of(match)

    @router.delete("/matches/{match_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def abort_match(service: Service, match_id: str) -> None:
        """Abort a live match."""
        _live(service, match_id).abort("Aborted through the API")

    @router.get("/history")
    def history(
        service: Service, game_id: str | None = None, limit: int = 50
    ) -> list[MatchRecord]:
        """Recent matches, newest first."""
        return service.store.recent(game_id=game_id, limit=limit)

    @router.get("/history/{match_id}")
    def history_match(service: Service, match_id: str) -> MatchRecord:
        """A stored match, with its full move history."""
        record = service.store.get(match_id)
        if record is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, "No stored match with that id"
            )
        return record

    @router.get("/stats")
    def stats(service: Service, game_id: str | None = None) -> list[PlayerStats]:
        """Results per game and player group."""
        return service.store.stats(game_id=game_id)

    return router


def mount_api(app: FastAPI, service: MatchService) -> None:
    """Add the API to an app."""
    app.state.service = service
    app.include_router(create_router())
