"""Image views: Jev seeing pictures through Pydantic AI, and games drawing them."""

import io
import json
import random
from collections.abc import Callable
from typing import Any

import httpx2
import pytest
from PIL import Image
from pydantic import JsonValue
from pydantic_ai import Agent, BinaryContent
from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.providers.typesafe import TypeSafeProvider
from typesafe_sdk import AsyncTypeSafeClient

from ludotastic import ActionMode, AIPlayer, TurnContext, View
from ludotastic.engine.models import IMAGES_HEADER, TypeSafeImageModel, resolve_model
from ludotastic.games.snake import Snake
from ludotastic.games.tictactoe import TicTacToe
from ludotastic.games.twentyfortyeight import TwentyFortyEight
from ludotastic.service import AISpec, BotSpec, MatchService

PNG = TicTacToe().snapshot(TicTacToe().initial_state(random.Random(0)), 0)


def fake_jev(seen: list[httpx2.Request]) -> TypeSafeImageModel:
    """Jev behind a fake HTTP server that always answers yes."""

    def reply(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(
            200,
            json={
                "model": "jev-1.14.0",
                "answers": {"response": {"type": "noul", "noul": 0.9}},
                "usage": {"input_tokens": 800, "output_tokens": 20},
            },
        )

    client = AsyncTypeSafeClient(
        api_key="test", transport=httpx2.MockTransport(reply), compression=False
    )
    return TypeSafeImageModel(
        "jev-latest", provider=TypeSafeProvider(typesafe_client=client)
    )


def body(request: httpx2.Request) -> tuple[dict[str, Any], list[bytes]]:
    """The JSON part of a request, and the files sent with it."""
    if request.headers["content-type"].startswith("application/json"):
        return json.loads(request.content), []
    boundary = request.headers["content-type"].split("boundary=")[1].encode()
    parts = [p for p in request.content.split(b"--" + boundary) if b"\r\n\r\n" in p]
    contents = [p.split(b"\r\n\r\n", 1)[1].rstrip(b"\r\n") for p in parts]
    return json.loads(contents[0]), contents[1:]


async def test_jev_gets_images_as_assets() -> None:
    seen: list[httpx2.Request] = []
    agent = Agent(fake_jev(seen), output_type=bool, instructions="Does X win?")
    result = await agent.run(["The board:", BinaryContent(PNG, media_type="image/png")])
    assert result.output is True
    (request,) = seen
    assert request.headers[IMAGES_HEADER] == "true"
    sent, files = body(request)
    (reference,) = sent["assets"]
    assert reference in json.dumps(sent["state"])  # In place of `<image 1>`.
    assert "<image 1>" not in json.dumps(sent["state"])
    assert files == [PNG]


async def test_jev_without_images_is_unchanged() -> None:
    seen: list[httpx2.Request] = []
    agent = Agent(fake_jev(seen), output_type=bool, instructions="Is this a greeting?")
    assert (await agent.run("hello")).output is True
    (request,) = seen
    assert IMAGES_HEADER not in request.headers
    sent, files = body(request)
    assert "assets" not in sent
    assert files == []


async def test_images_keep_other_headers() -> None:
    seen: list[httpx2.Request] = []
    model = fake_jev(seen)
    agent = Agent(model, output_type=bool, instructions="Does X win?")
    await agent.run(
        [BinaryContent(PNG, media_type="image/png")],
        model_settings={"extra_headers": {"X-Test": "1"}},
    )
    assert seen[0].headers["X-Test"] == "1"
    assert seen[0].headers[IMAGES_HEADER] == "true"


def test_resolve_model_picks_the_image_class(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TYPESAFE_API_KEY", "test")
    model = resolve_model("typesafe:jev-latest")
    assert isinstance(model, TypeSafeImageModel)
    assert model.model_name == "jev-latest"
    assert model.profile.get("supports_image_input") is True


@pytest.mark.parametrize(
    ("game", "size"),
    [
        (TicTacToe(), (420, 420)),
        (Snake(), (480, 480)),
        (TwentyFortyEight(), (500, 500)),
    ],
)
def test_games_draw_valid_pictures(game: Any, size: tuple[int, int]) -> None:  # noqa: ANN401
    state = game.initial_state(random.Random(0))
    picture = Image.open(io.BytesIO(game.snapshot(state, 0)))
    assert picture.format == "PNG"
    assert picture.size == size
    assert min(size) >= 280  # What Jev accepts.
    assert max(size) <= 1568
    assert game.can_draw
    assert "picture" in game.brief(state, 0)


def test_default_game_cannot_draw() -> None:
    from tests.test_engine import Race  # noqa: PLC0415

    race = Race()
    assert not race.can_draw
    assert race.snapshot(race.initial_state(random.Random(0)), 0) is None
    assert race.brief(race.initial_state(random.Random(0)), 1) == (
        "You are Player 2. The picture shows the game."
    )


def ctx() -> TurnContext:
    game = TicTacToe()
    state = game.initial_state(random.Random(0))
    return TurnContext(
        game=game,
        state=state,
        player=0,
        legal_actions=game.legal_actions(state, 0),
        turn=0,
        rng=random.Random(0),
    )


def recorder(prompts: list[list[Any]]) -> Callable[..., ModelResponse]:
    def pick(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        part = messages[0].parts[-1]
        assert isinstance(part, UserPromptPart)
        prompts.append(
            [part.content] if isinstance(part.content, str) else list(part.content)
        )
        return ModelResponse(
            parts=[ToolCallPart(info.output_tools[0].name, {"response": "4"})]
        )

    return pick


@pytest.mark.parametrize(
    ("view", "texts", "images"),
    [
        (View.TEXT, ["Board (numbers are empty cells)"], 0),
        (View.IMAGE, ["The picture shows the board"], 1),
        (View.BOTH, ["Board (numbers are empty cells)"], 1),
    ],
)
async def test_views_shape_the_prompt(
    view: View, texts: list[str], images: int
) -> None:
    prompts: list[list[Any]] = []
    player = AIPlayer(FunctionModel(recorder(prompts)), view=view)
    decision = await player.act(ctx())
    (prompt,) = prompts
    text = " ".join(item for item in prompt if isinstance(item, str))
    assert all(snippet in text for snippet in texts)
    assert sum(isinstance(item, BinaryContent) for item in prompt) == images
    assert ("view" in decision.details) is (view is not View.TEXT)
    assert player.label.endswith("" if view is View.TEXT else f"+{view}")
    assert ("+" in player.label) is (view is not View.TEXT)


async def test_image_view_needs_a_drawing_game() -> None:
    from tests.test_engine import Race  # noqa: PLC0415

    race = Race()
    state = race.initial_state(random.Random(0))
    turn = TurnContext(
        game=race,
        state=state,
        player=0,
        legal_actions=race.legal_actions(state, 0),
        turn=0,
        rng=random.Random(0),
    )
    player = AIPlayer(FunctionModel(recorder([])), view=View.IMAGE)
    with pytest.raises(ValueError, match="cannot draw itself"):
        await player.act(turn)


def test_text_only_models_need_the_text_view() -> None:
    from pydantic_ai.models.test import TestModel  # noqa: PLC0415
    from pydantic_ai.profiles import ModelProfile  # noqa: PLC0415

    blind = TestModel(profile=ModelProfile(supports_image_input=False))
    with pytest.raises(ValueError, match="cannot take images"):
        AIPlayer(blind, view=View.IMAGE)
    assert AIPlayer(blind).view is View.TEXT


async def test_service_checks_the_view(service: MatchService) -> None:
    from ludotastic import GameRegistry  # noqa: PLC0415
    from tests.test_engine import Race  # noqa: PLC0415

    games = GameRegistry(group="ludotastic.tests.none")
    games.register(Race)
    games.register(TicTacToe)
    service.games = games
    with pytest.raises(ValueError, match="cannot draw itself"):
        service.create("race", [AISpec(model="test", view=View.IMAGE), BotSpec()])
    match = service.create(
        "tictactoe",
        [AISpec(model="test", view=View.BOTH, mode=ActionMode.CHOICE), BotSpec()],
        start=False,
    )
    assert isinstance(match.players[0], AIPlayer)
    assert match.players[0].view is View.BOTH


def test_fallback_model_names_are_resolved(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TYPESAFE_API_KEY", "test")
    player = AIPlayer("test", fallback_model="typesafe:jev-latest")
    assert isinstance(player.fallback_model, TypeSafeImageModel)


def test_placeholders_are_swapped_everywhere() -> None:
    from ludotastic.engine.models import _replace  # noqa: PLC0415

    state: JsonValue = {
        "history": [{"text": "<image 1>", "n": 3}],
        "now": "<image 2>",
        "x": None,
    }
    refs = {"<image 1>": "a", "<image 2>": "b"}
    assert _replace(state, refs) == {
        "history": [{"text": "a", "n": 3}],
        "now": "b",
        "x": None,
    }


def test_tictactoe_draws_both_marks() -> None:
    from ludotastic.games.tictactoe import TicTacToeState  # noqa: PLC0415

    state = TicTacToeState(board=("X", "O", None, None, None, None, None, None, None))
    picture = Image.open(io.BytesIO(TicTacToe().snapshot(state, 1))).convert("RGB")
    colors = {color for _, color in picture.getcolors(maxcolors=100_000) or []}
    assert (37, 99, 235) in colors  # X, in blue.
    assert (225, 29, 72) in colors  # O, in red.
