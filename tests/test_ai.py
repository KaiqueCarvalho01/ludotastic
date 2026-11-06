"""AI players, using Pydantic AI's test and function models."""

__all__: tuple[str, ...] = ()

import json
import random
from typing import override

import pytest
from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    ToolCallPart,
)
from pydantic_ai.models.decision import (
    DecisionModel,
    DecisionModelSettings,
    DecisionRequest,
    DecisionResponse,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from ludotastic import ActionMode, AIPlayer, TurnContext
from ludotastic.games.tictactoe import Place, TicTacToe, TicTacToeState


def ctx(board: str = ".........") -> TurnContext:
    game = TicTacToe()
    state = TicTacToeState(
        board=tuple(None if c == "." else c for c in board)  # type: ignore[ty:invalid-argument-type]
    )
    (player,) = game.to_move(state)
    return TurnContext(
        game=game,
        state=state,
        player=player,
        legal_actions=game.legal_actions(state, player),
        turn=0,
        rng=random.Random(0),
    )


async def test_choice_mode_picks_a_described_move() -> None:
    seen: dict[str, object] = {}

    def pick(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        tool = info.output_tools[0]
        seen["schema"] = tool.parameters_json_schema
        seen["instructions"] = info.instructions
        return ModelResponse(parts=[ToolCallPart(tool.name, {"response": "4"})])

    player = AIPlayer(
        FunctionModel(pick), mode=ActionMode.CHOICE, instructions="Be bold."
    )
    decision = await player.act(ctx())
    assert decision.action == Place(cell=4)
    assert decision.details["mode"] == "choice"
    assert decision.usage is not None
    assert decision.usage.requests == 1
    assert decision.usage.tokens > 0
    options = seen["schema"]["properties"]["response"]["anyOf"]  # type: ignore[ty:not-subscriptable]
    assert {
        "const": "4",
        "description": "Place your mark in the center (cell 4).",
    } in options
    assert "Be bold." in str(seen["instructions"])
    assert "Rules:" in str(seen["instructions"])


async def test_structured_mode_retries_illegal_moves() -> None:
    calls: list[int] = []

    def play(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls.append(1)
        cell = 0 if len(messages) == 1 else 1
        return ModelResponse(
            parts=[ToolCallPart(info.output_tools[0].name, json.dumps({"cell": cell}))]
        )

    player = AIPlayer(
        FunctionModel(play), mode=ActionMode.STRUCTURED, include_rules=False
    )
    decision = await player.act(ctx("X...O...."))
    assert decision.action == Place(cell=1)
    assert len(calls) == 2


async def test_tools_mode_offers_engine_tools() -> None:
    player = AIPlayer(TestModel(), mode=ActionMode.TOOLS)
    decision = await player.act(ctx())
    assert decision.action == Place(cell=0)
    assert decision.usage is not None
    assert decision.usage.requests == 2


async def test_default_mode_and_label() -> None:
    player = AIPlayer("test")
    assert player.name == "test"
    assert player.label == "ai:test"
    assert AIPlayer("test", mode=ActionMode.TOOLS).label == "ai:test/tools"
    decision = await player.act(ctx())
    assert decision.details["mode"] == "choice"


async def test_provider_details_are_reported() -> None:
    def pick(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(
            parts=[ToolCallPart(info.output_tools[0].name, {"response": "0"})],
            provider_details={"confidence": {"response": 0.9}, "other": 1},
        )

    decision = await AIPlayer(FunctionModel(pick), fallback_model="test").act(ctx())
    assert decision.details["confidence"] == {"response": 0.9}
    assert "other" not in decision.details


async def test_forced_move_skips_the_model() -> None:
    def never(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        raise AssertionError  # pragma: no cover

    decision = await AIPlayer(FunctionModel(never)).act(ctx("XOXXOOOX."))
    assert decision.action == Place(cell=8)
    assert decision.details == {"mode": "choice", "forced": True}


def test_unknown_model() -> None:
    with pytest.raises(Exception, match="Unknown model"):
        AIPlayer("nope:nothing")


class FakeDecider(DecisionModel):
    """A decision model that never gets as far as deciding."""

    @property
    @override
    def model_name(self) -> str:
        return "fake-decider"

    @property
    @override
    def system(self) -> str:
        return "fake"

    @override
    async def decide(
        self,
        request: DecisionRequest,
        model_settings: DecisionModelSettings,
    ) -> DecisionResponse:  # pragma: no cover
        raise AssertionError


@pytest.mark.parametrize("mode", [ActionMode.STRUCTURED, ActionMode.TOOLS])
def test_decision_models_need_choice_mode(mode: ActionMode) -> None:
    with pytest.raises(ValueError, match="decision model"):
        AIPlayer(FakeDecider(), mode=mode)
    assert AIPlayer(FakeDecider(), mode=mode, fallback_model="test").mode is mode
    assert AIPlayer(FakeDecider(), mode=ActionMode.CHOICE).mode is ActionMode.CHOICE
    assert AIPlayer(FakeDecider()).mode is None
