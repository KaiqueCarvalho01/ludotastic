"""The NiceGUI playground, driven by a simulated user."""

import asyncio

import pytest
from nicegui import ui
from nicegui.testing import User

from ludotastic.engine.match import Match, MatchStatus
from ludotastic.games.tictactoe import TicTacToeState
from ludotastic.service import BotSpec, HumanSpec, MatchService


def _settled(match: Match) -> bool:
    return match.done or 0 in match.thinking


async def test_games_page(user: User) -> None:
    await user.open("/")
    await user.should_see("Tic-Tac-Toe")
    user.find(marker="play-tictactoe").click()
    await user.should_see("Start match")
    await user.should_see("X goes first")


async def test_unknown_pages(user: User) -> None:
    await user.open("/play/nope")
    await user.should_see("Unknown game: nope")
    await user.open("/match/nope")
    await user.should_see("no longer live")
    await user.open("/history/nope")
    await user.should_see("No stored match")


async def test_play_against_minimax(user: User, service: MatchService) -> None:
    await user.open("/play/tictactoe")
    user.find(marker="kind-1").click()
    toggle = user.find(marker="kind-1").elements.pop()
    assert isinstance(toggle, ui.toggle)
    toggle.set_value("bot")
    user.find(marker="start").click()
    await user.should_see("X to move (your turn)")
    (match,) = service.live()

    for _ in range(5):
        if match.done:
            break
        state = match.state
        assert isinstance(state, TicTacToeState)
        free = next(i for i, mark in enumerate(state.board) if mark is None)
        user.find(marker=f"cell-{free}").click()
        for _ in range(100):
            if _settled(match):
                break
            await asyncio.sleep(0.01)
        await asyncio.sleep(0.15)

    assert match.status is MatchStatus.FINISHED
    await user.should_see("O won")


async def test_ai_vs_ai_and_abort(user: User, service: MatchService) -> None:
    await user.open("/play/tictactoe")
    toggle = user.find(marker="kind-0").elements.pop()
    assert isinstance(toggle, ui.toggle)
    toggle.set_value("ai")
    user.find(marker="start").click()
    await user.should_see("Players")
    await user.should_see("test")
    (match,) = list(service.matches.values())
    await match.start()
    await user.should_see("Moves")


async def test_abort_from_the_page(user: User, service: MatchService) -> None:
    match = service.create("tictactoe", [HumanSpec(), HumanSpec()])
    await user.open(f"/match/{match.id}")
    await user.should_see("X to move")
    await user.open("/live")
    await user.should_see("Tic-Tac-Toe")
    await user.open(f"/match/{match.id}")
    user.find("Abort").click()
    await user.should_see("Aborted")


async def test_history_and_stats(user: User, service: MatchService) -> None:
    await user.open("/stats")
    await user.should_see("Play some matches first")
    await user.open("/live")
    await user.should_see("Nothing is being played")
    match = service.create("tictactoe", [BotSpec(bot="minimax"), BotSpec()], seed=2)
    await match.start()
    await user.open("/history")
    table = user.find(ui.table).elements.pop()
    assert isinstance(table, ui.table)
    assert table.rows[0]["id"] == match.id
    await user.open(f"/history/{match.id}")
    await user.should_see("X got three in a row")
    await user.open("/stats")
    table = user.find(ui.table).elements.pop()
    assert isinstance(table, ui.table)
    assert {row["player"] for row in table.rows} == {"bot:minimax", "bot:random"}


async def test_generic_renderer(user: User, service: MatchService) -> None:
    from ludotastic.games.tictactoe import TicTacToe  # noqa: PLC0415

    match = service.create("tictactoe", [HumanSpec(), BotSpec()], start=False)
    match.game.renderer = lambda: None
    assert isinstance(match.game, TicTacToe)
    match.start()
    await user.open(f"/match/{match.id}")
    await user.should_see("Place your mark in the center (cell 4).")
    user.find("Place your mark in the center (cell 4).").click()
    for _ in range(100):
        if match.history:
            break
        await asyncio.sleep(0.01)
    assert match.state.board[4] == "X"  # ty: ignore[unresolved-attribute]


async def test_create_app_serves_ui_and_api(service: MatchService) -> None:
    import httpx2  # noqa: PLC0415
    from nicegui.testing.general import nicegui_reset_globals  # noqa: PLC0415

    from ludotastic.web import create_app  # noqa: PLC0415

    with nicegui_reset_globals():
        app = create_app(service)
        async with app.router.lifespan_context(app):
            transport = httpx2.ASGITransport(app)
            async with httpx2.AsyncClient(
                transport=transport, base_url="http://t"
            ) as c:
                assert (await c.get("/api/games")).status_code == 200
                assert (await c.get("/")).status_code == 200


async def test_failed_start_is_reported(user: User, service: MatchService) -> None:
    await user.open("/play/tictactoe")
    model = user.find(marker="model-1").elements.pop()
    assert isinstance(model, ui.select)
    model.set_value("nope:nothing")
    user.find(marker="start").click()
    await user.should_see("Could not start the match")
    assert service.matches == {}


async def test_rejected_click_is_reported(user: User, service: MatchService) -> None:
    match = service.create("tictactoe", [HumanSpec(), HumanSpec()])
    await user.open(f"/match/{match.id}")
    await user.should_see("X to move")
    match.state = match.state.model_copy(update={"board": ("O",) + (None,) * 8})
    user.find(marker="cell-0").click()
    await user.should_see("Illegal action")


async def test_forced_moves_and_details(user: User, service: MatchService) -> None:
    from ludotastic.engine.match import MoveRecord  # noqa: PLC0415

    match = service.create("tictactoe", [HumanSpec(), HumanSpec()], start=False)
    match.history.append(
        MoveRecord(
            turn=0,
            seat=0,
            action={"cell": 0},
            description="Waited",
            seconds=1,
            forced=True,
        )
    )
    match.history.append(
        MoveRecord(
            turn=1,
            seat=1,
            action={"cell": 1},
            description="Thought",
            seconds=1,
            details={"model": "test"},
        )
    )
    await user.open(f"/match/{match.id}")
    await user.should_see("1. X: Waited")
    await user.should_see("2. O: Thought")
    await user.should_see("...")


async def test_no_games_and_broken_plugins(
    user: User, service: MatchService, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ludotastic import GameRegistry  # noqa: PLC0415

    games = GameRegistry(group="ludotastic.tests.none")
    monkeypatch.setattr(games, "_errors", {"broken": "ImportError: nope"})
    monkeypatch.setattr(games, "_loaded", True)
    service.games = games
    await user.open("/")
    await user.should_see("No games installed.")
    await user.should_see("Could not load broken: ImportError: nope")


async def test_generic_renderer_skips_other_seats(
    user: User, service: MatchService
) -> None:
    match = service.create("tictactoe", [BotSpec(), HumanSpec()], start=False)
    match.game.renderer = lambda: None
    match.thinking = {0}
    await user.open(f"/match/{match.id}")
    await user.should_see("X to move")
    await user.should_not_see("Place your mark in the center (cell 4).")
