"""The match service, storage and settings."""

import asyncio

import pytest

from ludotastic import ActionMode, AIPlayer, HumanPlayer, MatchStatus, RandomBot
from ludotastic.games.tictactoe import MinimaxBot
from ludotastic.service import AISpec, BotSpec, HumanSpec, MatchService
from ludotastic.settings import Settings, get_settings
from ludotastic.storage import Store


async def test_create_and_store(service: MatchService) -> None:
    match = service.create("tictactoe", [BotSpec(bot="minimax"), BotSpec()], seed=5)
    assert isinstance(match.players[0], MinimaxBot)
    assert isinstance(match.players[1], RandomBot)
    assert service.get(match.id) is match
    assert service.live() == [match]
    await match.start()
    assert service.live() == []
    record = service.store.get(match.id)
    assert record is not None
    assert record.status == "finished"
    assert record.seed == 5
    assert record.turns == match.turn
    assert len(record.history) == len(match.history)
    service.forget_finished()
    assert service.get(match.id) is None


async def test_build_players(service: MatchService) -> None:
    match = service.create(
        "tictactoe",
        [HumanSpec(name="Ann"), AISpec(model="test", mode=ActionMode.TOOLS)],
        start=False,
    )
    human, ai = match.players
    assert isinstance(human, HumanPlayer)
    assert human.name == "Ann"
    assert isinstance(ai, AIPlayer)
    assert ai.mode is ActionMode.TOOLS
    assert match.delay == 0.0


def test_bad_specs(service: MatchService) -> None:
    with pytest.raises(KeyError):
        service.create("nope", [BotSpec()])
    with pytest.raises(ValueError, match="no bot"):
        service.create("tictactoe", [BotSpec(bot="ghost"), BotSpec()])


def test_unsupported_mode(
    service: MatchService, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ludotastic.games.tictactoe import TicTacToe  # noqa: PLC0415

    info = TicTacToe.info.model_copy(update={"action_modes": (ActionMode.CHOICE,)})
    monkeypatch.setattr(TicTacToe, "info", info)
    with pytest.raises(ValueError, match="does not support"):
        service.create(
            "tictactoe", [AISpec(model="test", mode=ActionMode.TOOLS), BotSpec()]
        )


async def test_shutdown_aborts(service: MatchService) -> None:
    match = service.create("tictactoe", [HumanSpec(), BotSpec()])
    await asyncio.sleep(0.01)
    service.shutdown()
    await asyncio.sleep(0.01)
    assert match.status is MatchStatus.ABORTED
    record = service.store.get(match.id)
    assert record is not None
    assert record.reason == "Server shutting down"


async def test_stats(service: MatchService) -> None:
    for seed in range(4):
        match = service.create(
            "tictactoe", [BotSpec(bot="minimax"), BotSpec()], seed=seed
        )
        await match.start()
    draw = service.create(
        "tictactoe", [BotSpec(bot="minimax"), BotSpec(bot="minimax")], seed=0
    )
    await draw.start()
    stats = {s.group: s for s in service.store.stats(game_id="tictactoe")}
    minimax = stats["bot:minimax"]
    assert minimax.played == 6
    assert minimax.losses == 0
    assert minimax.draws >= 2
    assert minimax.mean_score > stats["bot:random"].mean_score
    assert stats["bot:random"].wins == 0
    assert 0 <= minimax.win_rate <= 1
    assert service.store.recent(game_id="tictactoe", limit=2)[0].id == draw.id
    assert len(service.store.recent()) == 5
    assert service.store.stats(game_id="other") == []


def test_empty_stats() -> None:
    from ludotastic.storage import PlayerStats  # noqa: PLC0415

    empty = PlayerStats(game_id="g", group="x")
    assert empty.win_rate == 0.0
    assert empty.mean_score == 0.0


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # noqa: ANN001
    monkeypatch.setenv("LUDOTASTIC_PORT", "9001")
    monkeypatch.setenv("LUDOTASTIC_DATA_DIR", str(tmp_path / "data"))
    settings = Settings(_env_file=None)
    assert settings.port == 9001
    assert settings.resolved_database_url.endswith("data/ludotastic.db")
    assert (tmp_path / "data").is_dir()
    explicit = Settings(_env_file=None, database_url="sqlite://")
    assert explicit.resolved_database_url == "sqlite://"
    get_settings.cache_clear()
    assert get_settings().port == 9001
    get_settings.cache_clear()


def test_service_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # noqa: ANN001
    monkeypatch.setenv("LUDOTASTIC_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    service = MatchService()
    assert "tictactoe" in service.games
    assert isinstance(service.store, Store)
    service.close()
    get_settings.cache_clear()


def test_other_databases_are_left_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    from ludotastic import storage  # noqa: PLC0415

    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        storage, "create_engine", lambda *a, **kw: calls.append((a, kw))
    )
    storage._engine("postgresql://user@localhost/db")  # noqa: SLF001
    assert calls == [(("postgresql://user@localhost/db",), {})]


def test_file_sqlite(tmp_path) -> None:  # noqa: ANN001
    store = Store(f"sqlite:///{tmp_path / 'x.db'}")
    assert store.recent() == []
    store.close()


async def test_stats_skip_unscored(service: MatchService) -> None:
    from ludotastic.storage import MatchRecord  # noqa: PLC0415

    match = service.create("tictactoe", [BotSpec(), BotSpec()], start=False)
    record = MatchRecord.from_match(match)
    record.status = "finished"
    from sqlmodel import Session  # noqa: PLC0415

    with Session(service.store.engine) as session:
        session.add(record)
        session.commit()
    assert service.store.stats() == []
