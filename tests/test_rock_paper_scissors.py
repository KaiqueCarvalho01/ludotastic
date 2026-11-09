"""Rock-Paper-Scissors rules, bots and UI."""

__all__: tuple[str, ...] = ()

import asyncio
import random
from typing import Final

import pytest
from inline_snapshot import snapshot
from nicegui.testing import User
from pydantic import ValidationError

from ludotastic import Match, MatchStatus, RandomBot, TurnContext
from ludotastic.games.rock_paper_scissors import (
    CounterBot,
    Move,
    RockPaperScissors,
    RockPaperScissorsState,
    Throw,
)
from ludotastic.games.rock_paper_scissors.game import MAX_ROUNDS, TARGET_WINS
from ludotastic.service import HumanSpec, MatchService

GAME: Final = RockPaperScissors()
THROWS: Final = tuple(Throw(move=move) for move in Move)


def state(
    wins: tuple[int, int] = (0, 0),
    rounds: int = 0,
    last: tuple[Move | None, Move | None] = (None, None),
) -> RockPaperScissorsState:
    return RockPaperScissorsState(wins=wins, rounds=rounds, last=last)


def ctx(s: RockPaperScissorsState, player: int) -> TurnContext:
    return TurnContext(
        game=GAME,
        state=s,
        player=player,
        legal_actions=GAME.legal_actions(s, player),
        turn=s.rounds,
        rng=random.Random(0),
    )


def test_initial_state() -> None:
    start = GAME.initial_state(random.Random(0))
    assert start.wins == (0, 0)
    assert start.rounds == 0
    assert start.last == (None, None)
    assert GAME.to_move(start) == (0, 1)
    assert set(GAME.legal_actions(start, 0)) == set(THROWS)
    assert set(GAME.legal_actions(start, 1)) == set(THROWS)
    assert GAME.outcome(start) is None


@pytest.mark.parametrize("players", [1, 3])
def test_wrong_player_count(players: int) -> None:
    with pytest.raises(ValueError, match="needs 2 to 2 players"):
        RockPaperScissors(players)


@pytest.mark.parametrize(
    ("move", "beats", "loses_to"),
    [
        (Move.ROCK, Move.SCISSORS, Move.PAPER),
        (Move.PAPER, Move.ROCK, Move.SCISSORS),
        (Move.SCISSORS, Move.PAPER, Move.ROCK),
    ],
)
def test_each_move_beats_and_loses_to(move: Move, beats: Move, loses_to: Move) -> None:
    assert move.beats is beats
    assert move.loses_to is loses_to


@pytest.mark.parametrize(
    ("first", "second", "wins"),
    [
        (Move.ROCK, Move.SCISSORS, (1, 0)),
        (Move.ROCK, Move.PAPER, (0, 1)),
        (Move.ROCK, Move.ROCK, (0, 0)),
        (Move.PAPER, Move.ROCK, (1, 0)),
        (Move.PAPER, Move.SCISSORS, (0, 1)),
        (Move.PAPER, Move.PAPER, (0, 0)),
        (Move.SCISSORS, Move.PAPER, (1, 0)),
        (Move.SCISSORS, Move.ROCK, (0, 1)),
        (Move.SCISSORS, Move.SCISSORS, (0, 0)),
    ],
)
def test_apply_scores_every_combination(
    first: Move, second: Move, wins: tuple[int, int]
) -> None:
    s = GAME.apply(
        state(),
        {0: Throw(move=first), 1: Throw(move=second)},
        random.Random(0),
    )
    assert s.wins == wins
    assert s.rounds == 1
    assert s.last == (first, second)


def test_apply_keeps_the_running_score() -> None:
    s = GAME.apply(
        state(wins=(1, 2), rounds=3),
        {0: Throw(move=Move.PAPER), 1: Throw(move=Move.ROCK)},
        random.Random(0),
    )
    assert s.wins == (2, 2)
    assert s.rounds == 4


@pytest.mark.parametrize("winner", [0, 1])
def test_outcome_at_target_wins(winner: int) -> None:
    wins = (TARGET_WINS, 0) if winner == 0 else (0, TARGET_WINS)
    s = state(wins=wins, rounds=TARGET_WINS)
    outcome = GAME.outcome(s)
    assert outcome is not None
    assert outcome.scores[winner] == 1.0
    assert outcome.winners == (winner,)
    assert GAME.to_move(s) == ()
    assert GAME.legal_actions(s, 0) == ()


def test_outcome_at_the_round_cap() -> None:
    outcome = GAME.outcome(state(wins=(2, 1), rounds=MAX_ROUNDS))
    assert outcome is not None
    assert outcome.scores == (1.0, 0.0)
    assert outcome.winners == (0,)
    assert outcome.reason == "Round limit reached, final score 2-1"


def test_out_of_turns_keeps_the_round_wins() -> None:
    outcome = GAME.out_of_turns(state(wins=(1, 2), rounds=5))
    assert outcome.scores == (1.0, 2.0)
    assert outcome.reason == "Turn limit reached, final score 1-2"


def test_observe_before_any_round() -> None:
    assert GAME.observe(state(), 0) == snapshot("""\
You are Player 1. Score: you 0, opponent 0 (first to 3 wins). Round 1. No rounds have been played yet. Choose one: rock (beats scissors, loses to paper), paper (beats rock, loses to scissors), scissors (beats paper, loses to rock).\
""")


def test_observe_after_a_round() -> None:
    s = state(wins=(1, 0), rounds=2, last=(Move.ROCK, Move.SCISSORS))
    assert GAME.observe(s, 0) == snapshot("""\
You are Player 1. Score: you 1, opponent 0 (first to 3 wins). Round 3. Last round: you played rock; your opponent played scissors; you won. Choose one: rock (beats scissors, loses to paper), paper (beats rock, loses to scissors), scissors (beats paper, loses to rock).\
""")
    assert "you lost" in GAME.observe(s, 1)
    tied = state(wins=(0, 0), rounds=1, last=(Move.PAPER, Move.PAPER))
    assert "you tied" in GAME.observe(tied, 0)
    over = state(wins=(TARGET_WINS, 0), rounds=3, last=(Move.ROCK, Move.SCISSORS))
    assert GAME.observe(over, 0).endswith("The match is over.")


def test_descriptions_and_keys() -> None:
    assert GAME.describe_action(Throw(move=Move.ROCK)) == "Play rock."
    assert GAME.describe_option(state(), 0, Throw(move=Move.PAPER)) == snapshot(
        "Play paper. Paper beats rock and loses to scissors."
    )
    assert GAME.action_key(Throw(move=Move.SCISSORS)) == "scissors"
    assert GAME.parse_action({"move": "rock"}) == Throw(move=Move.ROCK)
    with pytest.raises(ValidationError):
        GAME.parse_action({"move": "lizard"})
    assert GAME.player_label(0) == "Player 1"
    assert GAME.player_label(1) == "Player 2"
    assert list(GAME.bots()) == ["counter"]
    assert callable(GAME.renderer())


async def test_counter_bot_throws_at_random_first() -> None:
    decision = await CounterBot().act(ctx(state(), 0))
    assert decision.action in THROWS


async def test_counter_bot_beats_the_last_throw() -> None:
    s = state(rounds=1, last=(Move.ROCK, Move.ROCK))
    assert (await CounterBot().act(ctx(s, 0))).action == Throw(move=Move.PAPER)
    assert (await CounterBot().act(ctx(s, 1))).action == Throw(move=Move.PAPER)


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4])
async def test_counter_against_random_finishes(seed: int) -> None:
    match = Match(RockPaperScissors(), [CounterBot(), RandomBot()], seed=seed)
    outcome = await match.run()
    assert match.status is MatchStatus.FINISHED
    assert outcome is not None


async def test_counter_against_random_matches_the_docs() -> None:
    match = Match(RockPaperScissors(), [CounterBot(), RandomBot()], seed=1)
    outcome = await match.run()
    assert outcome is not None
    assert outcome.reason == "Player 1 reached 3 wins"
    assert [move.action["move"] for move in match.history] == [
        "rock", "rock", "paper", "rock", "paper", "rock", "paper", "rock",
    ]


async def test_play_hot_seat(user: User, service: MatchService) -> None:
    match = service.create("rock-paper-scissors", [HumanSpec(), HumanSpec()])
    await user.open(f"/match/{match.id}")
    await user.should_see("Player 1, choose:")
    await user.should_see("Player 2, choose:")
    await user.should_see("No rounds have been played yet.")
    await user.should_see("Round 1")
    user.find(marker="move-0-rock").click()
    user.find(marker="move-1-scissors").click()
    for _ in range(100):
        if isinstance(match.state, RockPaperScissorsState) and match.state.rounds:
            break
        await asyncio.sleep(0.01)
    s = match.state
    assert isinstance(s, RockPaperScissorsState)
    assert s.wins == (1, 0)
    assert s.last == (Move.ROCK, Move.SCISSORS)
    await user.should_see(
        "Last round: Player 1 played rock; Player 2 played scissors. Player 1 won."
    )
    await user.should_see("Round 2")
    await user.should_see("Player 1: 1")


async def test_renderer_skips_seats_that_cannot_act(
    user: User, service: MatchService
) -> None:
    match = service.create(
        "rock-paper-scissors", [HumanSpec(), HumanSpec()], start=False
    )
    match.thinking = {1}
    await user.open(f"/match/{match.id}")
    await user.should_see("Player 2, choose:")
    await user.should_not_see("Player 1, choose:")


@pytest.mark.parametrize(
    ("last", "heading", "detail"),
    [
        ((Move.ROCK, Move.PAPER), "Player 2 wins the round!", "Player 2 won."),
        ((Move.ROCK, Move.ROCK), "Tie round! Both played Rock.", "It was a tie."),
    ],
)
async def test_round_banner_shows_the_result(
    user: User,
    service: MatchService,
    last: tuple[Move, Move],
    heading: str,
    detail: str,
) -> None:
    match = service.create(
        "rock-paper-scissors", [HumanSpec(), HumanSpec()], start=False
    )
    match.state = state(rounds=1, last=last)
    await user.open(f"/match/{match.id}")
    await user.should_see(heading)
    await user.should_see(detail)


async def test_match_over_banner_names_the_winner(
    user: User, service: MatchService
) -> None:
    match = service.create(
        "rock-paper-scissors", [HumanSpec(), HumanSpec()], start=False
    )
    match.state = state(
        wins=(TARGET_WINS, 0),
        rounds=TARGET_WINS,
        last=(Move.ROCK, Move.SCISSORS),
    )
    await user.open(f"/match/{match.id}")
    await user.should_see("Player 1 wins the match!")
    await user.should_not_see("Player 1, choose:")


async def test_match_over_banner_shows_a_draw(
    user: User, service: MatchService
) -> None:
    match = service.create(
        "rock-paper-scissors", [HumanSpec(), HumanSpec()], start=False
    )
    match.state = state(
        rounds=MAX_ROUNDS,
        last=(Move.ROCK, Move.PAPER),
    )
    await user.open(f"/match/{match.id}")
    await user.should_see("Match over: it is a draw!")
