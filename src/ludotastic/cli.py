"""The `ludotastic` command."""

import asyncio
from typing import Annotated, Any

import typer
from dotenv import load_dotenv
from pydantic_ai import prices

from ludotastic.engine.game import ActionMode, View
from ludotastic.engine.registry import registry
from ludotastic.engine.usage import Usage, format_cost, format_tokens
from ludotastic.service import AISpec, BotSpec, MatchService, bot_names
from ludotastic.settings import get_settings

__all__ = ["app"]

app = typer.Typer(
    name="ludotastic",
    help="Where humans and AI come to play.",
    no_args_is_help=True,
)


@app.command()
def serve(
    host: Annotated[str | None, typer.Option(help="Address to listen on.")] = None,
    port: Annotated[int | None, typer.Option(help="Port to listen on.")] = None,
) -> None:
    """Run the playground and the API."""
    import uvicorn  # noqa: PLC0415

    from ludotastic.web import create_app  # noqa: PLC0415

    settings = get_settings()
    uvicorn.run(
        create_app(),
        host=host or settings.host,
        port=port or settings.port,
    )


@app.command("games")
def list_games() -> None:
    """List the installed games."""
    for game_id in registry:
        game = registry[game_id]()
        info = game.info
        modes = ", ".join(info.action_modes)
        typer.echo(
            f"{game_id}: {info.name} ({info.min_players}-{info.max_players} players, "
            f"{info.timing}; bots: {', '.join(bot_names(game))}; AI modes: {modes})"
        )
    for name, error in registry.errors.items():
        typer.secho(f"{name}: failed to load: {error}", fg=typer.colors.RED, err=True)


def _spec(text: str) -> BotSpec | AISpec:
    """Parse `bot:NAME`, or a model name with optional `@mode` and `+view`.

    Examples:
        >>> spec = _spec("typesafe:jev-latest@choice+image")
        >>> spec.model, str(spec.mode), str(spec.view)
        ('typesafe:jev-latest', 'choice', 'image')
    """
    if text.startswith("bot:"):
        return BotSpec(bot=text.removeprefix("bot:"))
    rest, _, view = text.partition("+")
    model, _, mode = rest.partition("@")
    return AISpec(
        model=model,
        mode=ActionMode(mode) if mode else None,
        view=View(view) if view else View.TEXT,
    )


@app.command()
def play(
    game_id: Annotated[str, typer.Argument(help="The game to play.")],
    players: Annotated[
        list[str],
        typer.Argument(
            help=(
                "One per seat: `bot:NAME` for a bot, or a model name such as "
                "`typesafe:jev-latest`, optionally with `@choice`, `@structured` "
                "or `@tools`, and `+image` or `+both` to show it pictures."
            )
        ),
    ],
    rounds: Annotated[int, typer.Option(help="How many matches to play.")] = 1,
    seed: Annotated[int | None, typer.Option(help="Seed for the first match.")] = None,
    swap: Annotated[
        bool, typer.Option(help="Rotate seats every round, for fairness.")
    ] = True,
    quiet: Annotated[bool, typer.Option(help="Only print the summary.")] = False,
) -> None:
    """Play matches between bots and AI models, without the UI."""
    settings = get_settings().model_copy(update={"ai_delay": 0.0})
    service = MatchService(settings=settings)
    specs = [_spec(p) for p in players]
    totals: dict[str, float] = {}
    spent: dict[str, Usage] = {}

    async def run_all() -> None:
        for round_ in range(rounds):
            shift = round_ % len(specs) if swap else 0
            seated = specs[shift:] + specs[:shift]
            match = service.create(
                game_id,
                seated,
                seed=None if seed is None else seed + round_,
                start=False,
            )
            if not quiet:
                match.subscribe(_printer())
            await match.run()
            names = [p.label for p in match.players]
            for seat, name in enumerate(names):
                spent[name] = spent.get(name, Usage()) + match.usage(seat)
            if match.outcome is None:
                typer.secho(f"Round {round_ + 1}: aborted: {match.error}", fg="red")
                continue
            for name, score in zip(names, match.outcome.scores, strict=True):
                totals[name] = totals.get(name, 0.0) + score
            result = ", ".join(
                f"{n}={s:g}" for n, s in zip(names, match.outcome.scores, strict=True)
            )
            typer.echo(f"Round {round_ + 1}: {match.outcome.reason} ({result})")

    updater = prices.update_in_background() if settings.update_prices else None
    try:
        asyncio.run(run_all())
    except KeyError:
        typer.secho(f"Unknown game: {game_id}", fg="red", err=True)
        raise typer.Exit(1) from None
    except ValueError as e:
        typer.secho(str(e), fg="red", err=True)
        raise typer.Exit(1) from None
    finally:
        if updater is not None:
            updater.stop()
        service.store.close()
    _summary(totals, spent)


def _summary(totals: dict[str, float], spent: dict[str, Usage]) -> None:
    typer.echo("Total score:")
    for name, score in sorted(totals.items(), key=lambda kv: -kv[1]):
        usage = spent.get(name, Usage())
        cost = (
            f" ({format_cost(usage.cost, priced=usage.priced)}, "
            f"{format_tokens(usage.tokens)} tokens, {usage.requests} requests)"
            if usage.requests
            else ""
        )
        typer.echo(f"  {name}: {score:g}{cost}")


def _printer() -> Any:  # noqa: ANN401
    printed = 0

    def show(match: Any) -> None:  # noqa: ANN401
        nonlocal printed
        for move in match.history[printed:]:
            typer.echo(
                f"  {move.turn + 1}. {match.game.player_label(move.seat)}: "
                f"{move.description}"
            )
        printed = len(match.history)

    return show


def main() -> None:
    """Run the CLI.

    Variables in a `.env` file in the working directory are loaded first, so
    model provider keys such as `TYPESAFE_API_KEY` can live there. Variables
    already set in the environment win.
    """
    load_dotenv(".env")
    app()
