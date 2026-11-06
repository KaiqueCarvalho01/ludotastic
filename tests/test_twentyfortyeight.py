"""2048 rules, bots and UI."""

__all__: tuple[str, ...] = ()

import asyncio
import random
from typing import Final

import pytest
from inline_snapshot import snapshot
from nicegui import ui
from nicegui.testing import User

from ludotastic import Match, RandomBot, TurnContext
from ludotastic.games.twentyfortyeight import (
    Direction,
    GreedyBot,
    Slide,
    TwentyFortyEight,
    TwentyFortyEightState,
)
from ludotastic.games.twentyfortyeight.game import Board, in_corner, slide, spawn
from ludotastic.service import HumanSpec, MatchService

UP, DOWN, LEFT, RIGHT = (Slide(direction=d) for d in Direction)
KEYS: Final = {d: f"Arrow{d.title()}" for d in Direction}
GAME: Final = TwentyFortyEight()


def board(*rows: str) -> Board:
    """Build a board from four rows of four space-separated numbers."""
    return tuple(tuple(int(n) for n in row.split()) for row in rows)  # type: ignore[ty:invalid-return-type]


def state(*rows: str, score: int = 0) -> TwentyFortyEightState:
    return TwentyFortyEightState(board=board(*rows), score=score)


def test_initial_state() -> None:
    start = GAME.initial_state(random.Random(0))
    assert start.empty == 14
    assert start.score == 0
    assert GAME.to_move(start) == (0,)
    assert GAME.outcome(start) is None


@pytest.mark.parametrize(
    ("direction", "expected", "points"),
    [
        (Direction.LEFT, ("4 0 0 0", "4 4 0 0", "0 0 0 0", "8 0 0 0"), 16),
        (Direction.RIGHT, ("0 0 0 4", "0 0 4 4", "0 0 0 0", "0 0 0 8"), 16),
        (Direction.UP, ("4 4 4 4", "4 0 0 0", "0 0 0 0", "0 0 0 0"), 8),
        (Direction.DOWN, ("0 0 0 0", "0 0 0 0", "4 0 0 0", "4 4 4 4"), 8),
    ],
)
def test_slides(direction: Direction, expected: tuple[str, ...], points: int) -> None:
    start = board("2 2 0 0", "2 2 4 0", "0 0 0 0", "4 0 0 4")
    new, scored, _ = slide(start, direction)
    assert new == board(*expected)
    assert scored == points


def test_apply_scores_and_spawns() -> None:
    s = GAME.apply(
        state("2 2 0 0", "0 0 0 0", "0 0 0 0", "0 0 0 0"), {0: LEFT}, random.Random(1)
    )
    assert s.score == 4
    assert s.moves == 1
    assert s.board[0][0] == 4
    assert s.empty == 14  # One merge freed a cell; one new tile took one.


def test_spawn() -> None:
    full = board("2 4 2 4", "4 2 4 2", "2 4 2 4", "4 2 4 2")
    assert spawn(full, random.Random(0)) == full
    empty = board("0 0 0 0", "0 0 0 0", "0 0 0 0", "0 0 0 0")
    tiles = {max(map(max, spawn(empty, random.Random(seed)))) for seed in range(100)}
    assert tiles == {2, 4}


def test_only_moves_that_change_the_board() -> None:
    stuck_left = state("2 4 0 0", "4 2 0 0", "0 0 0 0", "0 0 0 0")
    assert set(GAME.legal_actions(stuck_left, 0)) == {RIGHT, DOWN}


def test_game_over_and_turn_limit() -> None:
    over = state("2 4 2 4", "4 2 4 2", "2 4 2 4", "4 2 4 2", score=128)
    outcome = GAME.outcome(over)
    assert outcome is not None
    assert outcome.scores == (128.0,)
    assert outcome.reason == "No moves left, best tile 4, score 128"
    limit = GAME.out_of_turns(
        state("2 0 0 0", "0 0 0 0", "0 0 0 0", "0 0 0 0", score=8)
    )
    assert limit.reason == "Turn limit reached, best tile 2, score 8"


def test_observe_and_options() -> None:
    s = state("2 2 0 0", "0 0 0 0", "0 0 0 0", "0 0 0 8", score=36)
    assert GAME.observe(s, 0) == snapshot("""\
Score: 36. Moves: 0. Best tile: 8, which is in a corner. Empty cells: 13.
Board (rows top to bottom, . is empty):
    2    2    .    .
    .    .    .    .
    .    .    .    .
    .    .    .    8\
""")
    assert GAME.describe_option(s, 0, UP) == snapshot(
        "Slide up. Merges nothing. Leaves 13 empty cells before the new tile. The largest tile (8) ends up in a corner."
    )
    off = state("0 0 0 0", "0 8 0 0", "0 0 0 0", "0 0 0 0")
    assert not in_corner(off.board)
    assert "is not in a corner" in GAME.observe(off, 0)
    assert "is not in a corner" in GAME.describe_option(off, 0, DOWN)


def test_labels_and_keys() -> None:
    assert GAME.player_label(0) == "Player"
    assert GAME.action_key(UP) == "up"
    assert GAME.parse_action({"direction": "left"}) == LEFT
    assert list(GAME.bots()) == ["greedy"]
    assert callable(GAME.renderer())


async def test_greedy_keeps_the_corner() -> None:
    s = state("0 0 0 0", "0 0 0 0", "0 0 0 2", "8 4 2 0")
    ctx = TurnContext(
        game=GAME,
        state=s,
        player=0,
        legal_actions=GAME.legal_actions(s, 0),
        turn=0,
        rng=random.Random(0),
    )
    assert (await GreedyBot().act(ctx)).action in {DOWN, LEFT}


async def test_greedy_beats_random() -> None:
    greedy = [
        await Match(TwentyFortyEight(), [GreedyBot()], seed=s).run() for s in range(4)
    ]
    random_ = [
        await Match(TwentyFortyEight(), [RandomBot()], seed=s).run() for s in range(4)
    ]
    total = sum(o.scores[0] for o in greedy if o is not None)
    baseline = sum(o.scores[0] for o in random_ if o is not None)
    assert total > baseline


async def test_play_with_the_keyboard(user: User, service: MatchService) -> None:
    match = service.create("2048", [HumanSpec()], seed=11)  # Down is stuck.
    await user.open(f"/match/{match.id}")
    await user.should_see("Score 0")
    await user.should_see("Arrow keys or WASD to slide")

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

    press("x")  # Not a sliding key: ignored.
    start = match.state
    assert isinstance(start, TwentyFortyEightState)
    stuck = [
        d for d in Direction if Slide(direction=d) not in GAME.legal_actions(start, 0)
    ]
    for direction in stuck:  # A slide that changes nothing: ignored, no warning.
        press(KEYS[direction])
    await asyncio.sleep(0.05)
    assert not match.history
    await user.should_not_see("Illegal action")
    legal = GAME.legal_actions(match.state, 0)  # type: ignore[ty:invalid-argument-type]
    key = {
        d: k
        for k, d in {
            "ArrowUp": Direction.UP,
            "ArrowDown": Direction.DOWN,
            "ArrowLeft": Direction.LEFT,
            "ArrowRight": Direction.RIGHT,
        }.items()
    }[legal[0].direction]
    press(key)
    for _ in range(100):
        if match.history:
            break
        await asyncio.sleep(0.01)
    assert match.history[0].action == {"direction": str(legal[0].direction)}
    match.abort("done")
    await user.should_not_see("Arrow keys or WASD to slide")


@pytest.mark.parametrize("tile", [3, 1, -2, 6])
def test_boards_only_hold_powers_of_two(tile: int) -> None:
    from pydantic import ValidationError  # noqa: PLC0415

    with pytest.raises(ValidationError):
        TwentyFortyEightState.model_validate(
            {"board": [[tile, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]}
        )
