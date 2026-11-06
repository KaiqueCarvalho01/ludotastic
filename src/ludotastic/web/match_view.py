"""The page that shows a match being played."""

import json
from typing import Any, override

from nicegui import ui
from pydantic import BaseModel

from ludotastic.engine.game import Game
from ludotastic.engine.match import Match, MatchStatus
from ludotastic.engine.players import HumanPlayer
from ludotastic.engine.render import RenderContext

__all__ = ["generic_renderer", "match_view"]


class _Watcher(ui.timer):
    """A timer that also unsubscribes from the match once it is gone."""

    def __init__(self, interval: float, callback: Any, unsubscribe: Any) -> None:  # noqa: ANN401
        super().__init__(interval, callback)
        self._unsubscribe = unsubscribe

    @override
    def _handle_delete(self) -> None:
        self._unsubscribe()
        super()._handle_delete()


STATUS_COLORS = {
    MatchStatus.PENDING: "grey",
    MatchStatus.RUNNING: "primary",
    MatchStatus.FINISHED: "positive",
    MatchStatus.ABORTED: "negative",
}


def generic_renderer(ctx: RenderContext) -> None:
    """Show a game without a renderer of its own: text, plus buttons for actions."""
    match = ctx.match
    game: Game[Any, Any] = match.game
    seat = min(match.thinking) if match.thinking else 0
    ui.code(game.observe(match.state, seat), language="text").classes("w-full")
    for seat in sorted(match.thinking):
        if not ctx.can_act(seat):
            continue
        ui.label(f"{game.player_label(seat)} to move:").classes("font-bold")
        with ui.row().classes("flex-wrap gap-2"):
            for action in game.legal_actions(match.state, seat):
                ui.button(
                    game.describe_action(action),
                    on_click=lambda _, seat=seat, action=action: ctx.submit(
                        seat, action
                    ),
                ).props("outline no-caps")


def _details(details: dict[str, Any]) -> str:
    return json.dumps(details, indent=2, default=str)


def match_view(match: Match) -> None:  # noqa: C901, PLR0915
    """Draw a match, and keep it up to date."""
    game: Game[Any, Any] = match.game
    renderer = game.renderer() or generic_renderer
    human_seats = frozenset(
        i for i, player in enumerate(match.players) if isinstance(player, HumanPlayer)
    )
    dirty = True

    def mark_dirty(_: Match) -> None:
        nonlocal dirty
        dirty = True

    def submit(seat: int, action: BaseModel) -> None:
        try:
            match.submit(seat, action)
        except (TypeError, ValueError) as e:
            ui.notify(str(e), type="warning")

    ctx = RenderContext(match=match, seats=human_seats, submit=submit)

    with ui.row().classes("w-full items-center"):
        ui.label(game.info.name).classes("text-2xl font-bold")
        status_badge = ui.badge()
        ui.space()
        abort = ui.button(
            "Abort", icon="stop", color="negative", on_click=match.abort
        ).props("outline")

    with ui.row().classes("w-full items-start gap-8 no-wrap max-md:flex-wrap"):
        with ui.column().classes("items-center grow"):
            banner = ui.label().classes("text-xl").mark("banner")

            @ui.refreshable
            def board() -> None:
                renderer(ctx)

            board()

        with ui.column().classes("w-96 max-md:w-full"):
            with ui.card().classes("w-full"):
                ui.label("Players").classes("text-lg font-bold")

                @ui.refreshable
                def seats() -> None:
                    for seat in match.seats:
                        with ui.row().classes("items-center gap-2"):
                            ui.badge(seat.label)
                            ui.label(seat.player)
                            ui.label(f"({seat.kind})").classes("text-gray-500")
                            if seat.seat in match.thinking:
                                ui.spinner(size="sm")
                            if match.outcome:
                                ui.label(
                                    f"{match.outcome.scores[seat.seat]:g}"
                                ).classes("font-bold")

                seats()

            with ui.card().classes("w-full"):
                ui.label("Moves").classes("text-lg font-bold")

                @ui.refreshable
                def history() -> None:
                    if not match.history:
                        ui.label("No moves yet.").classes("text-gray-500")
                    for move in reversed(match.history[-50:]):
                        title = (
                            f"{move.turn + 1}. {game.player_label(move.seat)}: "
                            f"{move.description}"
                        )
                        if move.details or move.forced:
                            with ui.expansion(title).classes("w-full").props("dense"):
                                ui.label(f"{move.seconds:.2f}s").classes(
                                    "text-gray-500"
                                )
                                if move.forced:
                                    ui.label("Forced: the player was too slow.")
                                if move.details:
                                    ui.code(_details(move.details), language="json")
                        else:
                            ui.label(title)

                history()

    def banner_text() -> str:
        if match.status is MatchStatus.ABORTED:
            return f"Aborted: {match.error}"
        if match.outcome is not None:
            winners = match.outcome.winners
            who = (
                " and ".join(game.player_label(w) for w in winners) + " won"
                if winners
                else "Draw"
            )
            return f"{who}: {match.outcome.reason}"
        if match.thinking:
            labels = ", ".join(game.player_label(s) for s in sorted(match.thinking))
            yours = any(s in human_seats for s in match.thinking)
            return f"{labels} to move" + (" (your turn)" if yours else "")
        return "..."

    def update() -> None:
        nonlocal dirty
        if not dirty:
            return
        dirty = False
        status_badge.set_text(str(match.status))
        status_badge.props(f"color={STATUS_COLORS[match.status]}")
        abort.set_visibility(not match.done)
        banner.set_text(banner_text())
        board.refresh()
        seats.refresh()
        history.refresh()

    unsubscribe = match.subscribe(mark_dirty)
    update()
    _Watcher(0.1, update, unsubscribe)
