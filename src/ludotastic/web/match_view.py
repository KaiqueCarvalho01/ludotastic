"""The page that shows a match being played."""

import json
from typing import Any, override

from nicegui import ui
from pydantic import BaseModel

from ludotastic.engine.game import Game
from ludotastic.engine.match import Match, MatchStatus, MoveRecord
from ludotastic.engine.players import HumanPlayer
from ludotastic.engine.render import RenderContext
from ludotastic.engine.usage import Usage, format_cost, format_tokens

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


def _usage_line(usage: Usage) -> ui.row:
    """A compact meter: cost, tokens and requests."""
    cost = format_cost(usage.cost, priced=usage.priced)
    with ui.row().classes("items-center gap-3 text-xs text-gray-500") as row:
        with ui.row().classes("items-center gap-1 no-wrap"):
            ui.icon("payments", size="xs")
            ui.label(cost).classes("font-mono").mark("cost")
        with ui.row().classes("items-center gap-1 no-wrap"):
            ui.icon("token", size="xs")
            ui.label(format_tokens(usage.tokens)).classes("font-mono").tooltip(
                f"{usage.input_tokens:,} in, {usage.output_tokens:,} out"
            )
        with ui.row().classes("items-center gap-1 no-wrap"):
            ui.icon("sync_alt", size="xs")
            ui.label(f"{usage.requests:,}").classes("font-mono").tooltip("Requests")
    if usage.cost is None and usage.requests:
        row.tooltip("No price is known for this model.")
    return row


def _details(details: dict[str, Any]) -> str:
    return json.dumps(details, indent=2, default=str)


def _move_row(game: Game[Any, Any], move: MoveRecord) -> None:
    """One line of the move list, expandable when there is more to show."""
    title = f"{move.turn + 1}. {game.player_label(move.seat)}: {move.description}"
    confidence = move.details.get("confidence", {}).get("response")
    if not move.details and not move.forced and move.usage is None:
        ui.label(title).classes("w-full py-1 px-4 text-sm")
        return
    with ui.expansion().classes("w-full").props("dense") as expansion:
        with (
            expansion.add_slot("header"),
            ui.row().classes("w-full items-center gap-2 no-wrap py-1"),
        ):
            ui.label(title).classes("grow text-sm")
            if move.details.get("forced") or move.forced:
                ui.badge("forced", color="grey").props("outline")
            elif confidence is not None:
                ui.badge(f"{confidence:.0%}", color="grey").props("outline").tooltip(
                    "How sure the model was"
                )
        ui.label(f"{move.seconds:.2f}s").classes("text-xs text-gray-500")
        if move.forced:
            ui.label("Forced: the player was too slow.").classes("text-sm")
        elif move.details.get("forced"):
            ui.label("Forced: the only legal move.").classes("text-sm")
        if move.usage is not None:
            _usage_line(move.usage)
        if move.details:
            ui.code(_details(move.details), language="json").classes("w-full text-xs")


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

    with ui.element("div").classes(
        "w-full grid gap-6 grid-cols-1 lg:grid-cols-[minmax(0,1fr)_28rem] items-start"
    ):
        with ui.column().classes("items-center gap-4 min-w-0"):
            banner_card = ui.card().classes("w-full max-w-2xl").props("flat bordered")
            with banner_card:
                banner = (
                    ui.label()
                    .classes("w-full text-lg text-center break-words")
                    .mark("banner")
                )

            @ui.refreshable
            def board() -> None:
                renderer(ctx)

            board()

        with ui.column().classes("w-full gap-4 min-w-0"):
            with ui.card().classes("w-full"):
                ui.label("Players").classes("text-lg font-bold")

                @ui.refreshable
                def seats() -> None:
                    for seat in match.seats:
                        with ui.row().classes("w-full items-center gap-2 no-wrap"):
                            ui.badge(seat.label).classes("text-sm")
                            with ui.column().classes("gap-0 min-w-0 grow"):
                                ui.label(seat.player).classes("break-all font-medium")
                                ui.label(seat.kind).classes("text-xs text-gray-500")
                            # Bots answer instantly: a spinner would only flicker.
                            if seat.seat in match.thinking and seat.kind != "bot":
                                ui.spinner(size="sm")
                            if match.outcome:
                                ui.label(
                                    f"{match.outcome.scores[seat.seat]:g}"
                                ).classes("text-lg font-bold")
                        if seat.kind == "ai":
                            _usage_line(match.usage(seat.seat)).classes("pl-9")
                    ai_seats = sum(seat.kind == "ai" for seat in match.seats)
                    if ai_seats > 1:
                        ui.separator()
                        with ui.row().classes("w-full items-center gap-2"):
                            ui.label("Total").classes("text-sm font-medium")
                            _usage_line(match.usage())

                seats()

            with ui.card().classes("w-full p-0"):
                moves_card = (
                    ui.expansion("Moves", icon="list", caption="0 moves")
                    .classes("w-full")
                    .props("header-class='text-lg font-bold'")
                    .mark("moves")
                )
            shown = 0

            @ui.refreshable
            def history() -> None:
                nonlocal shown
                shown = len(match.history)
                if not moves_card.value:
                    return  # Only built while open: cheap during fast games.
                if not match.history:
                    ui.label("No moves yet.").classes("text-gray-500 px-4 pb-2")
                    return
                # A fixed-height scroll box, so the page does not grow as moves
                # arrive.
                with ui.scroll_area().classes("w-full h-96"):
                    for move in reversed(match.history[-50:]):
                        _move_row(game, move)

            with moves_card:
                history()
            moves_card.on_value_change(history.refresh)

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
        failed = match.status is MatchStatus.ABORTED or (
            match.outcome is not None and "failed" in match.outcome.reason
        )
        banner_card.classes(
            add="border-red-500" if failed else "",
            remove="" if failed else "border-red-500",
        )
        board.refresh()
        seats.refresh()
        count = len(match.history)
        moves_card.props(f"caption='{count} move{'' if count == 1 else 's'}'")
        if moves_card.value and count != shown:
            history.refresh()

    unsubscribe = match.subscribe(mark_dirty)
    update()
    _Watcher(0.1, update, unsubscribe)
