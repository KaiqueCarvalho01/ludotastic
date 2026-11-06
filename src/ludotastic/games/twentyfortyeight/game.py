"""2048 rules."""

import random
from collections.abc import Mapping, Sequence
from enum import StrEnum
from itertools import pairwise
from typing import TYPE_CHECKING, override

from pydantic import BaseModel, ConfigDict

from ludotastic.engine.game import ActionMode, BotFactory, Game, GameInfo, Outcome
from ludotastic.engine.players import Decision, Player, PlayerKind, TurnContext

if TYPE_CHECKING:
    from ludotastic.engine.render import Renderer

__all__ = [
    "Direction",
    "GreedyBot",
    "Slide",
    "TwentyFortyEight",
    "TwentyFortyEightState",
]

SIZE = 4
GOAL = 2048
FOUR_CHANCE = 0.1
"""How often a new tile is a 4 rather than a 2."""

type Row = tuple[int, int, int, int]
type Board = tuple[Row, Row, Row, Row]
"""Rows top to bottom; 0 is an empty cell."""

EMPTY: Board = ((0,) * SIZE,) * SIZE  # ty: ignore[invalid-assignment]


class Direction(StrEnum):
    """Which way every tile slides."""

    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"


class TwentyFortyEightState(BaseModel):
    """The board after some number of moves."""

    model_config = ConfigDict(frozen=True)

    board: Board = EMPTY
    score: int = 0
    """The sum of every merged tile so far."""
    moves: int = 0

    @property
    def best(self) -> int:
        """The largest tile."""
        return max(max(row) for row in self.board)

    @property
    def empty(self) -> int:
        """How many cells are free."""
        return sum(cell == 0 for row in self.board for cell in row)


class Slide(BaseModel):
    """Slide every tile one way."""

    model_config = ConfigDict(frozen=True, use_attribute_docstrings=True)

    direction: Direction
    """Which way the tiles slide: up, down, left or right."""


def merge_line(line: Sequence[int]) -> tuple[tuple[int, ...], int, list[int]]:
    """Slide one line towards its start, merging equal neighbours once.

    Returns the new line, the points scored, and the tiles the merges made.

    Examples:
        >>> merge_line((2, 2, 2, 0))
        ((4, 2, 0, 0), 4, [4])
        >>> merge_line((4, 4, 8, 8))
        ((8, 16, 0, 0), 24, [8, 16])
        >>> merge_line((2, 0, 0, 2))
        ((4, 0, 0, 0), 4, [4])
    """
    tiles = [tile for tile in line if tile]
    merged: list[int] = []
    made: list[int] = []
    i = 0
    while i < len(tiles):
        if i + 1 < len(tiles) and tiles[i] == tiles[i + 1]:
            merged.append(tiles[i] * 2)
            made.append(tiles[i] * 2)
            i += 2
        else:
            merged.append(tiles[i])
            i += 1
    padded = (*merged, *([0] * (len(line) - len(merged))))
    return padded, sum(made), made


def _transpose(board: Board) -> Board:
    return tuple(zip(*board, strict=True))  # ty: ignore[invalid-return-type]


def _flip(board: Board) -> Board:
    return tuple(row[::-1] for row in board)  # ty: ignore[invalid-return-type]


def slide(board: Board, direction: Direction) -> tuple[Board, int, list[int]]:
    """Slide a whole board; returns the board, points scored and tiles made.

    Examples:
        >>> board = ((2, 2, 0, 0), (0, 0, 0, 0), (0, 0, 0, 4), (0, 0, 0, 4))
        >>> new, points, made = slide(board, Direction.DOWN)
        >>> new[3], points, made
        ((2, 2, 0, 8), 8, [8])
    """
    # Turn the board so the slide goes left, slide, then turn it back.
    turned = {
        Direction.LEFT: board,
        Direction.RIGHT: _flip(board),
        Direction.UP: _transpose(board),
        Direction.DOWN: _flip(_transpose(board)),
    }[direction]
    rows: list[tuple[int, ...]] = []
    points = 0
    made: list[int] = []
    for row in turned:
        line, scored, tiles = merge_line(row)
        rows.append(line)
        points += scored
        made += tiles
    result: Board = tuple(rows)  # ty: ignore[invalid-assignment]
    back = {
        Direction.LEFT: result,
        Direction.RIGHT: _flip(result),
        Direction.UP: _transpose(result),
        Direction.DOWN: _transpose(_flip(result)),
    }[direction]
    return back, points, made


def spawn(board: Board, rng: random.Random) -> Board:
    """Put a 2, or sometimes a 4, on a random empty cell."""
    free = [(r, c) for r in range(SIZE) for c in range(SIZE) if board[r][c] == 0]
    if not free:
        return board
    r, c = rng.choice(free)
    tile = 4 if rng.random() < FOUR_CHANCE else 2
    rows = [list(row) for row in board]
    rows[r][c] = tile
    return tuple(tuple(row) for row in rows)  # ty: ignore[invalid-return-type]


def in_corner(board: Board) -> bool:
    """Whether the largest tile sits in a corner.

    Examples:
        >>> in_corner(((8, 2, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0)))
        True
    """
    best = max(max(row) for row in board)
    corners = (board[0][0], board[0][-1], board[-1][0], board[-1][-1])
    return best in corners


def render_board(board: Board) -> str:
    """Draw the board in text, with `.` for empty cells.

    Examples:
        >>> board = ((2, 0, 0, 0), (0, 4, 0, 0), (0, 0, 0, 0), (0, 0, 0, 2048))
        >>> print(render_board(board))
            2    .    .    .
            .    4    .    .
            .    .    .    .
            .    .    . 2048
    """
    return "\n".join(
        "".join(f"{(str(cell) if cell else '.'):>5}" for cell in row) for row in board
    )


# Background and text colors per tile, after the original game.
TILE_COLORS = {
    0: ("#cdc1b4", "#776e65"),
    2: ("#eee4da", "#776e65"),
    4: ("#ede0c8", "#776e65"),
    8: ("#f2b179", "#f9f6f2"),
    16: ("#f59563", "#f9f6f2"),
    32: ("#f67c5f", "#f9f6f2"),
    64: ("#f65e3b", "#f9f6f2"),
    128: ("#edcf72", "#f9f6f2"),
    256: ("#edcc61", "#f9f6f2"),
    512: ("#edc850", "#f9f6f2"),
    1024: ("#edc53f", "#f9f6f2"),
    2048: ("#edc22e", "#f9f6f2"),
}
BIG_TILE = ("#3c3a32", "#f9f6f2")


class TwentyFortyEight(Game[TwentyFortyEightState, Slide]):
    """Slide numbered tiles to merge them, and reach 2048."""

    info = GameInfo(
        id="2048",
        name="2048",
        description="Slide numbered tiles; equal tiles merge. Reach 2048.",
        min_players=1,
        max_players=1,
        action_modes=(ActionMode.CHOICE, ActionMode.STRUCTURED, ActionMode.TOOLS),
        tags=("puzzle", "solo"),
    )
    rules = (
        f"A {SIZE}x{SIZE} board holds numbered tiles. Each move slides every tile "
        "as far as it goes up, down, left or right. Two equal tiles that collide "
        "merge into one with their sum, and the sum is added to the score; a tile "
        "merges at most once per move. After every move that changes the board, "
        f"a new 2 (or sometimes a 4) appears on an empty cell. Reaching {GOAL} is "
        "the classic goal, but play goes on for a higher score. The game ends when "
        "no move can change the board."
    )
    state_type = TwentyFortyEightState
    action_type = Slide

    @override
    def initial_state(self, rng: random.Random) -> TwentyFortyEightState:
        """An empty board with two starting tiles."""
        return TwentyFortyEightState(board=spawn(spawn(EMPTY, rng), rng))

    @override
    def to_move(self, state: TwentyFortyEightState) -> Sequence[int]:
        return (0,)

    @override
    def legal_actions(
        self, state: TwentyFortyEightState, player: int
    ) -> Sequence[Slide]:
        """The directions that change the board."""
        return tuple(
            Slide(direction=d)
            for d in Direction
            if slide(state.board, d)[0] != state.board
        )

    @override
    def apply(
        self,
        state: TwentyFortyEightState,
        actions: Mapping[int, Slide],
        rng: random.Random,
    ) -> TwentyFortyEightState:
        """Slide, score the merges, and add a new tile."""
        board, points, _ = slide(state.board, actions[0].direction)
        return TwentyFortyEightState(
            board=spawn(board, rng),
            score=state.score + points,
            moves=state.moves + 1,
        )

    @override
    def outcome(self, state: TwentyFortyEightState) -> Outcome | None:
        """Over when no move changes the board; the score is the result."""
        if self.legal_actions(state, 0):
            return None
        return Outcome(
            scores=(float(state.score),),
            reason=f"No moves left, best tile {state.best}, score {state.score}",
        )

    @override
    def out_of_turns(self, state: TwentyFortyEightState) -> Outcome:
        """Keep the score when the match runs out of turns."""
        return Outcome(
            scores=(float(state.score),),
            reason=f"Turn limit reached, best tile {state.best}, score {state.score}",
        )

    @override
    def observe(self, state: TwentyFortyEightState, player: int) -> str:
        """The board, plus the numbers a player needs."""
        corner = "is" if in_corner(state.board) else "is not"
        return (
            f"Score: {state.score}. Moves: {state.moves}. Best tile: {state.best}, "
            f"which {corner} in a corner. Empty cells: {state.empty}.\n"
            "Board (rows top to bottom, . is empty):\n"
            f"{render_board(state.board)}"
        )

    @override
    def describe_action(self, action: Slide) -> str:
        """The direction, in words.

        Examples:
            >>> TwentyFortyEight().describe_action(Slide(direction=Direction.UP))
            'Slide up.'
        """
        return f"Slide {action.direction}."

    @override
    def describe_option(
        self, state: TwentyFortyEightState, player: int, action: Slide
    ) -> str:
        """What sliding this way does, as facts.

        Examples:
            >>> state = TwentyFortyEightState(
            ...     board=((2, 2, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 8))
            ... )
            >>> text = TwentyFortyEight().describe_option(
            ...     state, 0, Slide(direction=Direction.LEFT)
            ... )
            >>> for sentence in text.split(". "):
            ...     print(sentence)
            Slide left
            Merges 2+2 into 4, scoring 4
            Leaves 14 empty cells before the new tile
            The largest tile (8) ends up in a corner.
        """
        board, points, made = slide(state.board, action.direction)
        parts = [self.describe_action(action)]
        if made:
            merges = ", ".join(
                f"{t // 2}+{t // 2} into {t}" for t in sorted(made, reverse=True)
            )
            parts.append(f"Merges {merges}, scoring {points}.")
        else:
            parts.append("Merges nothing.")
        empty = sum(cell == 0 for row in board for cell in row)
        parts.append(f"Leaves {empty} empty cells before the new tile.")
        best = max(max(row) for row in board)
        where = "ends up in a corner" if in_corner(board) else "is not in a corner"
        parts.append(f"The largest tile ({best}) {where}.")
        return " ".join(parts)

    @override
    def action_key(self, action: Slide) -> str:
        """The direction.

        Examples:
            >>> TwentyFortyEight().action_key(Slide(direction=Direction.LEFT))
            'left'
        """
        return str(action.direction)

    @override
    def player_label(self, player: int) -> str:
        return "Player"

    @override
    def bots(self) -> Mapping[str, BotFactory]:
        """A greedy bot: merge the most, keep the board open, guard the corner."""
        return {"greedy": GreedyBot}

    @override
    def renderer(self) -> Renderer:
        """The tiles, playable with the arrow keys or WASD."""
        from ludotastic.games.twentyfortyeight.ui import render  # noqa: PLC0415

        return render


# The corner strategy: keep the big tiles in the bottom-left, in a row that
# grows towards that corner, and avoid sliding up.
PREFERENCE = (Direction.DOWN, Direction.LEFT, Direction.RIGHT, Direction.UP)


def _monotonic(board: Board) -> int:
    """How well rows and columns decrease away from the bottom-left corner."""
    score = 0
    for row in board:
        score += sum(a >= b for a, b in pairwise(row))
    for col in zip(*board, strict=True):
        score += sum(a <= b for a, b in pairwise(col))
    return score


class GreedyBot(Player):
    """Plays the corner strategy, looking one move ahead."""

    kind = PlayerKind.BOT

    def __init__(self, name: str = "greedy") -> None:
        """Name the player."""
        super().__init__(name)

    @override
    async def act(self, ctx: TurnContext) -> Decision:
        """Pick the move that keeps the board tidiest, then merges the most."""
        state = ctx.state
        assert isinstance(state, TwentyFortyEightState)  # noqa: S101

        def rank(action: Slide) -> tuple[bool, int, int, int, int]:
            board, points, _ = slide(state.board, action.direction)
            empty = sum(cell == 0 for row in board for cell in row)
            anchored = board[-1][0] == max(max(row) for row in board)
            return (
                anchored,
                _monotonic(board),
                empty,
                points,
                -PREFERENCE.index(action.direction),
            )

        moves = [a for a in ctx.legal_actions if isinstance(a, Slide)]
        return Decision(action=max(moves, key=rank))
