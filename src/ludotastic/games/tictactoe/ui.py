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
                .classes("w-24 h-24 text-5xl font-bold rounded-lg")
                .classes(COLORS.get(mark or "", ""))
                .mark(f"cell-{cell}")
            )
            if cell in highlight:
                button.classes("bg-yellow-200 dark:bg-yellow-800")
            else:
                button.classes("bg-gray-100 dark:bg-gray-800")
