"""Snake rules, bots and UI."""

import asyncio
import random

import pytest
from inline_snapshot import snapshot
from nicegui import ui
from nicegui.testing import User

from ludotastic import Match, MatchStatus, RandomBot, TurnContext
from ludotastic.games.snake import Direction, GreedyBot, Snake, SnakeState, Turn
from ludotastic.games.snake.game import MAX_IDLE, blocked_after, render_grid
from ludotastic.service import HumanSpec, MatchService

UP, DOWN, LEFT, RIGHT = (Turn(direction=d) for d in Direction)
GAME = Snake()


def state(
    body: tuple[tuple[int, int], ...],
    heading: Direction = Direction.RIGHT,
    food: tuple[int, int] | None = (9, 9),
    **kwargs: object,
) -> SnakeState:
    return SnakeState(body=body, heading=heading, food=food, **kwargs)  # ty: ignore[invalid-argument-type]


def test_initial_state() -> None:
    start = GAME.initial_state(random.Random(0))
    assert start.body == ((6, 6), (5, 6), (4, 6))
    assert start.food is not None
    assert start.food not in start.body
    assert GAME.to_move(start) == (0,)
    assert set(GAME.legal_actions(start, 0)) == {UP, DOWN, RIGHT}
    assert GAME.outcome(start) is None


def test_moves_and_follows() -> None:
    s = GAME.apply(state(((2, 2), (1, 2), (0, 2))), {0: DOWN}, random.Random(0))
    assert s.body == ((2, 3), (2, 2), (1, 2))
    assert s.heading is Direction.DOWN
    assert s.ticks == 1
    assert s.idle == 1


def test_missing_or_reversing_keeps_heading() -> None:
    start = state(((2, 2), (1, 2)))
    assert GAME.apply(start, {}, random.Random(0)).head == (3, 2)
    assert GAME.apply(start, {0: LEFT}, random.Random(0)).head == (3, 2)
    assert GAME.default_action(start, 0) == RIGHT


def test_eats_and_grows() -> None:
    s = GAME.apply(state(((2, 2), (1, 2)), food=(3, 2)), {0: RIGHT}, random.Random(0))
    assert s.body == ((3, 2), (2, 2), (1, 2))
    assert s.score == 1
    assert s.idle == 0
    assert s.food is not None
    assert s.food not in s.body


def test_full_board_wins() -> None:
    tiny = SnakeState(
        width=2, height=1, body=((0, 0),), heading=Direction.RIGHT, food=(1, 0)
    )
    s = GAME.apply(tiny, {0: RIGHT}, random.Random(0))
    assert s.food is None
    outcome = GAME.outcome(s)
    assert outcome is not None
    assert outcome.reason == "Filled the board with 1 point"


@pytest.mark.parametrize(
    ("body", "move", "hit"),
    [
        (((0, 0), (1, 0)), LEFT, "the wall"),
        (((2, 2), (2, 3), (3, 3), (3, 2), (3, 1)), RIGHT, "its own body"),
    ],
)
def test_crashes(body: tuple[tuple[int, int], ...], move: Turn, hit: str) -> None:
    s = GAME.apply(state(body, heading=Direction.UP), {0: move}, random.Random(0))
    assert s.crashed == hit
    assert GAME.legal_actions(s, 0) == ()
    outcome = GAME.outcome(s)
    assert outcome is not None
    assert outcome.scores == (0.0,)
    assert outcome.reason == f"Hit {hit} after 0 points"


def test_tail_moves_out_of_the_way() -> None:
    loop = state(((2, 2), (2, 3), (3, 3), (3, 2)), heading=Direction.UP)
    assert blocked_after(loop, Direction.RIGHT) is None
    fed = loop.model_copy(update={"food": (3, 2)})
    assert blocked_after(fed, Direction.RIGHT) == "its own body"


def test_idle_limit() -> None:
    outcome = GAME.outcome(state(((2, 2),), idle=MAX_IDLE, score=3))
    assert outcome is not None
    assert outcome.reason == f"Went {MAX_IDLE} ticks without eating, with 3 points"


def test_observe() -> None:
    small = SnakeState(
        width=4, height=3, body=((1, 1), (0, 1)), heading=Direction.RIGHT, food=(3, 0)
    )
    assert GAME.observe(small, 0) == snapshot("""\
Score: 0. The snake is 2 cells long and heading right.
Its head is at x=1, y=1 (x grows to the right, y grows downwards).
The food is at x=3, y=0.
Board (H head, o body, * food, . empty):
   0 1 2 3
 0 . . . *
 1 o H . .
 2 . . . .\
""")
    assert "There is no food left." in GAME.observe(
        small.model_copy(update={"food": None}), 0
    )
    assert render_grid(small).count("H") == 1


def test_describe_option() -> None:
    s = state(((1, 1), (0, 1)), food=(2, 1))
    assert GAME.describe_option(s, 0, RIGHT) == "Move right. This eats the food."
    hungry = s.model_copy(update={"food": None})
    assert GAME.describe_option(hungry, 0, DOWN) == "Move down. 143 cells reachable."
    assert GAME.describe_option(s, 0, DOWN) == snapshot(
        "Move down. The food would be 2 steps away (now 1). 143 cells reachable."
    )


def test_labels_and_keys() -> None:
    assert GAME.player_label(0) == "Snake"
    assert GAME.action_key(UP) == "up"
    assert GAME.parse_action({"direction": "left"}) == LEFT
    assert list(GAME.bots()) == ["greedy"]
    assert callable(GAME.renderer())


def ctx(s: SnakeState) -> TurnContext:
    return TurnContext(
        game=GAME,
        state=s,
        player=0,
        legal_actions=GAME.legal_actions(s, 0),
        turn=0,
        rng=random.Random(0),
    )


async def test_greedy_heads_for_food_safely() -> None:
    s = state(((5, 5), (4, 5)), food=(5, 2))
    assert (await GreedyBot().act(ctx(s))).action == UP
    cornered = state(((0, 1), (1, 1)), heading=Direction.LEFT, food=(0, 5))
    assert (await GreedyBot().act(ctx(cornered))).action == DOWN
    no_food = state(((5, 5), (4, 5)), food=None)
    assert (await GreedyBot().act(ctx(no_food))).action in {UP, DOWN, RIGHT}


async def test_greedy_beats_random() -> None:
    greedy = await Match(Snake(), [GreedyBot()], seed=1).run()
    random_ = await Match(Snake(), [RandomBot()], seed=1).run()
    assert greedy is not None
    assert random_ is not None
    assert greedy.scores[0] > 10 > random_.scores[0]


async def test_play_with_the_keyboard(user: User, service: MatchService) -> None:
    match = service.create("snake", [HumanSpec()])
    await user.open(f"/match/{match.id}")
    await user.should_see("Score 0")
    await user.should_see("Arrow keys or WASD to steer")
    start = match.state
    assert isinstance(start, SnakeState)

    def press(key: str) -> None:
        user.find(ui.keyboard).trigger(
            "key",
            {
                "action": "keydown",
                "key": key,
                "code": key,
                "repeat": False,
                "altKey": False,
                "ctrlKey": False,
                "shiftKey": False,
                "metaKey": False,
                "location": 0,
            },
        )

    press("x")  # Not a steering key: ignored.
    press("ArrowDown")
    for _ in range(100):
        if match.history and match.history[-1].action == {"direction": "down"}:
            break
        await asyncio.sleep(0.02)
    assert match.history[-1].action == {"direction": "down"}
    assert not match.history[-1].forced
    user.find(marker="steer-up").click()  # Straight back: ignored by the rules.
    match.abort("done")
    assert match.status is MatchStatus.ABORTED
    await user.should_not_see("Arrow keys or WASD to steer")


async def test_turn_limit_keeps_the_score() -> None:
    match = Match(Snake(), [GreedyBot()], seed=1, max_turns=40)
    outcome = await match.run()
    assert outcome is not None
    assert outcome.reason.startswith("Turn limit reached with ")
    state = match.state
    assert isinstance(state, SnakeState)
    assert outcome.scores == (float(state.score),)
