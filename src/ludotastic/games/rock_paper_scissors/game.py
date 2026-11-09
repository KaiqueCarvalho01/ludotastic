"""Rock-Paper-Scissors rules."""

__all__: tuple[str, ...] = (
    "MAX_ROUNDS",
    "TARGET_WINS",
    "CounterBot",
    "Move",
    "RockPaperScissors",
    "RockPaperScissorsState",
    "Throw",
)

import random
from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import TYPE_CHECKING, Final, override

from pydantic import BaseModel, ConfigDict

from ludotastic.engine.game import ActionMode, BotFactory, Game, GameInfo, Outcome
from ludotastic.engine.players import Decision, Player, PlayerKind, TurnContext
from ludotastic.types import Count, Seat

if TYPE_CHECKING:
    from ludotastic.engine.render import Renderer

TARGET_WINS: Final = 3
"""Round wins needed to take the match."""

MAX_ROUNDS: Final = 20
"""Round cap, so two deterministic players cannot play forever."""


class Move(StrEnum):
    """One of the three throws."""

    ROCK = "rock"
    PAPER = "paper"
    SCISSORS = "scissors"

    @property
    def beats(self) -> Move:
        """The move this one defeats.

        Examples:
            >>> Move.ROCK.beats is Move.SCISSORS
            True
            >>> Move.PAPER.beats is Move.ROCK
            True
            >>> Move.SCISSORS.beats is Move.PAPER
            True
        """
        return _BEATS[self]

    @property
    def loses_to(self) -> Move:
        """The move that defeats this one.

        Examples:
            >>> Move.ROCK.loses_to is Move.PAPER
            True
            >>> Move.PAPER.loses_to is Move.SCISSORS
            True
            >>> Move.SCISSORS.loses_to is Move.ROCK
            True
        """
        return self.beats.beats


_BEATS: Final = {
    Move.ROCK: Move.SCISSORS,
    Move.PAPER: Move.ROCK,
    Move.SCISSORS: Move.PAPER,
}


class Throw(BaseModel):
    """Throw one of the three moves."""

    model_config = ConfigDict(frozen=True, use_attribute_docstrings=True)

    move: Move
    """The move to throw: rock, paper or scissors."""


class RockPaperScissorsState(BaseModel):
    """The score, the round number and the last round's throws."""

    model_config = ConfigDict(frozen=True)

    wins: tuple[Count, Count] = (0, 0)
    """Round wins for player 1 and player 2."""
    rounds: Count = 0
    """Rounds played so far."""
    last: tuple[Move | None, Move | None] = (None, None)
    """The last round's throws, or `None` before the first round."""


def _by_round_wins(state: RockPaperScissorsState, reason: str) -> Outcome:
    """Win for whoever has more round wins, or a draw when level."""
    first, second = state.wins
    if first == second:
        return Outcome.draw(2, reason)
    return Outcome.win(2, 0 if first > second else 1, reason)


class RockPaperScissors(Game[RockPaperScissorsState, Throw]):
    """Two players throw at once; the winning throw scores the round."""

    info = GameInfo(
        id="rock-paper-scissors",
        name="Rock-Paper-Scissors",
        description="Two players throw simultaneously; the winning throw scores.",
        min_players=2,
        max_players=2,
        action_modes=(ActionMode.CHOICE, ActionMode.STRUCTURED, ActionMode.TOOLS),
        tags=("classic", "turn-based", "simultaneous"),
    )
    rules = (
        "Two players throw simultaneously every round: rock, paper or scissors. "
        "Rock beats scissors, scissors beats paper and paper beats rock. A round "
        "is a tie when both players throw the same move. The first player to "
        f"{TARGET_WINS} round wins takes the match. If {MAX_ROUNDS} rounds pass "
        "without a winner, the match ends with the round wins as the score."
    )
    state_type = RockPaperScissorsState
    action_type = Throw

    @override
    def initial_state(self, rng: random.Random) -> RockPaperScissorsState:
        """Start with no wins, no rounds and no last throws."""
        return RockPaperScissorsState()

    @override
    def to_move(self, state: RockPaperScissorsState) -> Sequence[Seat]:
        """Both seats throw in every round."""
        return () if self.outcome(state) is not None else (0, 1)

    @override
    def legal_actions(
        self, state: RockPaperScissorsState, player: Seat
    ) -> Sequence[Throw]:
        """Every throw, while the match is not over."""
        del player
        if self.outcome(state) is not None:
            return ()
        return tuple(Throw(move=move) for move in Move)

    @override
    def apply(
        self,
        state: RockPaperScissorsState,
        actions: Mapping[int, Throw],
        rng: random.Random,
    ) -> RockPaperScissorsState:
        """Score the round from both throws."""
        del rng
        first, second = actions[0].move, actions[1].move
        wins_1, wins_2 = state.wins
        if first.beats is second:
            wins_1 += 1
        elif second.beats is first:
            wins_2 += 1
        return RockPaperScissorsState(
            wins=(wins_1, wins_2),
            rounds=state.rounds + 1,
            last=(first, second),
        )

    @override
    def outcome(self, state: RockPaperScissorsState) -> Outcome | None:
        """Over at the target wins or at the round cap."""
        for seat in (0, 1):
            if state.wins[seat] >= TARGET_WINS:
                return Outcome.win(
                    2, seat, f"Player {seat + 1} reached {TARGET_WINS} wins"
                )
        if state.rounds >= MAX_ROUNDS:
            return _round_wins(
                state,
                f"Round limit reached, final score {state.wins[0]}-{state.wins[1]}",
            )
        return None

    @override
    def out_of_turns(self, state: RockPaperScissorsState) -> Outcome:
        """Keep the round wins as the score."""
        return _round_wins(
            state,
            f"Turn limit reached, final score {state.wins[0]}-{state.wins[1]}",
        )

    @override
    def observe(self, state: RockPaperScissorsState, player: Seat) -> str:
        """The score, the round and the last result; never a future throw."""
        opponent = 1 - player
        parts = [
            f"You are {self.player_label(player)}.",
            (
                f"Score: you {state.wins[player]}, "
                f"opponent {state.wins[opponent]} (first to {TARGET_WINS} wins)."
            ),
            f"Round {state.rounds + 1}.",
        ]
        own, theirs = state.last[player], state.last[opponent]
        if own is None or theirs is None:
            parts.append("No rounds have been played yet.")
        else:
            if own.beats is theirs:
                result = "you won"
            elif theirs.beats is own:
                result = "you lost"
            else:
                result = "you tied"
            parts.append(
                f"Last round: you played {own}; your opponent played {theirs}; "
                f"{result}."
            )
        if self.outcome(state) is None:
            options = ", ".join(
                f"{move} (beats {move.beats}, loses to {move.loses_to})"
                for move in Move
            )
            parts.append(f"Choose one: {options}.")
        else:
            parts.append("The match is over.")
        return " ".join(parts)

    @override
    def describe_action(self, action: Throw) -> str:
        """Name the throw.

        Examples:
            >>> RockPaperScissors().describe_action(Throw(move=Move.ROCK))
            'Play rock.'
        """
        return f"Play {action.move}."

    @override
    def describe_option(
        self, state: RockPaperScissorsState, player: Seat, action: Throw
    ) -> str:
        """Play the throw and state what it beats and loses to.

        Examples:
            >>> RockPaperScissors().describe_option(
            ...     RockPaperScissorsState(), 0, Throw(move=Move.PAPER)
            ... )
            'Play paper. Paper beats rock and loses to scissors.'
        """
        del state, player
        move = action.move
        return (
            f"Play {move}. {move.value.title()} beats {move.beats} "
            f"and loses to {move.loses_to}."
        )

    @override
    def action_key(self, action: Throw) -> str:
        """The move's name.

        Examples:
            >>> RockPaperScissors().action_key(Throw(move=Move.SCISSORS))
            'scissors'
        """
        return str(action.move)

    @override
    def player_label(self, player: Seat) -> str:
        """`Player 1` or `Player 2`."""
        return f"Player {player + 1}"

    @override
    def bots(self) -> Mapping[str, BotFactory]:
        """The counter bot beats whatever the opponent threw last."""
        return {"counter": CounterBot}

    @override
    def renderer(self) -> Renderer:
        """A scoreboard and three buttons per human seat."""
        from ludotastic.games.rock_paper_scissors.ui import render  # noqa: PLC0415

        return render


class CounterBot(Player):
    """Plays the throw that beats the opponent's last throw."""

    kind = PlayerKind.BOT

    def __init__(self, name: str = "counter") -> None:
        """Name the player."""
        super().__init__(name)

    @override
    async def act(self, ctx: TurnContext) -> Decision:
        """Counter the opponent, or pick at random on the first round."""
        state = ctx.state
        assert isinstance(state, RockPaperScissorsState)  # noqa: S101
        last = state.last[1 - ctx.player]
        move = ctx.rng.choice(tuple(Move)) if last is None else last.loses_to
        return Decision(action=Throw(move=move))
