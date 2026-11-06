"""The game abstraction every Ludotastic game implements."""

import json
import random
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping, Sequence
from enum import StrEnum
from typing import TYPE_CHECKING, Any, ClassVar, Self, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:
    from pydantic_ai import Tool

    from ludotastic.engine.players import Player
    from ludotastic.engine.render import Renderer

__all__ = [
    "ActionMode",
    "BotFactory",
    "Game",
    "GameInfo",
    "Outcome",
    "Timing",
]


class Timing(StrEnum):
    """How a game advances in time."""

    STEP = "step"
    """The game waits for every player that has to act before advancing."""

    TICK = "tick"
    """The game advances on a clock, and a player that is too slow loses its turn."""


class ActionMode(StrEnum):
    """How an AI player is asked for its action."""

    CHOICE = "choice"
    """Pick one of the legal actions, each described in words.

    Never produces an illegal action, and is the natural fit for decision models
    such as TypeSafe's Jev.
    """

    STRUCTURED = "structured"
    """Fill in the game's action model from the observation.

    Illegal actions are sent back to the model to retry.
    """

    TOOLS = "tools"
    """Inspect the game through tools, then submit the game's action model."""


class GameInfo(BaseModel):
    """Static metadata describing a game."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    """Unique, URL-safe identifier."""
    name: str
    """Human-readable name."""
    description: str
    """One-line description."""
    min_players: int = Field(default=1, ge=1)
    """Fewest players the game supports."""
    max_players: int = Field(default=1, ge=1)
    """Most players the game supports."""
    timing: Timing = Timing.STEP
    """Whether the game waits for players or runs on a clock."""
    tick_seconds: float = Field(default=1.0, gt=0)
    """Length of a tick, for games with [`Timing.TICK`][ludotastic.Timing.TICK]."""
    action_modes: tuple[ActionMode, ...] = tuple(ActionMode)
    """The ways an AI can be asked to act, the first being the default."""
    tags: tuple[str, ...] = ()
    """Free-form tags, such as `classic` or `real-time`."""

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.max_players < self.min_players:
            msg = "max_players must be at least min_players"
            raise ValueError(msg)
        if not self.action_modes:
            msg = "at least one action mode is required"
            raise ValueError(msg)
        return self


class Outcome(BaseModel):
    """The result of a finished match."""

    model_config = ConfigDict(frozen=True)

    scores: tuple[float, ...]
    """One score per player; higher is better."""
    reason: str
    """Why the match ended, in words."""

    @property
    def winners(self) -> tuple[int, ...]:
        """The players with the top score, or none if every score is equal.

        Examples:
            >>> Outcome(scores=(1, 0), reason="").winners
            (0,)
            >>> Outcome(scores=(0.5, 0.5), reason="").winners
            ()
        """
        top = max(self.scores)
        if all(score == top for score in self.scores):
            return ()
        return tuple(i for i, score in enumerate(self.scores) if score == top)

    @classmethod
    def win(cls, num_players: int, winner: int, reason: str) -> Self:
        """One player wins and everybody else loses.

        Examples:
            >>> Outcome.win(2, 1, "three in a row").scores
            (0.0, 1.0)
        """
        scores = tuple(1.0 if i == winner else 0.0 for i in range(num_players))
        return cls(scores=scores, reason=reason)

    @classmethod
    def draw(cls, num_players: int, reason: str) -> Self:
        """Every player gets the same share.

        Examples:
            >>> Outcome.draw(2, "board full").scores
            (0.5, 0.5)
        """
        return cls(scores=(1 / num_players,) * num_players, reason=reason)

    @classmethod
    def forfeit(cls, num_players: int, loser: int, reason: str) -> Self:
        """One player forfeits, and everybody else wins.

        Examples:
            >>> Outcome.forfeit(3, 0, "timeout").scores
            (0.0, 1.0, 1.0)
        """
        scores = tuple(0.0 if i == loser else 1.0 for i in range(num_players))
        return cls(scores=scores, reason=reason)


type BotFactory = Callable[[], Player]
"""Builds a scripted (non-AI) player."""


class Game[S: BaseModel, A: BaseModel](ABC):
    """A game: its rules, state transitions and how it is shown to players.

    A game is a pure state machine. States and actions are Pydantic models, so
    they can be sent over the API, stored, and handed to AI models as-is. The
    engine owns everything else: players, turn order, time, and history.

    Subclasses set [`info`][ludotastic.Game.info], `state_type`, `action_type`
    and [`rules`][ludotastic.Game.rules], and implement the abstract methods.
    Register the subclass under the `ludotastic.games` entry-point group to make
    it available.
    """

    info: ClassVar[GameInfo]
    """Static metadata about the game."""
    rules: ClassVar[str] = ""
    """The rules, in Markdown, shown to people and given to AI players."""
    state_type: ClassVar[type[BaseModel]]
    """The Pydantic model of the game's state."""
    action_type: ClassVar[type[BaseModel]]
    """The Pydantic model of one player's action."""

    def __init__(self, num_players: int | None = None) -> None:
        """Set the game up for a number of players.

        Args:
            num_players: How many players take part; defaults to the minimum.

        Raises:
            ValueError: If the game does not support that many players.
        """
        num_players = num_players or self.info.min_players
        if not self.info.min_players <= num_players <= self.info.max_players:
            msg = (
                f"{self.info.name} needs {self.info.min_players} to "
                f"{self.info.max_players} players, not {num_players}"
            )
            raise ValueError(msg)
        self.num_players = num_players

    @abstractmethod
    def initial_state(self, rng: random.Random) -> S:
        """Build the state a match starts in."""

    @abstractmethod
    def to_move(self, state: S) -> Sequence[int]:
        """The players that act next; several for simultaneous moves."""

    @abstractmethod
    def legal_actions(self, state: S, player: int) -> Sequence[A]:
        """Every action `player` may take in `state`."""

    @abstractmethod
    def apply(self, state: S, actions: Mapping[int, A], rng: random.Random) -> S:
        """Return the state after the players' actions.

        In [`Timing.TICK`][ludotastic.Timing.TICK] games, a player that did not
        act in time and has no [default action][ludotastic.Game.default_action]
        is missing from `actions`.
        """

    @abstractmethod
    def outcome(self, state: S) -> Outcome | None:
        """The outcome if the match is over, otherwise `None`."""

    @abstractmethod
    def observe(self, state: S, player: int) -> str:
        """Describe `state` in text, as `player` sees it.

        This is the prompt an AI player gets, so it should hold everything the
        player needs to decide, and nothing it should not know.
        """

    def describe_action(self, action: A) -> str:
        """Describe an action in words, for people and AI players alike."""
        return self.action_key(action)

    def action_key(self, action: A) -> str:
        """A short, unique, stable identifier for an action."""
        return json.dumps(action.model_dump(mode="json"), sort_keys=True)

    def parse_action(self, data: Any) -> A:  # noqa: ANN401
        """Validate raw data, such as JSON from the API, into an action."""
        return cast("A", self.action_type.model_validate(data))

    def is_legal(self, state: S, player: int, action: A) -> bool:
        """Whether `player` may take `action` in `state`."""
        return action in self.legal_actions(state, player)

    def default_action(self, state: S, player: int) -> A | None:  # noqa: ARG002
        """The action taken for a player that was too slow on a tick.

        Returning `None` means the player simply does not act this tick.
        """
        return None

    def player_label(self, player: int) -> str:
        """A short name for a seat, such as `X` or `Black`."""
        return f"Player {player + 1}"

    def bots(self) -> Mapping[str, BotFactory]:
        """Scripted players specific to this game, by name.

        The engine always adds a `random` bot on top of these.
        """
        bots: dict[str, BotFactory] = {}
        return bots

    def ai_tools(self, state: S, player: int) -> Sequence[Tool[Any]]:  # noqa: ARG002
        """Extra tools offered to AI players in the `tools` action mode.

        The engine already offers tools to observe the game and list the legal
        actions.
        """
        return ()

    def renderer(self) -> Renderer | None:
        """The NiceGUI renderer for this game, if it has one.

        Import NiceGUI code lazily in here, so the game logic stays usable
        without loading the UI. Games without a renderer get a generic,
        text-based view.
        """
        return None
