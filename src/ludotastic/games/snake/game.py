"""Snake rules."""

__all__: tuple[str, ...] = (
    "Direction",
    "GreedyBot",
    "Snake",
    "SnakeState",
    "Turn",
)

import random
from collections import deque
from collections.abc import Iterable, Mapping, Sequence
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Final, override

from annotated_types import Ge
from pydantic import BaseModel, ConfigDict

from ludotastic.engine.drawing import Canvas
from ludotastic.engine.game import (
    ActionMode,
    BotFactory,
    Game,
    GameInfo,
    Outcome,
    Timing,
)
from ludotastic.engine.players import Decision, Player, PlayerKind, TurnContext
from ludotastic.types import Count, PositiveInt, Seat

if TYPE_CHECKING:
    from ludotastic.engine.render import Renderer

WIDTH: Final = 12
HEIGHT: Final = 12
START_LENGTH: Final = 3
MAX_IDLE: Final = 6 * WIDTH * HEIGHT
"""Ticks without eating after which the game ends, so a looping snake stops."""

type Coordinate = Annotated[int, Ge(0)]
"""A column or row number, counting from 0 at the top left."""

type Cell = tuple[Coordinate, Coordinate]
"""A cell as `(x, y)`, with `(0, 0)` at the top left.

Neighbours of edge cells can fall off the board, so `step` can return
negative coordinates; `SnakeState.inside` tells them apart.
"""


class Direction(StrEnum):
    """Where the snake heads."""

    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"

    @property
    def delta(self) -> Cell:
        """The step this direction takes.

        Examples:
            >>> Direction.LEFT.delta
            (-1, 0)
        """
        return _DELTAS[self]

    @property
    def opposite(self) -> Direction:
        """The direction straight back.

        Examples:
            >>> Direction.UP.opposite
            <Direction.DOWN: 'down'>
        """
        return _OPPOSITES[self]


_DELTAS: Final[dict[Direction, Cell]] = {
    Direction.UP: (0, -1),
    Direction.DOWN: (0, 1),
    Direction.LEFT: (-1, 0),
    Direction.RIGHT: (1, 0),
}
_OPPOSITES: Final = {
    Direction.UP: Direction.DOWN,
    Direction.DOWN: Direction.UP,
    Direction.LEFT: Direction.RIGHT,
    Direction.RIGHT: Direction.LEFT,
}


class SnakeState(BaseModel):
    """The board after some number of ticks."""

    model_config = ConfigDict(frozen=True)

    width: PositiveInt = WIDTH
    height: PositiveInt = HEIGHT
    body: tuple[Cell, ...]
    """The snake, head first."""
    heading: Direction
    """The direction the snake last moved in."""
    food: Cell | None
    """Where the food is; `None` once the board is full."""
    score: Count = 0
    """Food eaten so far."""
    ticks: Count = 0
    idle: Count = 0
    """Ticks since the snake last ate."""
    crashed: str | None = None
    """What the snake ran into, once it has."""

    @property
    def head(self) -> Cell:
        """The cell the snake's head is on."""
        return self.body[0]

    def inside(self, cell: Cell) -> bool:
        """Whether a cell is on the board."""
        x, y = cell
        return 0 <= x < self.width and 0 <= y < self.height


class Turn(BaseModel):
    """Head in a direction this tick."""

    model_config = ConfigDict(frozen=True, use_attribute_docstrings=True)

    direction: Direction
    """Which way the head moves: up, down, left or right."""


def step(cell: Cell, direction: Direction) -> Cell:
    """The neighbour of a cell in a direction.

    Examples:
        >>> step((3, 3), Direction.UP)
        (3, 2)
    """
    dx, dy = direction.delta
    return cell[0] + dx, cell[1] + dy


def blocked_after(state: SnakeState, direction: Direction) -> str | None:
    """What the head would hit by moving in `direction`, if anything.

    The tail moves away as the head moves in, unless the snake eats, so moving
    into the tail's cell is safe when there is no food there.
    """
    target = step(state.head, direction)
    if not state.inside(target):
        return "the wall"
    grows = target == state.food
    body = state.body if grows else state.body[:-1]
    if target in body:
        return "its own body"
    return None


def reachable(state: SnakeState, start: Cell, blocked: Iterable[Cell]) -> Count:
    """How many cells can be reached from `start`, avoiding `blocked`."""
    walls = set(blocked)
    seen = {start}
    queue = deque([start])
    while queue:
        cell = queue.popleft()
        for direction in Direction:
            nxt = step(cell, direction)
            if nxt not in seen and nxt not in walls and state.inside(nxt):
                seen.add(nxt)
                queue.append(nxt)
    return len(seen)


def distance(a: Cell, b: Cell) -> Count:
    """Steps between two cells, ignoring obstacles.

    Examples:
        >>> distance((0, 0), (3, 4))
        7
    """
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def place_food(state: SnakeState, rng: random.Random) -> Cell | None:
    """A random free cell, or `None` if the snake fills the board."""
    taken = set(state.body)
    free = [
        (x, y)
        for y in range(state.height)
        for x in range(state.width)
        if (x, y) not in taken
    ]
    return rng.choice(free) if free else None


def render_grid(state: SnakeState) -> str:
    """Draw the board in text.

    `H` is the head, `o` the body, `*` the food and `.` an empty cell. Rows and
    columns are numbered from 0, top left.
    """
    body = set(state.body[1:])
    header = "   " + " ".join(f"{x % 10}" for x in range(state.width))
    rows = [header]
    for y in range(state.height):
        cells = []
        for x in range(state.width):
            cell = (x, y)
            if cell == state.head:
                cells.append("H")
            elif cell in body:
                cells.append("o")
            elif cell == state.food:
                cells.append("*")
            else:
                cells.append(".")
        rows.append(f"{y:2} " + " ".join(cells))
    return "\n".join(rows)


PIXELS: Final = 40
"""Side of one cell in the board picture."""


def draw_board(state: SnakeState) -> bytes:
    """Draw the board as a PNG, the way it looks in the playground.

    Examples:
        >>> state = SnakeState(body=((1, 1),), heading=Direction.RIGHT, food=(3, 3))
        >>> draw_board(state)[1:4]
        b'PNG'
    """
    canvas = Canvas(state.width * PIXELS, state.height * PIXELS)
    body = set(state.body[1:])
    for y in range(state.height):
        for x in range(state.width):
            box = (
                x * PIXELS + 2,
                y * PIXELS + 2,
                (x + 1) * PIXELS - 2,
                (y + 1) * PIXELS - 2,
            )
            if (x, y) == state.head:
                canvas.draw.rounded_rectangle(box, radius=8, fill=(4, 120, 87))
            elif (x, y) in body:
                canvas.draw.rounded_rectangle(box, radius=4, fill=(52, 211, 153))
            else:
                canvas.draw.rounded_rectangle(box, radius=4, fill=(243, 244, 246))
                if (x, y) == state.food:
                    canvas.draw.ellipse(
                        (box[0] + 6, box[1] + 6, box[2] - 6, box[3] - 6),
                        fill=(244, 63, 94),
                    )
    return canvas.png()


class Snake(Game[SnakeState, Turn]):
    """The classic: eat, grow, and do not bite yourself."""

    info = GameInfo(
        id="snake",
        name="Snake",
        description="Steer a growing snake to the food without hitting anything.",
        min_players=1,
        max_players=1,
        timing=Timing.TICK,
        tick_seconds=0.25,
        action_modes=(ActionMode.CHOICE, ActionMode.STRUCTURED, ActionMode.TOOLS),
        tags=("classic", "real-time", "solo"),
    )
    rules = (
        f"You steer a snake on a {WIDTH}x{HEIGHT} board. Every tick it moves one "
        "cell in the direction you choose: up, down, left or right. It cannot "
        "turn straight back on itself. Eating the food scores a point and makes "
        "the snake one cell longer, and new food appears elsewhere. The game "
        "ends when the snake hits a wall or its own body, or goes "
        f"{MAX_IDLE} ticks without eating. Score as many points as you can."
    )
    state_type = SnakeState
    action_type = Turn

    @override
    def initial_state(self, rng: random.Random) -> SnakeState:
        """A short snake in the middle, heading right, with food somewhere."""
        y = HEIGHT // 2
        x = WIDTH // 2
        body = tuple((x - i, y) for i in range(START_LENGTH))
        state = SnakeState(body=body, heading=Direction.RIGHT, food=None)
        return state.model_copy(update={"food": place_food(state, rng)})

    @override
    def to_move(self, state: SnakeState) -> Sequence[Seat]:
        return (0,)

    @override
    def legal_actions(self, state: SnakeState, player: Seat) -> Sequence[Turn]:
        """Any direction but straight back."""
        if state.crashed is not None:
            return ()
        return tuple(
            Turn(direction=d) for d in Direction if d != state.heading.opposite
        )

    @override
    def default_action(self, state: SnakeState, player: Seat) -> Turn:
        """Too slow: keep going the same way."""
        return Turn(direction=state.heading)

    @override
    def apply(
        self,
        state: SnakeState,
        actions: Mapping[int, Turn],
        rng: random.Random,
    ) -> SnakeState:
        """Move one cell; eat, grow, or crash."""
        direction = actions[0].direction if 0 in actions else state.heading
        if direction == state.heading.opposite:
            direction = state.heading
        ticks = state.ticks + 1
        if (hit := blocked_after(state, direction)) is not None:
            return state.model_copy(
                update={"crashed": hit, "ticks": ticks, "heading": direction}
            )
        head = step(state.head, direction)
        if head == state.food:
            grown = state.model_copy(
                update={
                    "body": (head, *state.body),
                    "heading": direction,
                    "score": state.score + 1,
                    "ticks": ticks,
                    "idle": 0,
                }
            )
            return grown.model_copy(update={"food": place_food(grown, rng)})
        return state.model_copy(
            update={
                "body": (head, *state.body[:-1]),
                "heading": direction,
                "ticks": ticks,
                "idle": state.idle + 1,
            }
        )

    @override
    def outcome(self, state: SnakeState) -> Outcome | None:
        """Over on a crash, a full board, or too long without eating.

        The score is the food eaten, so solo matches can be compared.
        """
        points = f"{state.score} point{'s' if state.score != 1 else ''}"
        if state.crashed is not None:
            reason = f"Hit {state.crashed} after {points}"
        elif state.food is None:
            reason = f"Filled the board with {points}"
        elif state.idle >= MAX_IDLE:
            reason = f"Went {MAX_IDLE} ticks without eating, with {points}"
        else:
            return None
        return Outcome(scores=(float(state.score),), reason=reason)

    @override
    def out_of_turns(self, state: SnakeState) -> Outcome:
        """Keep the score when the match runs out of turns."""
        points = f"{state.score} point{'s' if state.score != 1 else ''}"
        return Outcome(
            scores=(float(state.score),), reason=f"Turn limit reached with {points}"
        )

    @override
    def observe(self, state: SnakeState, player: Seat) -> str:
        """The grid, plus the facts a player needs about it."""
        hx, hy = state.head
        food = (
            f"The food is at x={state.food[0]}, y={state.food[1]}."
            if state.food is not None
            else "There is no food left."
        )
        return (
            f"Score: {state.score}. The snake is {len(state.body)} cells long and "
            f"heading {state.heading}.\n"
            f"Its head is at x={hx}, y={hy} (x grows to the right, y grows "
            "downwards).\n"
            f"{food}\n"
            "Board (H head, o body, * food, . empty):\n"
            f"{render_grid(state)}"
        )

    @override
    def snapshot(self, state: SnakeState, player: Seat) -> bytes:
        """The board as a picture, as it looks in the playground."""
        return draw_board(state)

    @override
    def brief(self, state: SnakeState, player: Seat) -> str:
        """The score and heading; the picture shows the board."""
        return (
            f"Score: {state.score}. The snake is {len(state.body)} cells long and "
            f"heading {state.heading}. The picture shows the board: the snake is "
            "green with a darker head, and the food is the red dot."
        )

    @override
    def describe_action(self, action: Turn) -> str:
        """The direction, in words.

        Examples:
            >>> Snake().describe_action(Turn(direction=Direction.UP))
            'Move up.'
        """
        return f"Move {action.direction}."

    @override
    def describe_option(self, state: SnakeState, player: Seat, action: Turn) -> str:
        """What moving this way leads to, as facts.

        Examples:
            >>> state = SnakeState(
            ...     width=6,
            ...     height=6,
            ...     body=((1, 0), (0, 0)),
            ...     heading=Direction.RIGHT,
            ...     food=(3, 0),
            ... )
            >>> Snake().describe_option(state, 0, Turn(direction=Direction.RIGHT))
            'Move right. The food would be 1 step away (now 2). 35 cells reachable.'
            >>> Snake().describe_option(state, 0, Turn(direction=Direction.UP))
            'Move up. This hits the wall: the game ends.'
        """
        text = self.describe_action(action)
        hit = blocked_after(state, action.direction)
        if hit is not None:
            return f"{text} This hits {hit}: the game ends."
        head = step(state.head, action.direction)
        if head == state.food:
            return f"{text} This eats the food."
        parts = [text]
        if state.food is not None:
            now = distance(state.head, state.food)
            then = distance(head, state.food)
            steps = "step" if then == 1 else "steps"
            parts.append(f"The food would be {then} {steps} away (now {now}).")
        space = reachable(state, head, state.body[:-1])
        parts.append(f"{space} cells reachable.")
        return " ".join(parts)

    @override
    def action_key(self, action: Turn) -> str:
        """The direction.

        Examples:
            >>> Snake().action_key(Turn(direction=Direction.LEFT))
            'left'
        """
        return str(action.direction)

    @override
    def player_label(self, player: Seat) -> str:
        return "Snake"

    @override
    def bots(self) -> Mapping[str, BotFactory]:
        """A greedy bot that heads for the food without boxing itself in."""
        return {"greedy": GreedyBot}

    @override
    def renderer(self) -> Renderer:
        """The board, steerable with the arrow keys or WASD."""
        from ludotastic.games.snake.ui import render  # noqa: PLC0415

        return render


class GreedyBot(Player):
    """Heads for the food, preferring moves that keep the most room."""

    kind = PlayerKind.BOT

    def __init__(self, name: str = "greedy") -> None:
        """Name the player."""
        super().__init__(name)

    @override
    async def act(self, ctx: TurnContext) -> Decision:
        """Pick the safe move closest to the food, breaking ties by room."""
        state = ctx.state
        assert isinstance(state, SnakeState)  # noqa: S101

        def rank(action: Turn) -> tuple[bool, bool, int, int]:
            safe = blocked_after(state, action.direction) is None
            head = step(state.head, action.direction)
            room = reachable(state, head, state.body[:-1]) if safe else 0
            roomy = room >= len(state.body)
            near = -distance(head, state.food) if state.food is not None else 0
            return safe, roomy, near, room

        moves = [a for a in ctx.legal_actions if isinstance(a, Turn)]
        best = max(rank(a) for a in moves)
        choices = [a for a in moves if rank(a) == best]
        return Decision(action=ctx.rng.choice(choices))
