"""Matches: a game, its players, and the loop that runs them."""

__all__: tuple[str, ...] = (
    "Match",
    "MatchStatus",
    "MoveRecord",
    "SeatInfo",
)

import asyncio
import contextlib
import random
import uuid
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from ludotastic.engine.game import Game, Outcome, Timing
from ludotastic.engine.players import Decision, HumanPlayer, Player, TurnContext
from ludotastic.engine.usage import Usage
from ludotastic.types import Count, NonNegativeFloat, Seat


class MatchStatus(StrEnum):
    """Where a match is in its life."""

    PENDING = "pending"
    RUNNING = "running"
    FINISHED = "finished"
    ABORTED = "aborted"


class SeatInfo(BaseModel):
    """Who sits in a seat."""

    seat: Seat
    label: str
    """The game's name for the seat, such as `X`."""
    player: str
    """The player's display name."""
    kind: str
    """`human`, `bot` or `ai`."""
    group: str
    """The player's statistics label."""


class MoveRecord(BaseModel):
    """One action in a match's history."""

    turn: Count
    seat: Seat
    action: dict[str, Any]
    description: str
    seconds: NonNegativeFloat
    """How long the player took."""
    details: dict[str, Any] = Field(default_factory=dict)
    """Whatever the player reported, such as model usage."""
    forced: bool = False
    """Whether the engine chose this action, because the player was too slow."""
    usage: Usage | None = None
    """What the move cost, for players that use a model."""


type Listener = Callable[[Match], Awaitable[None] | None]


class Match:
    """A game being played by a set of players.

    Create one, then [`run`][ludotastic.Match.run] it as a task. Watch it with
    [`subscribe`][ludotastic.Match.subscribe].
    """

    def __init__(  # noqa: PLR0913
        self,
        game: Game[Any, Any],
        players: Sequence[Player],
        *,
        seed: int | None = None,
        turn_timeout: float | None = None,
        max_turns: int | None = None,
        delay: float = 0.0,
    ) -> None:
        """Seat the players.

        Args:
            game: The game to play.
            players: One player per seat, in seat order.
            seed: Seed for the match's randomness; random when not given.
            turn_timeout: For step-based games, how long a player may think
                before forfeiting the match; `None` waits forever.
            max_turns: End the match as a draw after this many turns.
            delay: Pause between turns, so people can follow along.

        Raises:
            ValueError: If the number of players does not fit the game.
        """
        if len(players) != game.num_players:
            msg = f"{game.info.name} is set up for {game.num_players} players"
            raise ValueError(msg)
        self.id = uuid.uuid4().hex
        self.game = game
        self.players = list(players)
        self.seed = seed if seed is not None else random.SystemRandom().getrandbits(32)
        self.rng = random.Random(self.seed)
        self.turn_timeout = turn_timeout
        self.max_turns = max_turns
        self.delay = delay
        self.state: BaseModel = game.initial_state(self.rng)
        self.history: list[MoveRecord] = []
        self.status = MatchStatus.PENDING
        self.outcome: Outcome | None = None
        self.error: str | None = None
        self.thinking: set[int] = set()
        self.created_at = datetime.now(UTC)
        self.finished_at: datetime | None = None
        self._listeners: list[Listener] = []
        self._turns = 0

    @property
    def turn(self) -> int:
        """The number of turns played so far."""
        return self._turns

    @property
    def seats(self) -> list[SeatInfo]:
        """Who sits where."""
        return [
            SeatInfo(
                seat=i,
                label=self.game.player_label(i),
                player=p.name,
                kind=str(p.kind),
                group=p.label,
            )
            for i, p in enumerate(self.players)
        ]

    def usage(self, seat: int | None = None) -> Usage:
        """Model usage so far, for one seat or the whole match."""
        return Usage.total(
            move.usage
            for move in self.history
            if move.usage is not None and (seat is None or move.seat == seat)
        )

    @property
    def done(self) -> bool:
        """Whether the match is over, one way or another."""
        return self.status in {MatchStatus.FINISHED, MatchStatus.ABORTED}

    def subscribe(self, listener: Listener) -> Callable[[], None]:
        """Call `listener` whenever the match changes; returns an unsubscriber."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    async def _notify(self) -> None:
        for listener in list(self._listeners):
            try:
                result = listener(self)
                if isinstance(result, Awaitable):
                    await result
            except Exception:  # noqa: BLE001 - one broken viewer must not stop the match
                logger.exception("Match listener failed")

    def submit(self, seat: int, action: BaseModel | dict[str, Any]) -> None:
        """Hand in an action for a human seat.

        Raises:
            TypeError: If the seat is not a human player.
            ValueError: If a step-based game is not waiting on that seat, or the
                action is illegal.
        """
        player = self.players[seat]
        if not isinstance(player, HumanPlayer):
            msg = f"Seat {seat} is not played by a human"
            raise TypeError(msg)
        if not isinstance(action, BaseModel):
            action = self.game.parse_action(action)
        if self.game.info.timing is Timing.STEP:
            if seat not in self.thinking:
                msg = f"It is not seat {seat}'s turn"
                raise ValueError(msg)
            if not self.game.is_legal(self.state, seat, action):
                msg = "Illegal action"
                raise ValueError(msg)
        player.submit(action)

    def abort(self, reason: str = "Aborted") -> None:
        """Stop the match without an outcome."""
        if self.done:
            return
        self.status = MatchStatus.ABORTED
        self.error = reason
        self.finished_at = datetime.now(UTC)
        for player in self.players:
            player.cancel()
        if self._task is not None:
            self._task.cancel()

    _task: asyncio.Task[Outcome | None] | None = None

    def start(self) -> asyncio.Task[Outcome | None]:
        """Run the match in the background."""
        task = self._task
        if task is None:
            task = self._task = asyncio.create_task(self.run(), name=f"match-{self.id}")
        return task

    async def run(self) -> Outcome | None:
        """Play the match to the end."""
        self.status = MatchStatus.RUNNING
        await self._notify()
        try:
            while (outcome := self.game.outcome(self.state)) is None:
                if self.max_turns is not None and self.turn >= self.max_turns:
                    outcome = self.game.out_of_turns(self.state)
                    break
                forfeit = await self._play_turn()
                if forfeit is not None:
                    outcome = forfeit
                    break
                await self._notify()
                if self.delay:
                    await asyncio.sleep(self.delay)
        except asyncio.CancelledError:
            # `abort()` may have already set the status and reason.
            self.status = MatchStatus.ABORTED
            self.error = self.error or "Cancelled"
            self.finished_at = self.finished_at or datetime.now(UTC)
            await self._notify()
            return None
        except Exception as e:  # noqa: BLE001 - record any failure on the match
            logger.exception("Match {} failed", self.id)
            self.status = MatchStatus.ABORTED
            self.error = f"{type(e).__name__}: {e}"
            self.finished_at = datetime.now(UTC)
            await self._notify()
            return None
        finally:
            self.thinking.clear()
            for player in self.players:
                player.cancel()
        self.outcome = outcome
        self.status = MatchStatus.FINISHED
        self.finished_at = datetime.now(UTC)
        await self._notify()
        return outcome

    async def _play_turn(self) -> Outcome | None:
        """Ask every seat to move, then advance the game; returns a forfeit, if any."""
        game = self.game
        seats = list(game.to_move(self.state))
        ticking = game.info.timing is Timing.TICK
        timeout = game.info.tick_seconds if ticking else self.turn_timeout
        decisions = await self._ask(seats, timeout, ticking=ticking)

        actions: dict[int, BaseModel] = {}
        for seat in seats:
            result = decisions.get(seat)
            label = game.player_label(seat)
            if isinstance(result, BaseException):
                logger.warning(
                    "Seat {} failed in match {}: {!r}", seat, self.id, result
                )
                reason = f"{label} failed: {type(result).__name__}: {result}"
                return Outcome.forfeit(game.num_players, seat, reason)
            if result is not None:
                decision, seconds = result
                if not game.is_legal(self.state, seat, decision.action):
                    reason = f"{label} made an illegal move"
                    return Outcome.forfeit(game.num_players, seat, reason)
                actions[seat] = decision.action
                self._record(
                    seat, decision.action, seconds, decision.details, decision.usage
                )
            elif not ticking:
                return Outcome.forfeit(
                    game.num_players, seat, f"{label} ran out of time"
                )
            elif (default := game.default_action(self.state, seat)) is not None:
                actions[seat] = default
                self._record(seat, default, timeout or 0.0, {}, forced=True)
        self.state = game.apply(self.state, actions, self.rng)
        self._turns += 1
        return None

    async def _ask(
        self, seats: list[int], deadline: float | None, *, ticking: bool = False
    ) -> dict[int, tuple[Decision, float] | BaseException]:
        """Ask seats to act, at once; slow seats are left out of the result.

        On a tick, only people are held to `deadline`, and not on the first
        tick: bots and AI players are always waited for. With a person
        playing, the tick lasts at least `deadline`.
        """
        contexts = {
            seat: TurnContext(
                game=self.game,
                state=self.state,
                player=seat,
                legal_actions=list(self.game.legal_actions(self.state, seat)),
                turn=self.turn,
                rng=random.Random(self.rng.getrandbits(64)),
            )
            for seat in seats
        }
        self.thinking = set(seats)
        await self._notify()
        loop = asyncio.get_running_loop()
        started = loop.time()

        async def ask(seat: int) -> tuple[Decision, float]:
            decision = await self.players[seat].act(contexts[seat])
            return decision, loop.time() - started

        tasks = {seat: asyncio.create_task(ask(seat)) for seat in seats}
        # A real-time game waits for each person's first move, so nobody loses
        # before they have even seen the board.
        first = self.turn == 0
        clocked = {
            seat: task
            for seat, task in tasks.items()
            if not ticking
            or (isinstance(self.players[seat], HumanPlayer) and not first)
        }
        unclocked = [t for t in tasks.values() if t not in clocked.values()]
        if clocked:
            await asyncio.wait(clocked.values(), timeout=deadline)
        if unclocked:
            await asyncio.wait(unclocked)
        if ticking and deadline is not None and clocked:
            # With a person playing, a tick never ends early: a steady pace.
            await asyncio.sleep(max(0.0, started + deadline - loop.time()))
        pending = {task for task in tasks.values() if not task.done()}
        for seat, task in tasks.items():
            if task in pending:
                player = self.players[seat]
                if isinstance(player, HumanPlayer):
                    player.timeout()
                else:  # pragma: no cover - only people are left pending
                    player.cancel()
                task.cancel()
        for task in pending:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self.thinking.clear()
        return {
            seat: task.exception() or task.result()
            for seat, task in tasks.items()
            if task not in pending
        }

    def _record(  # noqa: PLR0913
        self,
        seat: int,
        action: BaseModel,
        seconds: float,
        details: dict[str, Any],
        usage: Usage | None = None,
        *,
        forced: bool = False,
    ) -> None:
        self.history.append(
            MoveRecord(
                turn=self.turn,
                seat=seat,
                action=action.model_dump(mode="json"),
                description=self.game.describe_action(action),
                seconds=round(seconds, 3),
                details=details,
                forced=forced,
                usage=usage,
            )
        )
