"""The `ludotastic` command."""

import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ludotastic.cli import app
from ludotastic.settings import get_settings

runner = CliRunner()


@pytest.fixture(autouse=True)
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUDOTASTIC_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()


def test_games() -> None:
    result = runner.invoke(app, ["games"])
    assert result.exit_code == 0
    assert "tictactoe: Tic-Tac-Toe" in result.output


def test_play_bots() -> None:
    result = runner.invoke(
        app,
        [
            "play",
            "tictactoe",
            "bot:minimax",
            "bot:minimax",
            "--rounds",
            "2",
            "--seed",
            "1",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "1. X:" in result.output
    assert "Round 2: The board is full" in result.output
    assert "bot:minimax: 2" in result.output


def test_play_ai_quietly() -> None:
    result = runner.invoke(
        app, ["play", "tictactoe", "test@choice", "bot:random", "--quiet", "--no-swap"]
    )
    assert result.exit_code == 0, result.output
    assert "1. X:" not in result.output
    assert "ai:test/choice" in result.output


def test_play_reports_aborts() -> None:
    result = runner.invoke(
        app, ["play", "tictactoe", "test@structured", "test", "--quiet"]
    )
    assert result.exit_code == 0, result.output
    assert "Total score" in result.output


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["play", "nope", "bot:random"], "Unknown game"),
        (["play", "tictactoe", "bot:ghost", "bot:random"], "no bot"),
    ],
)
def test_play_errors(args: list[str], message: str) -> None:
    result = runner.invoke(app, args)
    assert result.exit_code == 1
    assert message in result.output


def test_serve(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr("uvicorn.run", lambda app, **kw: calls.append(kw))
    monkeypatch.setattr("ludotastic.web.create_app", object)
    result = runner.invoke(app, ["serve", "--port", "9999"])
    assert result.exit_code == 0, result.output
    assert calls == [{"host": "127.0.0.1", "port": 9999}]


def test_games_reports_broken_plugins(monkeypatch: pytest.MonkeyPatch) -> None:
    from ludotastic import registry  # noqa: PLC0415

    monkeypatch.setattr(registry, "_errors", {"broken": "ImportError: nope"})
    result = runner.invoke(app, ["games"])
    assert "broken: failed to load: ImportError: nope" in result.output


def test_play_reports_aborted_rounds(monkeypatch: pytest.MonkeyPatch) -> None:
    from ludotastic import Match  # noqa: PLC0415

    async def abort(self: Match) -> None:
        self.error = "nope"

    monkeypatch.setattr(Match, "run", abort)
    result = runner.invoke(app, ["play", "tictactoe", "bot:random", "bot:random"])
    assert result.exit_code == 0, result.output
    assert "Round 1: aborted: nope" in result.output


def test_main(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from ludotastic import cli  # noqa: PLC0415

    monkeypatch.setattr("sys.argv", ["ludotastic", "games"])
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LUDOTASTIC_TEST_KEY", raising=False)
    (tmp_path / ".env").write_text("LUDOTASTIC_TEST_KEY=from-dotenv\n")
    with pytest.raises(SystemExit) as exit_info:
        cli.main()
    assert exit_info.value.code == 0
    assert os.environ.pop("LUDOTASTIC_TEST_KEY") == "from-dotenv"
