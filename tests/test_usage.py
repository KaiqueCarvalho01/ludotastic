"""Model usage and cost: per move, per match, stored, and shown."""

from decimal import Decimal
from pathlib import Path
from typing import override

import pytest
from nicegui import ui
from nicegui.testing import User
from typer.testing import CliRunner

from ludotastic import Decision, Match, Player, PlayerKind, RandomBot, TurnContext
from ludotastic.engine.usage import Usage, format_cost, format_tokens
from ludotastic.games.snake import Snake
from ludotastic.games.tictactoe import TicTacToe
from ludotastic.service import MatchService
from ludotastic.settings import get_settings

PRICED = Usage(requests=1, input_tokens=600, output_tokens=40, cost=Decimal("0.00002"))
UNPRICED = Usage(requests=1, input_tokens=100, output_tokens=10)


class Spender(Player):
    """Plays at random, reporting a fixed usage per move, like an AI would."""

    kind = PlayerKind.AI

    def __init__(self, usage: Usage, name: str = "spender") -> None:
        """Set the usage reported per move."""
        super().__init__(name)
        self.spend = usage

    @override
    async def act(self, ctx: TurnContext) -> Decision:
        return Decision(
            action=ctx.rng.choice(ctx.legal_actions),
            details={"model": "spender"},
            usage=self.spend,
        )


def test_usage_adds_up() -> None:
    total = Usage.total([PRICED, PRICED])
    assert total.requests == 2
    assert total.tokens == 1280
    assert total.cost == Decimal("0.00004")
    assert total.priced
    mixed = PRICED + UNPRICED
    assert mixed.cost == Decimal("0.00002")
    assert not mixed.priced
    assert (
        Usage(requests=2, input_tokens=200, output_tokens=20, cost=None, priced=False)
        == UNPRICED + UNPRICED
    )
    assert Usage() + Usage() == Usage()
    assert format_tokens(PRICED.tokens) == "640"
    assert format_cost(mixed.cost, priced=mixed.priced) == "≥ $0.00002"


async def test_match_usage_per_seat(service: MatchService) -> None:
    match = Match(TicTacToe(), [Spender(PRICED), RandomBot()], seed=1)
    await match.run()
    x_moves = sum(m.seat == 0 for m in match.history)
    assert match.usage(0).requests == x_moves
    assert match.usage(0).cost == PRICED.cost * x_moves  # ty: ignore[unsupported-operator]
    assert match.usage(1) == Usage()
    assert match.usage() == match.usage(0)

    service.store.save(match)
    record = service.store.get(match.id)
    assert record is not None
    assert record.usage(0) == match.usage(0)
    assert record.usage() == match.usage()


async def test_stats_count_cost_and_solo_scores(service: MatchService) -> None:
    for seed in range(2):
        service.store.save(await _played(Match(Snake(), [Spender(PRICED)], seed=seed)))
    (stats,) = service.store.stats(game_id="snake")
    assert stats.played == 2
    assert stats.wins == stats.draws == stats.losses == 0  # Solo: just scores.
    assert stats.usage.requests > 0
    assert stats.usage.cost is not None


async def _played(match: Match) -> Match:
    await match.run()
    return match


async def test_meter_on_the_match_page(user: User, service: MatchService) -> None:
    match = Match(TicTacToe(), [Spender(PRICED, "a"), Spender(UNPRICED, "b")], seed=2)
    service.matches[match.id] = match
    await match.run()
    await user.open(f"/match/{match.id}")
    costs = sorted(label.text for label in user.find(marker="cost").elements)  # ty: ignore[unresolved-attribute]
    total = match.usage()
    # Seat a is priced, seat b is not, so the total is a lower bound.
    assert costs == sorted(
        [format_cost(match.usage(0).cost), "n/a", format_cost(total.cost, priced=False)]
    )
    moves = user.find(marker="moves").elements.pop()
    assert isinstance(moves, ui.expansion)
    moves.open()
    await user.should_see("1. X:")


async def test_cost_in_history_and_stats(user: User, service: MatchService) -> None:
    match = await _played(Match(TicTacToe(), [Spender(PRICED), RandomBot()], seed=3))
    service.store.save(match)
    await user.open("/history")
    table = user.find(ui.table).elements.pop()
    assert isinstance(table, ui.table)
    assert table.rows[0]["ai cost"] == format_cost(match.usage().cost)
    await user.open("/stats")
    table = user.find(ui.table).elements.pop()
    assert isinstance(table, ui.table)
    by_player = {row["player"]: row for row in table.rows}
    assert by_player["ai:spender"]["cost"] == format_cost(match.usage(0).cost)
    assert by_player["bot:random"]["cost"] == ""


def test_cli_prints_cost(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from ludotastic import cli  # noqa: PLC0415

    monkeypatch.setenv("LUDOTASTIC_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LUDOTASTIC_UPDATE_PRICES", "false")
    get_settings.cache_clear()
    monkeypatch.setattr(
        "ludotastic.service.build_player",
        lambda game, spec: Spender(PRICED) if spec.kind == "ai" else RandomBot(),
    )
    result = CliRunner().invoke(
        cli.app, ["play", "tictactoe", "test", "bot:random", "--quiet"]
    )
    get_settings.cache_clear()
    assert result.exit_code == 0, result.output
    assert "tokens" in result.output
    assert "requests" in result.output


@pytest.mark.parametrize("enabled", [True, False])
async def test_prices_update_with_the_server(
    service: MatchService, monkeypatch: pytest.MonkeyPatch, *, enabled: bool
) -> None:
    from nicegui.testing.general import nicegui_reset_globals  # noqa: PLC0415

    from ludotastic.web import create_app  # noqa: PLC0415

    events: list[str] = []

    class Updater:
        def stop(self) -> None:
            events.append("stopped")

    def start() -> Updater:
        events.append("started")
        return Updater()

    monkeypatch.setattr("ludotastic.web.prices.update_in_background", start)
    service.settings = service.settings.model_copy(update={"update_prices": enabled})
    with nicegui_reset_globals():
        app = create_app(service)
        async with app.router.lifespan_context(app):
            assert events == (["started"] if enabled else [])
    assert events == (["started", "stopped"] if enabled else [])
