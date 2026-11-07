"""Rock-Paper-Scissors in NiceGUI."""

__all__: tuple[str, ...] = ("render",)

from typing import Final

from nicegui import ui

from ludotastic.engine.render import RenderContext
from ludotastic.games.rock_paper_scissors.game import (
    Move,
    RockPaperScissorsState,
    Throw,
)

LABELS: Final = ("Player 1", "Player 2")


def _last_round(state: RockPaperScissorsState) -> str:
    """Describe the last round, or say that none has been played.

    Examples:
        >>> _last_round(RockPaperScissorsState())
        'No rounds have been played yet.'
        >>> _last_round(RockPaperScissorsState(last=(Move.ROCK, Move.SCISSORS)))
        'Last round: Player 1 played rock; Player 2 played scissors. Player 1 won.'
        >>> _last_round(RockPaperScissorsState(last=(Move.ROCK, Move.PAPER)))
        'Last round: Player 1 played rock; Player 2 played paper. Player 2 won.'
        >>> _last_round(RockPaperScissorsState(last=(Move.ROCK, Move.ROCK)))
        'Last round: Player 1 played rock; Player 2 played rock. It was a tie.'
    """
    first, second = state.last
    if first is None or second is None:
        return "No rounds have been played yet."
    if first.beats is second:
        result = "Player 1 won"
    elif second.beats is first:
        result = "Player 2 won"
    else:
        result = "It was a tie"
    return f"Last round: Player 1 played {first}; Player 2 played {second}. {result}."


def _seat_buttons(ctx: RenderContext, seat: int) -> None:
    """Draw the three throws for one seat, disabling them once picked."""
    buttons: list[ui.button] = []

    def play(move: Move) -> None:
        ctx.submit(seat, Throw(move=move))
        for button in buttons:
            button.disable()

    with ui.column().classes("items-center gap-2"):
        ui.label(f"{LABELS[seat]}, choose:").classes("font-bold").mark(f"turn-{seat}")
        with ui.row().classes("gap-2"):
            for move in Move:
                button = (
                    ui.button(
                        move.value.title(),
                        on_click=lambda _, move=move: play(move),
                        color=None,
                    )
                    .props("flat bordered")
                    .mark(f"move-{seat}-{move.value}")
                )
                buttons.append(button)


def render(ctx: RenderContext) -> None:
    """Draw the scoreboard, the last round, and a throw picker per human seat."""
    state = ctx.match.state
    assert isinstance(state, RockPaperScissorsState)  # noqa: S101
    with ui.column().classes("items-center gap-4"):
        with ui.row().classes("items-center gap-6 text-lg"):
            ui.label(f"Player 1: {state.wins[0]}").classes("font-mono").mark("wins-0")
            ui.label(f"Round {state.rounds + 1}").classes("font-mono").mark("round")
            ui.label(f"Player 2: {state.wins[1]}").classes("font-mono").mark("wins-1")
        ui.label(_last_round(state)).classes("text-base").mark("last-round")
        for seat in sorted(ctx.seats):
            if ctx.can_act(seat):
                _seat_buttons(ctx, seat)
