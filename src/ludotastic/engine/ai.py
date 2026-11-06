"""AI players, powered by Pydantic AI."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast, override

from pydantic import BaseModel
from pydantic_ai import (
    Agent,
    Choice,
    Choices,
    ModelRetry,
    RunContext,
    Tool,
    ToolOutput,
    UsageLimits,
)
from pydantic_ai.capabilities import ModelFallback
from pydantic_ai.models import Model, infer_model

from ludotastic.engine.game import ActionMode
from ludotastic.engine.players import Decision, Player, PlayerKind, TurnContext

if TYPE_CHECKING:
    from pydantic_ai.settings import ModelSettings

__all__ = ["AIPlayer"]


@dataclass(frozen=True, kw_only=True)
class _Turn:
    ctx: TurnContext


def _legal_keys(ctx: TurnContext) -> dict[str, BaseModel]:
    return {ctx.game.action_key(action): action for action in ctx.legal_actions}


class AIPlayer(Player):
    """A player that asks an AI model for every action.

    Works with language models and with decision models such as TypeSafe's Jev
    (`typesafe:jev-latest`), using any model name Pydantic AI understands.
    """

    kind = PlayerKind.AI

    def __init__(  # noqa: PLR0913
        self,
        model: Model | str,
        *,
        mode: ActionMode | None = None,
        name: str | None = None,
        instructions: str | None = None,
        include_rules: bool = True,
        fallback_model: Model | str | None = None,
        retries: int = 2,
        request_limit: int = 10,
        model_settings: ModelSettings | None = None,
    ) -> None:
        """Set up the player.

        Args:
            model: A Pydantic AI model, or a model name like `openai:gpt-6-luna`.
            mode: How to ask for actions; defaults to the game's preferred mode.
            name: Display name; defaults to the model name.
            instructions: Extra instructions, such as a persona or strategy.
            include_rules: Whether to send the game's rules with every request.
            fallback_model: A model that takes over requests the main model
                cannot handle, such as a language model behind a decision model.
            retries: How often an invalid or illegal action is sent back.
            request_limit: The most model requests a single turn may take.
            model_settings: Settings such as temperature, passed to every run.
        """
        self.model = model if isinstance(model, Model) else infer_model(model)
        self.model_id = model if isinstance(model, str) else self.model.model_name
        super().__init__(name or self.model_id)
        self.mode = mode
        self.instructions = instructions
        self.include_rules = include_rules
        self.fallback_model = fallback_model
        self.retries = retries
        self.request_limit = request_limit
        self.model_settings = model_settings

    @property
    @override
    def label(self) -> str:
        """Group statistics by model and mode, not by display name."""
        mode = "" if self.mode is None else f"/{self.mode}"
        return f"ai:{self.model_id}{mode}"

    def _instructions(self, ctx: TurnContext) -> str:
        game = ctx.game
        seat = game.player_label(ctx.player)
        parts = [f"You are playing {game.info.name} as {seat}. Play to win."]
        if self.include_rules and game.rules:
            parts.append(f"Rules:\n{game.rules}")
        if self.instructions is not None:
            parts.append(self.instructions)
        return "\n\n".join(parts)

    def _agent(
        self,
        ctx: TurnContext,
        output_type: Any,  # noqa: ANN401
        tools: Sequence[Tool[_Turn]] = (),
    ) -> Agent[_Turn, Any]:
        capabilities = (
            None
            if self.fallback_model is None
            else [ModelFallback(self.fallback_model)]
        )
        return Agent(
            self.model,
            deps_type=_Turn,
            output_type=output_type,
            instructions=self._instructions(ctx),
            retries=self.retries,
            model_settings=self.model_settings,
            capabilities=capabilities,
            tools=tools,
            name=f"ludotastic-{ctx.game.info.id}",
        )

    @override
    async def act(self, ctx: TurnContext) -> Decision:
        """Ask the model for an action."""
        mode = self.mode or ctx.game.info.action_modes[0]
        if mode is ActionMode.CHOICE:
            agent = self._choice_agent(ctx)
            prompt = ctx.observation
        else:
            agent = self._action_agent(ctx, with_tools=mode is ActionMode.TOOLS)
            prompt = (
                f"It is your turn ({ctx.game.player_label(ctx.player)}). "
                "Look at the game with the tools, then submit your action."
                if mode is ActionMode.TOOLS
                else ctx.observation
            )
        result = await agent.run(
            prompt,
            deps=_Turn(ctx=ctx),
            usage_limits=UsageLimits(request_limit=self.request_limit),
        )
        usage = result.usage
        details: dict[str, Any] = {
            "mode": str(mode),
            "model": result.response.model_name,
            "requests": usage.requests,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
        }
        if (provider_details := result.response.provider_details) is not None:
            for key in ("confidence", "probabilities", "route"):
                if key in provider_details:
                    details[key] = provider_details[key]
        return Decision(action=cast("BaseModel", result.output), details=details)

    def _choice_agent(self, ctx: TurnContext) -> Agent[_Turn, Any]:
        game = ctx.game
        options = {
            key: Choice(game.describe_action(action), value=action)
            for key, action in _legal_keys(ctx).items()
        }
        choices = Choices(
            options,
            name="move",
            description=f"Which move should {game.player_label(ctx.player)} make?",
        )
        return self._agent(ctx, choices)

    def _action_agent(self, ctx: TurnContext, *, with_tools: bool) -> Agent[_Turn, Any]:
        game = ctx.game
        output = ToolOutput(
            game.action_type,
            name="submit_action",
            description=f"Make your move as {game.player_label(ctx.player)}.",
        )
        tools = (*_engine_tools(), *game.ai_tools(ctx.state, ctx.player))
        agent = self._agent(ctx, output, tools if with_tools else ())

        @agent.output_validator
        def check_legal(run: RunContext[_Turn], action: BaseModel) -> BaseModel:
            turn = run.deps.ctx
            if turn.game.is_legal(turn.state, turn.player, action):
                return action
            legal = ", ".join(turn.game.action_key(a) for a in turn.legal_actions)
            msg = f"That move is not legal. Legal moves: {legal}."
            raise ModelRetry(msg)

        return agent


def _engine_tools() -> Sequence[Tool[_Turn]]:
    def look_at_game(run: RunContext[_Turn]) -> str:
        """Look at the game as it stands, from your seat."""
        return run.deps.ctx.observation

    def list_legal_moves(run: RunContext[_Turn]) -> list[str]:
        """List every legal move, described in words."""
        turn = run.deps.ctx
        return [
            f"{turn.game.action_key(a)}: {turn.game.describe_action(a)}"
            for a in turn.legal_actions
        ]

    return (Tool(look_at_game), Tool(list_legal_moves))
