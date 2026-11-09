"""Rock-Paper-Scissors in NiceGUI."""

__all__: tuple[str, ...] = ("render",)

from typing import Final

from nicegui import ui

from ludotastic.engine.render import RenderContext
from ludotastic.games.rock_paper_scissors.game import (
    TARGET_WINS,
    Move,
    RockPaperScissorsState,
    Throw,
)

LABELS: Final = ("Player 1", "Player 2")

PLAYER_STYLES: Final = (
    {
        "name": "text-sky-700 dark:text-sky-300",
        "score": "text-sky-600 dark:text-sky-300",
        "card": "border-sky-200 bg-sky-50 dark:border-sky-800 dark:bg-sky-950",
    },
    {
        "name": "text-rose-700 dark:text-rose-300",
        "score": "text-rose-600 dark:text-rose-300",
        "card": "border-rose-200 bg-rose-50 dark:border-rose-800 dark:bg-rose-950",
    },
)

MOVE_STYLES: Final = {
    Move.ROCK: {
        "icon": "pan_tool",
        "button": (
            "bg-slate-100 text-slate-800 hover:bg-slate-200 "
            "dark:bg-slate-700 dark:text-slate-100"
        ),
    },
    Move.PAPER: {
        "icon": "description",
        "button": (
            "bg-sky-100 text-sky-800 hover:bg-sky-200 dark:bg-sky-900 dark:text-sky-100"
        ),
    },
    Move.SCISSORS: {
        "icon": "content_cut",
        "button": (
            "bg-emerald-100 text-emerald-800 hover:bg-emerald-200 "
            "dark:bg-emerald-900 dark:text-emerald-100"
        ),
    },
}

ROUND_STYLES: Final = {
    "win": "bg-green-100 text-green-800 border-green-300",
    "tie": "bg-amber-100 text-amber-800 border-amber-300",
    "ready": "bg-slate-100 text-slate-700 border-slate-300",
}


def _last_round(state: RockPaperScissorsState) -> str:
    """Describe the last round, or say that none has been played.

    Examples:
        >>> _last_round(RockPaperScissorsState())
        'No rounds have been played yet.'
        >>> _last_round(RockPaperScissorsState(last=(Move.ROCK, Move.SCISSORS)))
        'Last round: Player 1 played rock; Player 2 played scissors. Player 1 won.'
        >>> _last_round(RockPaperScissorsState(last=(Move.ROCK, Move.PAPER)))
        'Last round: Player 1 played rock; Player 2 played paper. Player 2 won.'
        >>> _last_round(RockPaperScissorsState(last=(Move.ROCK, Move.ROCK)))
        'Last round: Player 1 played rock; Player 2 played rock. It was a tie.'
    """
    first, second = state.last
    if first is None or second is None:
        return "No rounds have been played yet."
    if first.beats is second:
        result = "Player 1 won"
    elif second.beats is first:
        result = "Player 2 won"
    else:
        result = "It was a tie"
    return f"Last round: Player 1 played {first}; Player 2 played {second}. {result}."


def _header(state: RockPaperScissorsState) -> None:
    """Show the game title and the current round."""
    with ui.column().classes("items-center gap-1"):
        ui.label("Rock-Paper-Scissors").classes(
            "text-3xl sm:text-4xl font-black tracking-tight"
        )
        ui.label(f"Round {state.rounds + 1} — first to {TARGET_WINS} wins").classes(
            "text-lg text-slate-600 dark:text-slate-300"
        ).mark("round")


def _player_card(state: RockPaperScissorsState, seat: int) -> None:
    """Show one player's name, score and last throw."""
    style = PLAYER_STYLES[seat]
    last = state.last[seat]
    with ui.card().classes(
        "w-48 sm:w-64 items-center p-4 text-center border-2 rounded-2xl "
        f"{style['card']}"
    ):
        ui.label(LABELS[seat]).classes(f"text-xl font-bold {style['name']}")
        ui.label(f"{LABELS[seat]}: {state.wins[seat]}").classes(
            f"text-4xl font-mono font-black {style['score']}"
        ).mark(f"wins-{seat}")
        if last is None:
            ui.label("Waiting for the first round").classes("text-sm text-slate-500")
        else:
            ui.icon(MOVE_STYLES[last]["icon"]).classes("text-5xl")
            ui.label(last.value.title()).classes("text-lg font-semibold")


def _round_banner(state: RockPaperScissorsState) -> None:
    """Show the previous round's result, or a ready message."""
    first, second = state.last
    if first is None or second is None:
        heading = "Ready to play"
        style = ROUND_STYLES["ready"]
    elif first.beats is second:
        heading = (
            f"Player 1 wins the round! "
            f"({first.value.title()} beats {second.value.title()})"
        )
        style = ROUND_STYLES["win"]
    elif second.beats is first:
        heading = (
            f"Player 2 wins the round! "
            f"({second.value.title()} beats {first.value.title()})"
        )
        style = ROUND_STYLES["win"]
    else:
        heading = f"Tie round! Both played {first.value.title()}."
        style = ROUND_STYLES["tie"]
    with ui.column().classes(
        f"w-full items-center gap-1 border-2 rounded-xl px-4 py-3 {style}"
    ):
        ui.label(heading).classes("text-xl font-bold")
        ui.label(_last_round(state)).classes("text-sm").mark("last-round")


def _action_row(ctx: RenderContext, seat: int) -> None:
    """Draw the three throws for one seat, disabling them once picked."""
    buttons: list[ui.button] = []

    def play(move: Move) -> None:
        ctx.submit(seat, Throw(move=move))
        for button in buttons:
            button.disable()

    with ui.column().classes("w-full items-center gap-3"):
        ui.label(f"{LABELS[seat]}, choose:").classes("text-xl font-bold").mark(
            f"turn-{seat}"
        )
        with ui.row().classes("flex-wrap justify-center gap-3"):
            for move in Move:
                style = MOVE_STYLES[move]
                button = (
                    ui.button(
                        move.value.title(),
                        icon=style["icon"],
                        on_click=lambda _, move=move: play(move),
                        color=None,
                    )
                    .classes(
                        "w-32 h-20 text-base font-bold rounded-xl shadow-sm "
                        f"sm:w-40 sm:h-24 sm:text-lg {style['button']}"
                    )
                    .mark(f"move-{seat}-{move.value}")
                )
                buttons.append(button)


def _match_over_banner(ctx: RenderContext, state: RockPaperScissorsState) -> None:
    """Announce the result of a finished match."""
    outcome = ctx.match.game.outcome(state)
    assert outcome is not None  # noqa: S101
    if len(outcome.winners) == 1:
        text = f"{LABELS[outcome.winners[0]]} wins the match!"
    else:
        text = "Match over: it is a draw!"
    ui.label(text).classes(
        "w-full text-center text-2xl font-black bg-purple-100 text-purple-800 "
        "border-2 border-purple-300 rounded-xl px-4 py-3"
    ).mark("match-over")


def render(ctx: RenderContext) -> None:
    """Draw the scoreboard, player cards, round banner and throw pickers."""
    state = ctx.match.state
    assert isinstance(state, RockPaperScissorsState)  # noqa: S101
    with ui.column().classes("items-center gap-6 w-full max-w-4xl px-4 py-4"):
        _header(state)
        with ui.row().classes(
            "w-full flex-nowrap items-stretch justify-center gap-4 sm:gap-8"
        ):
            _player_card(state, 0)
            ui.label("VS").classes("self-center text-2xl font-black text-slate-400")
            _player_card(state, 1)
        _round_banner(state)
        for seat in sorted(ctx.seats):
            if ctx.can_act(seat):
                _action_row(ctx, seat)
        if ctx.match.game.outcome(state) is not None:
            _match_over_banner(ctx, state)
