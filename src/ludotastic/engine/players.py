"""Players: whoever, or whatever, chooses the actions."""

__all__: tuple[str, ...] = (
    "Decision",
    "HumanPlayer",
    "Player",
    "PlayerKind",
    "RandomBot",
    "TurnContext",
)

import asyncio
import random
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, override

from pydantic import BaseModel

from ludotastic.engine.game import Game
from ludotastic.engine.usage import Usage
from ludotastic.types import Count, Seat


class PlayerKind(StrEnum):
    """The broad kind of a player."""

    HUMAN = "human"
    BOT = "bot"
    AI = "ai"


@dataclass(frozen=True, kw_only=True)
class TurnContext:
    """Everything a player gets when asked to act."""

    game: Game[Any, Any]
    """The game being played."""
    state: BaseModel
    """The current state."""
    player: Seat
    """The seat that has to act."""
    legal_actions: Sequence[BaseModel]
    """Every action the seat may take."""
    turn: Count
    """The number of turns played so far."""
    rng: random.Random
    """A random source, seeded per match for reproducible bots."""

    @property
    def observation(self) -> str:
        """The state as this seat sees it."""
        return self.game.observe(self.state, self.player)


@dataclass(frozen=True, kw_only=True)
class Decision:
    """An action, plus whatever the player wants to report about it."""

    action: BaseModel
    """The chosen action."""
    details: dict[str, Any] = field(default_factory=dict)
    """JSON-serializable details, such as the model or its confidence."""
    usage: Usage | None = None
    """What deciding cost, for players that use a model."""


class Player(ABC):
    """Somebody, or something, that chooses actions."""

    kind: PlayerKind
    """The kind of player."""

    def __init__(self, name: str) -> None:
        """Name the player."""
        self.name = name

    @property
    def label(self) -> str:
        """A stable label grouping comparable players, for statistics."""
        return f"{self.kind}:{self.name}"

    @abstractmethod
    async def act(self, ctx: TurnContext) -> Decision:
        """Choose an action."""

    def cancel(self) -> None:  # noqa: B027
        """Stop waiting for an action; called when a turn times out or a match ends."""


class HumanPlayer(Player):
    """A person, acting through the UI or the API."""

    kind = PlayerKind.HUMAN

    def __init__(self, name: str = "Human") -> None:
        """Name the player."""
        super().__init__(name)
        self._pending: BaseModel | None = None
        self._future: asyncio.Future[BaseModel] | None = None

    @property
    def waiting(self) -> bool:
        """Whether the player is being asked to act right now."""
        return self._future is not None and not self._future.done()

    def submit(self, action: BaseModel) -> None:
        """Hand in an action.

        Submitted before the player is asked, the action is kept for the next
        turn, which is how real-time games take key presses between ticks.
        """
        if self._future is not None and not self._future.done():
            self._future.set_result(action)
        else:
            self._pending = action

    @override
    async def act(self, ctx: TurnContext) -> Decision:
        """Wait for an action to be submitted."""
        if self._pending is not None:
            action, self._pending = self._pending, None
            return Decision(action=action)
        self._future = asyncio.get_running_loop().create_future()
        try:
            return Decision(action=await self._future)
        finally:
            self._future = None

    @override
    def cancel(self) -> None:
        """Stop waiting, and drop any action handed in early."""
        self._pending = None
        self.timeout()

    def timeout(self) -> None:
        """Stop waiting for this turn, but keep any action handed in early.

        Real-time games call this when a tick ends: a key pressed in between
        ticks still counts for the next one.
        """
        if self._future is not None and not self._future.done():
            self._future.cancel()


class RandomBot(Player):
    """Picks any legal action, uniformly at random."""

    kind = PlayerKind.BOT

    def __init__(self, name: str = "random") -> None:
        """Name the player."""
        super().__init__(name)

    @override
    async def act(self, ctx: TurnContext) -> Decision:
        """Pick a random legal action."""
        return Decision(action=ctx.rng.choice(ctx.legal_actions))
