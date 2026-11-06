"""The engine: games, matches, players and the registry."""

import asyncio
import random
from collections.abc import Callable, Mapping, Sequence
from typing import override

import pytest
from pydantic import BaseModel, ValidationError

from ludotastic import (
    ENTRY_POINT_GROUP,
    Decision,
    Game,
    GameInfo,
    GameRegistry,
    HumanPlayer,
    Match,
    MatchStatus,
    Outcome,
    Player,
    PlayerKind,
    RandomBot,
    Timing,
    TurnContext,
    registry,
)
from ludotastic.games.tictactoe import Place, TicTacToe


class Counter(BaseModel):
    """How far each player has got."""

    ticks: int = 0
    positions: tuple[int, ...] = (0, 0)


class Step(BaseModel):
    """Move forward."""

    by: int = 1


class Race(Game[Counter, Step]):
    """Both players move at once, on a clock, to reach 3 first."""

    info = GameInfo(
        id="race",
        name="Race",
        description="Run!",
        min_players=2,
        max_players=2,
        timing=Timing.TICK,
        tick_seconds=0.05,
    )
    state_type = Counter
    action_type = Step

    @override
    def initial_state(self, rng: random.Random) -> Counter:
        return Counter()

    @override
    def to_move(self, state: Counter) -> Sequence[int]:
        return (0, 1)

    @override
    def legal_actions(self, state: Counter, player: int) -> Sequence[Step]:
        return (Step(by=0), Step(by=1))

    @override
    def apply(
        self,
        state: Counter,
        actions: Mapping[int, Step],
        rng: random.Random,
    ) -> Counter:
        positions = tuple(
            pos + (actions[i].by if i in actions else 0)
            for i, pos in enumerate(state.positions)
        )
        return Counter(ticks=state.ticks + 1, positions=positions)

    @override
    def outcome(self, state: Counter) -> Outcome | None:
        if max(state.positions) >= 3:
            top = max(state.positions)
            scores = tuple(1.0 if p == top else 0.0 for p in state.positions)
            return Outcome(scores=scores, reason="Finish line")
        return None

    @override
    def observe(self, state: Counter, player: int) -> str:
        return f"You are at {state.positions[player]}"

    @override
    def default_action(self, state: Counter, player: int) -> Step | None:
        return Step(by=0) if player == 0 else None


class Runner(Player):
    """Always steps forward."""

    kind = PlayerKind.BOT

    @override
    async def act(self, ctx: TurnContext) -> Decision:
        return Decision(action=Step(by=1))


class Sleeper(Player):
    """Never answers in time."""

    kind = PlayerKind.BOT

    @override
    async def act(self, ctx: TurnContext) -> Decision:
        await asyncio.sleep(10)
        raise AssertionError  # pragma: no cover


class Cheater(Player):
    """Plays an occupied cell."""

    kind = PlayerKind.BOT

    @override
    async def act(self, ctx: TurnContext) -> Decision:
        return Decision(action=Place(cell=0))


class Crasher(Player):
    """Raises."""

    kind = PlayerKind.BOT

    @override
    async def act(self, ctx: TurnContext) -> Decision:
        msg = "boom"
        raise RuntimeError(msg)


async def until(condition: Callable[[], bool]) -> None:
    """Wait for `condition` to hold."""
    while not condition():
        await asyncio.sleep(0)


def test_game_info_validation() -> None:
    with pytest.raises(ValidationError, match="max_players"):
        GameInfo(id="x", name="X", description="", min_players=3, max_players=2)
    with pytest.raises(ValidationError, match="action mode"):
        GameInfo(id="x", name="X", description="", action_modes=())
    with pytest.raises(ValidationError):
        GameInfo(id="Bad Id", name="X", description="")


def test_outcome_winners() -> None:
    assert Outcome(scores=(1, 1, 0), reason="").winners == (0, 1)


def test_game_defaults() -> None:
    game = Race()
    assert game.player_label(1) == "Player 2"
    assert game.action_key(Step(by=2)) == '{"by": 2}'
    assert game.describe_action(Step(by=2)) == '{"by": 2}'
    assert game.bots() == {}
    assert game.renderer() is None
    assert game.ai_tools(Counter(), 0) == ()
    assert (
        TicTacToe().default_action(TicTacToe().initial_state(random.Random()), 0)
        is None
    )


def test_registry_loads_entry_points() -> None:
    assert ENTRY_POINT_GROUP == "ludotastic.games"
    assert registry["tictactoe"] is TicTacToe
    assert "tictactoe" in list(registry)
    assert len(registry) >= 1
    assert registry.errors == {}


def test_registry_register() -> None:
    games = GameRegistry(group="ludotastic.tests.none")
    assert games.register(Race) is Race
    games.register(Race)
    assert list(games) == ["race"]

    class Impostor(Race):
        pass

    with pytest.raises(ValueError, match="taken"):
        games.register(Impostor)
    with pytest.raises(TypeError):
        games.register(int)  # ty: ignore[invalid-argument-type]


def test_registry_reports_broken_entry_points(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys  # noqa: PLC0415
    from importlib.metadata import EntryPoint  # noqa: PLC0415

    broken = EntryPoint(name="broken", value="ludotastic.nope:Nope", group="g")
    module = sys.modules["ludotastic.engine.registry"]
    monkeypatch.setattr(module, "entry_points", lambda group: [broken])
    games = GameRegistry(group="g")
    assert len(games) == 0
    assert "ModuleNotFoundError" in games.errors["broken"]


def test_match_needs_right_player_count() -> None:
    with pytest.raises(ValueError, match="set up for 2"):
        Match(TicTacToe(), [RandomBot()])


async def test_match_records_history_and_notifies() -> None:
    match = Match(TicTacToe(), [RandomBot(), RandomBot()], seed=7)
    seen: list[MatchStatus] = []
    unsubscribe = match.subscribe(lambda m: seen.append(m.status))

    async def async_listener(_: Match) -> None:
        pass

    match.subscribe(async_listener)
    outcome = await match.run()
    unsubscribe()
    assert outcome is not None
    assert match.done
    assert match.history
    assert match.turn == len(match.history)
    assert seen[0] is MatchStatus.RUNNING
    assert seen[-1] is MatchStatus.FINISHED
    assert [s.label for s in match.seats] == ["X", "O"]


async def test_same_seed_same_match() -> None:
    first = Match(TicTacToe(), [RandomBot(), RandomBot()], seed=3)
    second = Match(TicTacToe(), [RandomBot(), RandomBot()], seed=3)
    await first.run()
    await second.run()
    assert [m.action for m in first.history] == [m.action for m in second.history]


async def test_failing_listener_does_not_break_the_match() -> None:
    match = Match(TicTacToe(), [RandomBot(), RandomBot()], seed=1)

    def broken(_: Match) -> None:
        raise RuntimeError

    match.subscribe(broken)
    assert await match.run() is not None


async def test_illegal_move_forfeits() -> None:
    match = Match(TicTacToe(), [Cheater("a"), Cheater("b")])
    outcome = await match.run()
    assert outcome is not None
    assert outcome.scores == (1.0, 0.0)
    assert "illegal" in outcome.reason


async def test_crash_forfeits() -> None:
    outcome = await Match(TicTacToe(), [Crasher("c"), RandomBot()]).run()
    assert outcome is not None
    assert outcome.scores == (0.0, 1.0)
    assert "boom" in outcome.reason


async def test_step_timeout_forfeits() -> None:
    match = Match(TicTacToe(), [RandomBot(), Sleeper("s")], turn_timeout=0.01)
    outcome = await match.run()
    assert outcome is not None
    assert outcome.scores == (1.0, 0.0)
    assert "ran out of time" in outcome.reason


def ready(name: str) -> HumanPlayer:
    """A person who has already pressed a key, and then goes idle."""
    human = HumanPlayer(name)
    human.submit(Step(by=0))
    return human


async def test_max_turns() -> None:
    match = Match(Race(), [ready("a"), ready("b")], max_turns=2)
    outcome = await match.run()
    assert outcome is not None
    assert outcome.reason == "Turn limit reached"
    assert match.turn == 2
    # The first tick waits for each person; the second times them out.
    assert [m.forced for m in match.history] == [False, False, True]


async def test_tick_game_and_delay() -> None:
    match = Match(Race(), [Runner("r"), ready("h")], delay=0.001)
    outcome = await match.run()
    assert outcome is not None
    assert outcome.scores == (1.0, 0.0)
    assert match.state.positions == (3, 0)  # ty: ignore[unresolved-attribute]


class Slowpoke(Player):
    """A bot slower than a tick, but not forever."""

    kind = PlayerKind.BOT

    @override
    async def act(self, ctx: TurnContext) -> Decision:
        await asyncio.sleep(Race.info.tick_seconds * 2)
        return Decision(action=Step(by=1))


async def test_ticks_wait_for_bots_and_ai() -> None:
    """Only people are held to the clock; a slow bot never misses a tick."""
    match = Match(Race(), [Slowpoke("slow"), ready("h")])
    outcome = await match.run()
    assert outcome is not None
    assert outcome.scores == (1.0, 0.0)
    assert [m.forced for m in match.history if m.seat == 0] == [False] * 3


async def test_ticks_keep_a_steady_pace_for_people() -> None:
    human = ready("h")
    loop = asyncio.get_running_loop()
    started = loop.time()
    await Match(Race(), [Runner("a"), human]).run()
    # Three ticks; the first waits for the person instead of the clock.
    assert loop.time() - started >= 2 * Race.info.tick_seconds


async def test_bot_only_ticks_run_flat_out() -> None:
    loop = asyncio.get_running_loop()
    started = loop.time()
    await Match(Race(), [Runner("a"), Runner("b")]).run()
    assert loop.time() - started < Race.info.tick_seconds


async def test_human_player() -> None:
    match = Match(TicTacToe(), [HumanPlayer(), RandomBot()], seed=0)
    task = match.start()
    assert match.start() is task
    human = match.players[0]
    assert isinstance(human, HumanPlayer)
    await until(lambda: human.waiting)
    with pytest.raises(TypeError):
        match.submit(1, Place(cell=0))
    with pytest.raises(ValueError, match="Illegal"):
        match.submit(0, Place(cell=4).model_copy(update={"cell": 9}))
    match.submit(0, {"cell": 4})
    await until(lambda: human.waiting)
    match.players[1] = HumanPlayer()
    with pytest.raises(ValueError, match="not seat 1"):
        match.submit(1, Place(cell=0))
    assert match.state.board[4] == "X"  # ty: ignore[unresolved-attribute]
    match.abort("bye")
    match.abort("twice")
    assert await task is None
    assert match.status is MatchStatus.ABORTED
    assert match.error == "bye"


async def test_human_can_act_ahead_in_tick_games() -> None:
    human = HumanPlayer()
    human.submit(Step(by=1))
    match = Match(Race(), [human, Runner("r")])
    ctx = TurnContext(
        game=match.game,
        state=match.state,
        player=0,
        legal_actions=[],
        turn=0,
        rng=random.Random(),
    )
    assert (await human.act(ctx)).action == Step(by=1)
    match.submit(0, Step(by=1))
    human.timeout()  # A tick ending keeps the key press for the next one.
    assert (await human.act(ctx)).action == Step(by=1)
    match.submit(0, Step(by=1))
    human.cancel()  # The match ending drops it.
    assert not human.waiting
    task = asyncio.create_task(human.act(ctx))
    await asyncio.sleep(0)
    assert human.waiting
    human.timeout()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_cancelling_the_task_aborts() -> None:
    match = Match(TicTacToe(), [HumanPlayer(), RandomBot()])
    task = asyncio.create_task(match.run())
    await asyncio.sleep(0.01)
    task.cancel()
    assert await task is None
    assert match.status is MatchStatus.ABORTED
    assert match.error == "Cancelled"


async def test_game_errors_abort(monkeypatch: pytest.MonkeyPatch) -> None:
    game = TicTacToe()

    def broken(*_: object) -> None:
        msg = "bad rules"
        raise RuntimeError(msg)

    monkeypatch.setattr(game, "apply", broken)
    match = Match(game, [RandomBot(), RandomBot()])
    assert await match.run() is None
    assert match.status is MatchStatus.ABORTED
    assert match.error == "RuntimeError: bad rules"
