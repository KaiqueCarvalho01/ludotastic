"""Tic-Tac-Toe rules and bots."""

__all__: tuple[str, ...] = ()

import random

import pytest
from hypothesis import given
from hypothesis import strategies as st
from inline_snapshot import snapshot

from ludotastic import Match, MatchStatus, RandomBot, TurnContext
from ludotastic.games.tictactoe import MinimaxBot, Place, TicTacToe, TicTacToeState


def board(text: str) -> TicTacToeState:
    """Build a state from nine characters, `.` for empty."""
    return TicTacToeState(
        board=tuple(None if c == "." else c for c in text)  # type: ignore[ty:invalid-argument-type]
    )


def test_initial_state() -> None:
    game = TicTacToe()
    state = game.initial_state(random.Random(0))
    assert game.to_move(state) == (0,)
    assert len(game.legal_actions(state, 0)) == 9
    assert game.legal_actions(state, 1) == ()
    assert game.outcome(state) is None


def test_wrong_player_count() -> None:
    with pytest.raises(ValueError, match="needs 2 to 2 players"):
        TicTacToe(3)


def test_apply_alternates() -> None:
    game = TicTacToe()
    rng = random.Random(0)
    state = game.apply(game.initial_state(rng), {0: Place(cell=4)}, rng)
    assert state.board[4] == "X"
    assert game.to_move(state) == (1,)
    assert Place(cell=4) not in game.legal_actions(state, 1)


@pytest.mark.parametrize(
    ("text", "scores"),
    [
        ("XXXOO....", (1.0, 0.0)),
        ("OX.OX.O.X", (0.0, 1.0)),
        ("X.O.XO..X", (1.0, 0.0)),
        ("XOXXOOOXX", (0.5, 0.5)),
    ],
)
def test_outcome(text: str, scores: tuple[float, float]) -> None:
    outcome = TicTacToe().outcome(board(text))
    assert outcome is not None
    assert outcome.scores == scores


def test_no_moves_after_a_win() -> None:
    assert TicTacToe().legal_actions(board("XXXOO...."), 1) == ()


def test_observe() -> None:
    assert TicTacToe().observe(board("X...O...."), 0) == snapshot("""\
You are X; your opponent is O. It is X's turn.
Board (numbers are empty cells):
 X | 1 | 2
---+---+---
 3 | O | 5
---+---+---
 6 | 7 | 8
Empty cells: 1 (top center), 2 (top right), 3 (middle left), 5 (middle right), 6 (bottom left), 7 (bottom center), 8 (bottom right).\
""")


def test_parse_action() -> None:
    assert TicTacToe().parse_action({"cell": 3}) == Place(cell=3)


def _ctx(game: TicTacToe, state: TicTacToeState, player: int) -> TurnContext:
    return TurnContext(
        game=game,
        state=state,
        player=player,
        legal_actions=game.legal_actions(state, player),
        turn=0,
        rng=random.Random(0),
    )


@pytest.mark.parametrize(
    ("text", "player", "expected"),
    [
        ("XX.OO....", 0, 2),  # Win.
        ("XX..O....", 1, 2),  # Block.
    ],
)
async def test_minimax_finds_the_move(text: str, player: int, expected: int) -> None:
    game = TicTacToe()
    decision = await MinimaxBot().act(_ctx(game, board(text), player))
    assert decision.action == Place(cell=expected)


@given(seed=st.integers(0, 2**32 - 1), minimax_first=st.booleans())
async def test_minimax_never_loses(seed: int, minimax_first: bool) -> None:  # noqa: FBT001
    players = [MinimaxBot(), RandomBot()]
    if not minimax_first:
        players.reverse()
    match = Match(TicTacToe(), players, seed=seed)
    outcome = await match.run()
    assert match.status is MatchStatus.FINISHED
    assert outcome is not None
    minimax_seat = 0 if minimax_first else 1
    assert outcome.scores[minimax_seat] >= 0.5


async def test_minimax_draws_itself() -> None:
    outcome = await Match(TicTacToe(), [MinimaxBot(), MinimaxBot()], seed=1).run()
    assert outcome is not None
    assert outcome.scores == (0.5, 0.5)


def test_renderer_is_lazy() -> None:
    assert callable(TicTacToe().renderer())
