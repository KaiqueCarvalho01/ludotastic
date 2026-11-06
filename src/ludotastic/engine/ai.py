"""AI players, powered by Pydantic AI."""

__all__: tuple[str, ...] = ("AIPlayer",)

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast, override

from pydantic import BaseModel
from pydantic_ai import (
    Agent,
    BinaryContent,
    Choice,
    Choices,
    ModelRetry,
    RunContext,
    Tool,
    ToolOutput,
    UsageLimits,
)
from pydantic_ai.capabilities import ModelFallback
from pydantic_ai.models import Model
from pydantic_ai.models.decision import DecisionModel

from ludotastic.engine.game import ActionMode, View
from ludotastic.engine.models import resolve_model
from ludotastic.engine.players import Decision, Player, PlayerKind, TurnContext
from ludotastic.engine.usage import Usage

if TYPE_CHECKING:
    from pydantic_ai.settings import ModelSettings


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
        view: View = View.TEXT,
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
            view: Whether the model is shown the game as text, as a picture,
                or both.
            retries: How often an invalid or illegal action is sent back.
            request_limit: The most model requests a single turn may take.
            model_settings: Settings such as temperature, passed to every run.

        Raises:
            ValueError: If a decision model, which can only pick among options,
                is asked to act in another mode without a fallback model.
        """
        self.model = model if isinstance(model, Model) else resolve_model(model)
        picks_only = isinstance(self.model, DecisionModel)
        if (
            picks_only
            and mode not in {None, ActionMode.CHOICE}
            and fallback_model is None
        ):
            msg = (
                f"{self.model.model_name} is a decision model: it can only pick "
                f"among options, so it needs the {ActionMode.CHOICE} mode, or a "
                f"fallback model for the {mode} mode"
            )
            raise ValueError(msg)
        self.model_id = model if isinstance(model, str) else self.model.model_name
        super().__init__(name or self.model_id)
        self.mode = mode
        self.instructions = instructions
        self.include_rules = include_rules
        self.fallback_model = (
            resolve_model(fallback_model)
            if isinstance(fallback_model, str)
            else fallback_model
        )
        if view is not View.TEXT and not self.model.profile.get(
            "supports_image_input", False
        ):
            msg = (
                f"{self.model.model_name} cannot take images, so it needs the text view"
            )
            raise ValueError(msg)
        self.view = view
        self.retries = retries
        self.request_limit = request_limit
        self.model_settings = model_settings

    @property
    @override
    def label(self) -> str:
        """Group statistics by model, mode and view, not by display name."""
        mode = "" if self.mode is None else f"/{self.mode}"
        view = "" if self.view is View.TEXT else f"+{self.view}"
        return f"ai:{self.model_id}{mode}{view}"

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
        """Ask the model for an action.

        A forced move, with only one legal action, is played without asking: there
        is nothing to decide, and decision models refuse a pick-one with a single
        option.
        """
        mode = self.mode or ctx.game.info.action_modes[0]
        if len(ctx.legal_actions) == 1:
            return Decision(
                action=ctx.legal_actions[0], details={"mode": str(mode), "forced": True}
            )
        if mode is ActionMode.CHOICE:
            agent = self._choice_agent(ctx)
            prompt = self._prompt(ctx)
        else:
            agent = self._action_agent(ctx, with_tools=mode is ActionMode.TOOLS)
            prompt = (
                f"It is your turn ({ctx.game.player_label(ctx.player)}). "
                "Look at the game with the tools, then submit your action."
                if mode is ActionMode.TOOLS
                else self._prompt(ctx)
            )
        result = await agent.run(
            prompt,
            deps=_Turn(ctx=ctx),
            usage_limits=UsageLimits(request_limit=self.request_limit),
        )
        run = result.usage
        usage = Usage(
            requests=run.requests,
            input_tokens=run.input_tokens,
            output_tokens=run.output_tokens,
            cost=run.cost,
        )
        details: dict[str, Any] = {
            "mode": str(mode),
            "model": result.response.model_name,
        }
        if self.view is not View.TEXT:
            details["view"] = str(self.view)
        if (provider_details := result.response.provider_details) is not None:
            for key in ("confidence", "probabilities", "route"):
                if key in provider_details:
                    details[key] = provider_details[key]
        return Decision(
            action=cast("BaseModel", result.output), details=details, usage=usage
        )

    def _prompt(self, ctx: TurnContext) -> str | list[str | BinaryContent]:
        """The game as this player is shown it: text, a picture, or both."""
        if self.view is View.TEXT:
            return ctx.observation
        picture = ctx.game.snapshot(ctx.state, ctx.player)
        if picture is None:
            msg = f"{ctx.game.info.name} cannot draw itself for the image view"
            raise ValueError(msg)
        image = BinaryContent(picture, media_type="image/png")
        if self.view is View.IMAGE:
            return [ctx.game.brief(ctx.state, ctx.player), image]
        return [ctx.observation, image]

    def _choice_agent(self, ctx: TurnContext) -> Agent[_Turn, Any]:
        game = ctx.game
        options = {
            key: Choice(
                game.describe_option(ctx.state, ctx.player, action), value=action
            )
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
            f"{turn.game.action_key(a)}: "
            f"{turn.game.describe_option(turn.state, turn.player, a)}"
            for a in turn.legal_actions
        ]

    return (Tool(look_at_game), Tool(list_legal_moves))
