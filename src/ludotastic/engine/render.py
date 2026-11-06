"""The interface between games and the UI."""

__all__: tuple[str, ...] = (
    "RenderContext",
    "Renderer",
)

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from pydantic import BaseModel

if TYPE_CHECKING:
    from ludotastic.engine.match import Match


@dataclass(frozen=True, kw_only=True)
class RenderContext:
    """What a renderer gets to draw a match."""

    match: Match
    """The match to draw; read `match.state`, `match.game`, and so on."""
    seats: frozenset[int]
    """The human seats this viewer controls, if any."""
    submit: Callable[[int, BaseModel], None]
    """Hand in an action for one of `seats`."""

    def can_act(self, seat: int) -> bool:
        """Whether this viewer may act for `seat` right now."""
        return seat in self.seats and seat in self.match.thinking


class Renderer(Protocol):
    """Draws a game in NiceGUI.

    Called inside a NiceGUI container, and again every time the match changes.
    Use `ui.*` elements freely. For real-time games, also bind keys with
    `ui.keyboard` and submit actions through `ctx.submit`.
    """

    def __call__(self, ctx: RenderContext) -> Any:  # noqa: ANN401
        """Draw the match."""
        ...
