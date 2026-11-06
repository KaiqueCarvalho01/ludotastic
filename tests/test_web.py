"""The NiceGUI playground, driven by a simulated user."""

__all__: tuple[str, ...] = ()

import asyncio
from typing import cast

import pytest
from nicegui import ui
from nicegui.elements.dark_mode import DarkMode
from nicegui.testing import User

from ludotastic.engine.match import Match, MatchStatus
from ludotastic.games.tictactoe import TicTacToeState
from ludotastic.service import BotSpec, HumanSpec, MatchService


def _value(element: DarkMode) -> bool | None:
    # NiceGUI's bindable `value` is untyped.
    return cast("bool | None", element.value)


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
    await user.should_see("Seed 2")
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
            details={"model": "test", "confidence": {"response": 0.25}},
        )
    )
    match.history.append(
        MoveRecord(
            turn=2,
            seat=0,
            action={"cell": 2},
            description="Only move",
            seconds=0,
            details={"mode": "choice", "forced": True},
        )
    )
    match.history.append(
        MoveRecord(turn=3, seat=1, action={"cell": 3}, description="Plain", seconds=1)
    )
    match.history.append(
        MoveRecord(
            turn=4,
            seat=0,
            action={"cell": 4},
            description="Unsure",
            seconds=1,
            details={"model": "test"},
        )
    )
    await user.open(f"/match/{match.id}")
    await user.should_see("...")
    await user.should_not_see("1. X: Waited")  # Not built until opened.
    moves = user.find(marker="moves").elements.pop()
    assert isinstance(moves, ui.expansion)
    assert moves.props["caption"] == "5 moves"
    moves.open()
    await user.should_see("1. X: Waited")
    await user.should_see("2. O: Thought")
    await user.should_see("25%")
    await user.should_see("3. X: Only move")
    await user.should_see("4. O: Plain")
    await user.should_see("5. X: Unsure")
    match.history.clear()
    match.state = match.state  # Nothing new: an open list is left alone.
    await match._notify()  # noqa: SLF001
    await user.should_see("No moves yet.")
    assert moves.props["caption"] == "0 moves"


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


async def test_history_of_uninstalled_game(user: User, service: MatchService) -> None:
    match = service.create("tictactoe", [BotSpec(), BotSpec()], seed=1)
    await match.start()
    record = service.store.get(match.id)
    assert record is not None
    record.game_id = "gone"
    from sqlmodel import Session  # noqa: PLC0415

    with Session(service.store.engine) as session:
        session.merge(record)
        session.commit()
    await user.open(f"/history/{match.id}")
    await user.should_see("The game 'gone' is not installed.")


async def test_dark_mode_toggle(
    user: User, service: MatchService, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def browser_is_dark(code: str) -> bool:
        assert code == "Quasar.Dark.isActive"
        return True

    monkeypatch.setattr(ui, "run_javascript", browser_is_dark)
    await user.open("/")
    dark = user.find(DarkMode).elements.pop()
    assert isinstance(dark, DarkMode)
    assert dark.value is None  # Follows the system by default.
    # From auto, the first click flips what the browser shows: dark, so light.
    for expected in (False, True, False):
        user.find(marker="dark-toggle").click()
        for _ in range(50):
            if _value(dark) is expected:
                break
            await asyncio.sleep(0.01)
        assert dark.value is expected
