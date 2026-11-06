"""Running matches for the UI, the API and the CLI."""

from collections.abc import Sequence
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from ludotastic.engine.ai import AIPlayer
from ludotastic.engine.game import ActionMode, Game
from ludotastic.engine.match import Match
from ludotastic.engine.players import HumanPlayer, Player, PlayerKind, RandomBot
from ludotastic.engine.registry import GameRegistry, registry
from ludotastic.settings import Settings, get_settings
from ludotastic.storage import Store

__all__ = [
    "AISpec",
    "BotSpec",
    "HumanSpec",
    "MatchService",
    "PlayerSpec",
    "bot_names",
]


class HumanSpec(BaseModel):
    """A person at the keyboard."""

    kind: Literal[PlayerKind.HUMAN] = PlayerKind.HUMAN
    name: str = "Human"


class BotSpec(BaseModel):
    """A scripted player."""

    kind: Literal[PlayerKind.BOT] = PlayerKind.BOT
    bot: str = "random"
    """The bot's name, from [`bot_names`][ludotastic.service.bot_names]."""


class AISpec(BaseModel):
    """An AI model."""

    kind: Literal[PlayerKind.AI] = PlayerKind.AI
    model: str
    """Any Pydantic AI model name, such as `typesafe:jev-latest`."""
    mode: ActionMode | None = None
    """How to ask for actions; defaults to the game's preferred mode."""
    name: str | None = None
    instructions: str | None = None
    fallback_model: str | None = None
    """A model behind the main one, such as a language model behind Jev."""


type PlayerSpec = Annotated[HumanSpec | BotSpec | AISpec, Field(discriminator="kind")]


def bot_names(game: Game[Any, Any]) -> list[str]:
    """The bots available for a game."""
    return ["random", *game.bots()]


def build_player(game: Game[Any, Any], spec: HumanSpec | BotSpec | AISpec) -> Player:
    """Turn a spec into a player.

    Raises:
        ValueError: If the bot or action mode is unknown for this game.
    """
    match spec:
        case HumanSpec():
            return HumanPlayer(spec.name)
        case BotSpec(bot="random"):
            return RandomBot()
        case BotSpec():
            factory = game.bots().get(spec.bot)
            if factory is None:
                msg = f"{game.info.name} has no bot {spec.bot!r}"
                raise ValueError(msg)
            return factory()
        case _:
            if spec.mode is not None and spec.mode not in game.info.action_modes:
                msg = f"{game.info.name} does not support the {spec.mode} mode"
                raise ValueError(msg)
            return AIPlayer(
                spec.model,
                mode=spec.mode,
                name=spec.name,
                instructions=spec.instructions,
                fallback_model=spec.fallback_model,
            )


class MatchService:
    """Creates matches, keeps the live ones, and saves them when they end."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        games: GameRegistry | None = None,
        store: Store | None = None,
    ) -> None:
        """Wire the service up; defaults come from the settings."""
        self.settings = settings or get_settings()
        self.games = games if games is not None else registry
        self.store = store or Store(self.settings.resolved_database_url)
        self.matches: dict[str, Match] = {}

    def create(
        self,
        game_id: str,
        players: Sequence[HumanSpec | BotSpec | AISpec],
        *,
        seed: int | None = None,
        start: bool = True,
    ) -> Match:
        """Set a match up and, by default, start it.

        Raises:
            KeyError: If the game is unknown.
        """
        game = self.games[game_id](len(players))
        seated = [build_player(game, spec) for spec in players]
        has_human = any(isinstance(p, HumanPlayer) for p in seated)
        match = Match(
            game,
            seated,
            seed=seed,
            turn_timeout=self.settings.turn_timeout,
            max_turns=self.settings.max_turns,
            delay=0.0 if has_human else self.settings.ai_delay,
        )
        self.matches[match.id] = match
        match.subscribe(self._on_change)
        if start:
            match.start()
        return match

    def _on_change(self, match: Match) -> None:
        if match.done:
            self.store.save(match)

    def get(self, match_id: str) -> Match | None:
        """A live match by id."""
        return self.matches.get(match_id)

    def live(self) -> list[Match]:
        """Matches still being played, newest first."""
        return sorted(
            (m for m in self.matches.values() if not m.done),
            key=lambda m: m.created_at,
            reverse=True,
        )

    def forget_finished(self) -> None:
        """Drop finished matches from memory; they stay in the store."""
        self.matches = {k: m for k, m in self.matches.items() if not m.done}

    def shutdown(self) -> None:
        """Abort every live match."""
        for match in self.live():
            match.abort("Server shutting down")

    def close(self) -> None:
        """Abort every live match, and close the store."""
        self.shutdown()
        self.store.close()
