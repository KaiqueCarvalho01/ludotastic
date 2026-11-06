"""The game engine: games, players, matches and the plugin registry."""

__all__: tuple[str, ...] = (
    "ENTRY_POINT_GROUP",
    "AIPlayer",
    "ActionMode",
    "Decision",
    "Game",
    "GameInfo",
    "GameRegistry",
    "HumanPlayer",
    "Match",
    "MatchStatus",
    "MoveRecord",
    "Outcome",
    "Player",
    "PlayerKind",
    "RandomBot",
    "RenderContext",
    "Renderer",
    "SeatInfo",
    "Timing",
    "TurnContext",
    "View",
    "registry",
)

from .ai import AIPlayer
from .game import ActionMode, Game, GameInfo, Outcome, Timing, View
from .match import Match, MatchStatus, MoveRecord, SeatInfo
from .players import Decision, HumanPlayer, Player, PlayerKind, RandomBot, TurnContext
from .registry import ENTRY_POINT_GROUP, GameRegistry, registry
from .render import RenderContext, Renderer
