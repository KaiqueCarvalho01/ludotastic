"""Tic-Tac-Toe rules."""

__all__: tuple[str, ...] = (
    "Mark",
    "MinimaxBot",
    "Place",
    "TicTacToe",
    "TicTacToeState",
)

import random
from collections.abc import Mapping, Sequence
from functools import cache
from typing import TYPE_CHECKING, Annotated, Final, Literal, override

from annotated_types import Interval
from pydantic import BaseModel, ConfigDict

from ludotastic.engine.drawing import Canvas
from ludotastic.engine.game import ActionMode, BotFactory, Game, GameInfo, Outcome
from ludotastic.engine.players import Decision, Player, PlayerKind, TurnContext

if TYPE_CHECKING:
    from ludotastic.engine.render import Renderer

type Mark = Literal["X", "O"]
type Cell = Mark | None
type Board = tuple[Cell, Cell, Cell, Cell, Cell, Cell, Cell, Cell, Cell]

MARKS: Final[tuple[Mark, Mark]] = ("X", "O")
LINES: Final = (
    (0, 1, 2),
    (3, 4, 5),
    (6, 7, 8),
    (0, 3, 6),
    (1, 4, 7),
    (2, 5, 8),
    (0, 4, 8),
    (2, 4, 6),
)
ROWS: Final = ("top", "middle", "bottom")
COLUMNS: Final = ("left", "center", "right")


class TicTacToeState(BaseModel):
    """The board, read left to right and top to bottom."""

    model_config = ConfigDict(frozen=True)

    board: Board = (None, None, None, None, None, None, None, None, None)
    """Cells 0 to 8: 0 is top left, 4 the center, 8 bottom right."""

    @property
    def next_mark(self) -> Mark:
        """Whose turn it is; X always starts."""
        return "X" if self.board.count("X") == self.board.count("O") else "O"


class Place(BaseModel):
    """Place your mark in an empty cell."""

    model_config = ConfigDict(frozen=True, use_attribute_docstrings=True)

    cell: Annotated[int, Interval(ge=0, le=8)]
    """The cell to mark: 0 is top left, 1 top center, 2 top right, 3 middle left,
    4 center, 5 middle right, 6 bottom left, 7 bottom center, 8 bottom right."""


def cell_name(cell: int) -> str:
    """Name a cell in words.

    Examples:
        >>> cell_name(0), cell_name(4), cell_name(7)
        ('top left', 'center', 'bottom center')
    """
    row, column = ROWS[cell // 3], COLUMNS[cell % 3]
    if row == "middle" and column == "center":
        return "center"
    return f"{row} {column}"


def winner(board: Board) -> Mark | None:
    """The mark with three in a row, if any.

    Examples:
        >>> winner(("X", "X", "X", None, "O", "O", None, None, None))
        'X'
    """
    for a, b, c in LINES:
        if board[a] is not None and board[a] == board[b] == board[c]:
            return board[a]
    return None


def render_board(board: Board) -> str:
    """Draw the board in text, numbering the empty cells.

    Examples:
        >>> print(render_board(("X", None, None, None, "O", None, None, None, None)))
         X | 1 | 2
        ---+---+---
         3 | O | 5
        ---+---+---
         6 | 7 | 8
    """
    cells = [mark or str(i) for i, mark in enumerate(board)]
    rows = [" " + " | ".join(cells[r * 3 : r * 3 + 3]) for r in range(3)]
    return "\n---+---+---\n".join(rows)


PICTURE: Final = 420
"""Side of the board picture, in pixels."""


def draw_board(board: Board) -> bytes:
    """Draw the board as a PNG, the way it looks in the playground.

    Examples:
        >>> draw_board((None,) * 9)[1:4]
        b'PNG'
    """
    canvas = Canvas(PICTURE, PICTURE)
    cell = PICTURE / 3
    for i in (1, 2):
        canvas.draw.line(
            [(i * cell, 10), (i * cell, PICTURE - 10)], fill="black", width=6
        )
        canvas.draw.line(
            [(10, i * cell), (PICTURE - 10, i * cell)], fill="black", width=6
        )
    for index, mark in enumerate(board):
        x, y = (index % 3 + 0.5) * cell, (index // 3 + 0.5) * cell
        if mark is None:
            canvas.text((x, y), str(index), size=36, fill=(170, 170, 170))
        else:
            canvas.text((x, y), mark, size=110, fill=MARK_COLORS[mark])
    return canvas.png()


MARK_COLORS: Final = {"X": (37, 99, 235), "O": (225, 29, 72)}


class TicTacToe(Game[TicTacToeState, Place]):
    """The classic: three in a row wins."""

    info = GameInfo(
        id="tictactoe",
        name="Tic-Tac-Toe",
        description="Take turns marking a 3x3 grid; three in a row wins.",
        min_players=2,
        max_players=2,
        action_modes=(ActionMode.CHOICE, ActionMode.STRUCTURED, ActionMode.TOOLS),
        tags=("classic", "turn-based", "solved"),
    )
    rules = (
        "Two players, X and O, take turns placing their mark in an empty cell "
        "of a 3x3 grid. X goes first. The first to get three of their marks in a "
        "row, column or diagonal wins. If all nine cells fill up with no line, "
        "the game is a draw."
    )
    state_type = TicTacToeState
    action_type = Place

    @override
    def initial_state(self, rng: random.Random) -> TicTacToeState:
        """Start with an empty board."""
        return TicTacToeState()

    @override
    def to_move(self, state: TicTacToeState) -> Sequence[int]:
        """X (seat 0) and O (seat 1) alternate."""
        return (MARKS.index(state.next_mark),)

    @override
    def legal_actions(self, state: TicTacToeState, player: int) -> Sequence[Place]:
        """Any empty cell, on your turn."""
        if self.outcome(state) is not None or MARKS[player] != state.next_mark:
            return ()
        return tuple(
            Place(cell=i) for i, mark in enumerate(state.board) if mark is None
        )

    @override
    def apply(
        self,
        state: TicTacToeState,
        actions: Mapping[int, Place],
        rng: random.Random,
    ) -> TicTacToeState:
        """Place the mark."""
        board = list(state.board)
        for player, action in actions.items():
            board[action.cell] = MARKS[player]
        return TicTacToeState(board=tuple(board))

    @override
    def outcome(self, state: TicTacToeState) -> Outcome | None:
        """Three in a row wins; a full board is a draw."""
        if (mark := winner(state.board)) is not None:
            return Outcome.win(2, MARKS.index(mark), f"{mark} got three in a row")
        if all(state.board):
            return Outcome.draw(2, "The board is full")
        return None

    @override
    def observe(self, state: TicTacToeState, player: int) -> str:
        """The board, with empty cells numbered.

        This ASCII layout is deliberately kept as is, so results stay comparable.
        Listing the eight lines in words instead measured noticeably better for
        TypeSafe's Jev at spotting threats (97% against 87% on forced moves);
        see `docs/notes/tictactoe-observation.md` before changing it.
        """
        mark = MARKS[player]
        other = MARKS[1 - player]
        empty = ", ".join(
            f"{i} ({cell_name(i)})"
            for i, cell in enumerate(state.board)
            if cell is None
        )
        return (
            f"You are {mark}; your opponent is {other}. "
            f"It is {state.next_mark}'s turn.\n"
            "Board (numbers are empty cells):\n"
            f"{render_board(state.board)}\n"
            f"Empty cells: {empty or 'none'}."
        )

    @override
    def snapshot(self, state: TicTacToeState, player: int) -> bytes:
        """The board as a picture: X in blue, O in red, empty cells numbered."""
        return draw_board(state.board)

    @override
    def brief(self, state: TicTacToeState, player: int) -> str:
        """Who is who, and whose turn it is; the picture shows the board."""
        mark, other = MARKS[player], MARKS[1 - player]
        return (
            f"You are {mark}; your opponent is {other}. It is {state.next_mark}'s "
            "turn. The picture shows the board; empty cells show their number."
        )

    @override
    def describe_action(self, action: Place) -> str:
        """Name the cell.

        Examples:
            >>> TicTacToe().describe_action(Place(cell=4))
            'Place your mark in the center (cell 4).'
        """
        return f"Place your mark in the {cell_name(action.cell)} (cell {action.cell})."

    @override
    def action_key(self, action: Place) -> str:
        """The cell number.

        Examples:
            >>> TicTacToe().action_key(Place(cell=4))
            '4'
        """
        return str(action.cell)

    @override
    def player_label(self, player: int) -> str:
        """`X` or `O`."""
        return MARKS[player]

    @override
    def bots(self) -> Mapping[str, BotFactory]:
        """A perfect player."""
        return {"minimax": MinimaxBot}

    @override
    def renderer(self) -> Renderer:
        """A clickable 3x3 grid."""
        from ludotastic.games.tictactoe.ui import render  # noqa: PLC0415

        return render


@cache
def _score(board: Board) -> int:
    """Minimax score from the point of view of the mark to move: 1, 0 or -1."""
    to_move: Mark = "X" if board.count("X") == board.count("O") else "O"
    if winner(board) is not None:
        return -1  # The previous player just won.
    empty = [i for i, cell in enumerate(board) if cell is None]
    if not empty:
        return 0
    return max(-_score(_place(board, i, to_move)) for i in empty)


def _place(board: Board, cell: int, mark: Mark) -> Board:
    return (*board[:cell], mark, *board[cell + 1 :])  # ty: ignore[invalid-return-type]


class MinimaxBot(Player):
    """Plays perfectly, breaking ties at random."""

    kind = PlayerKind.BOT

    def __init__(self, name: str = "minimax") -> None:
        """Name the player."""
        super().__init__(name)

    @override
    async def act(self, ctx: TurnContext) -> Decision:
        """Pick a move with the best minimax score."""
        state = ctx.state
        assert isinstance(state, TicTacToeState)  # noqa: S101
        mark = state.next_mark
        scored = [
            (-_score(_place(state.board, action.cell, mark)), action)
            for action in ctx.legal_actions
            if isinstance(action, Place)
        ]
        best = max(score for score, _ in scored)
        return Decision(
            action=ctx.rng.choice([a for score, a in scored if score == best]),
            details={"score": best},
        )
