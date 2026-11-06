"""Tic-Tac-Toe in NiceGUI."""

from nicegui import ui

from ludotastic.engine.render import RenderContext
from ludotastic.games.tictactoe.game import (
    LINES,
    MARKS,
    Place,
    TicTacToeState,
    winner,
)

__all__ = ["render"]

COLORS = {"X": "text-blue-500", "O": "text-rose-500"}
# Quasar fades disabled buttons; a played cell should stay as crisp as any other.
CRISP = "!opacity-100 disabled:!cursor-default"
# Quasar sizes buttons by their content; force square cells instead.
CELL_SIZE = "!p-0 !w-24 !h-24 !min-h-0 sm:!w-28 sm:!h-28"


def _winning_cells(state: TicTacToeState) -> set[int]:
    mark = winner(state.board)
    return (
        {
            cell
            for line in LINES
            if all(state.board[i] == mark for i in line)
            for cell in line
        }
        if mark
        else set()
    )


def render(ctx: RenderContext) -> None:
    """Draw the board as a grid of buttons."""
    state = ctx.match.state
    assert isinstance(state, TicTacToeState)  # noqa: S101
    seat = MARKS.index(state.next_mark)
    clickable = ctx.can_act(seat)
    highlight = _winning_cells(state)
    with ui.grid(columns=3).classes("gap-2"):
        for cell, mark in enumerate(state.board):
            button = (
                ui.button(
                    mark or "",
                    on_click=lambda _, cell=cell: ctx.submit(seat, Place(cell=cell)),
                    color=None,
                )
                .props("flat bordered" + (" disable" if mark or not clickable else ""))
                .classes(f"{CELL_SIZE} text-6xl font-bold rounded-xl {CRISP}")
                .classes(COLORS.get(mark or "", ""))
                .mark(f"cell-{cell}")
            )
            if cell in highlight:
                button.classes("bg-amber-200 dark:bg-amber-700/60")
            elif clickable and mark is None:
                button.classes("bg-gray-100 dark:bg-gray-800")
                button.classes("hover:bg-blue-100 dark:hover:bg-gray-700")
            else:
                button.classes("bg-gray-100 dark:bg-gray-800")
