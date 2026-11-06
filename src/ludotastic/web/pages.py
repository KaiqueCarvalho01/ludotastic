"""The NiceGUI playground."""

from collections.abc import Callable
from functools import partial
from typing import Any

from nicegui import ui

from ludotastic.engine.game import Game
from ludotastic.engine.players import PlayerKind
from ludotastic.engine.usage import Usage, format_cost
from ludotastic.service import (
    AISpec,
    BotSpec,
    HumanSpec,
    MatchService,
    bot_names,
    replay,
)
from ludotastic.web.match_view import match_view

__all__ = ["build_root"]

NAV = (("Games", "/"), ("Live", "/live"), ("History", "/history"), ("Stats", "/stats"))


def _header(service: MatchService) -> None:
    with ui.header().classes("items-center no-wrap gap-2 sm:gap-4 px-3 sm:px-6 py-2"):
        ui.link(service.settings.title, "/").classes(
            "text-lg sm:text-xl font-bold text-white no-underline shrink-0"
        )
        ui.space()
        with ui.row().classes(
            "items-center no-wrap gap-3 sm:gap-5 text-sm sm:text-base"
        ):
            for label, path in NAV:
                ui.link(label, path).classes("text-white no-underline hover:underline")
            ui.link("API", "/docs", new_tab=True).classes(
                "text-white no-underline hover:underline max-sm:hidden"
            )
        dark = ui.dark_mode(service.settings.dark)

        async def toggle_dark() -> None:
            # In auto mode, `dark.value` is None and `toggle()` refuses: flip
            # whatever the browser is showing instead.
            if dark.value is None:
                dark.value = not await ui.run_javascript("Quasar.Dark.isActive")
            else:
                dark.toggle()

        ui.button(icon="dark_mode", on_click=toggle_dark).props(
            "flat round dense color=white"
        ).tooltip("Toggle dark mode").mark("dark-toggle")


def _games_page(service: MatchService) -> None:
    ui.label("Games").classes("text-2xl font-bold")
    if not service.games:
        ui.label("No games installed.")
    with ui.row().classes("gap-4"):
        for game_id in service.games:
            info = service.games[game_id].info
            with ui.card().classes("w-72"):
                ui.label(info.name).classes("text-lg font-bold")
                ui.label(info.description)
                with ui.row().classes("gap-1"):
                    players = (
                        str(info.min_players)
                        if info.min_players == info.max_players
                        else f"{info.min_players}-{info.max_players}"
                    )
                    noun = "player" if info.max_players == 1 else "players"
                    ui.badge(f"{players} {noun}", color="grey")
                    ui.badge(str(info.timing), color="grey")
                    for tag in info.tags:
                        ui.badge(tag, color="grey").props("outline")
                ui.button(
                    "Play",
                    icon="play_arrow",
                    on_click=partial(ui.navigate.to, f"/play/{game_id}"),
                ).mark(f"play-{game_id}")
    for name, error in service.games.errors.items():
        ui.label(f"Could not load {name}: {error}").classes("text-negative")


class _SeatForm:
    """The controls for one seat in the new-match form."""

    def __init__(self, service: MatchService, game: Game[Any, Any], seat: int) -> None:
        settings = service.settings
        default_kind = PlayerKind.HUMAN if seat == 0 else PlayerKind.AI
        with ui.card().classes("w-80"):
            ui.label(game.player_label(seat)).classes("text-lg font-bold")
            self.kind = ui.toggle(
                {PlayerKind.HUMAN: "Human", PlayerKind.BOT: "Bot", PlayerKind.AI: "AI"},
                value=default_kind,
            ).mark(f"kind-{seat}")
            self.name = ui.input("Name", value="Human").classes("w-full")
            self.name.bind_visibility_from(self.kind, "value", value=PlayerKind.HUMAN)
            bots = bot_names(game)
            self.bot = ui.select(bots, value=bots[-1], label="Bot").classes("w-full")
            self.bot.mark(f"bot-{seat}")
            self.bot.bind_visibility_from(self.kind, "value", value=PlayerKind.BOT)
            with ui.column().classes("w-full") as ai_box:
                self.model = (
                    ui.select(
                        settings.suggested_models,
                        value=settings.default_model,
                        label="Model",
                        new_value_mode="add-unique",
                        with_input=True,
                    )
                    .classes("w-full")
                    .mark(f"model-{seat}")
                )
                modes = {str(m): str(m) for m in game.info.action_modes}
                self.mode = ui.select(
                    {"": "Game default", **modes}, value="", label="Action mode"
                ).classes("w-full")
                self.fallback = ui.select(
                    ["", *settings.suggested_models],
                    value="",
                    label="Fallback model (optional)",
                    new_value_mode="add-unique",
                    with_input=True,
                ).classes("w-full")
                self.instructions = ui.textarea(
                    "Extra instructions (optional)"
                ).classes("w-full")
            ai_box.bind_visibility_from(self.kind, "value", value=PlayerKind.AI)

    def spec(self) -> HumanSpec | BotSpec | AISpec:
        match self.kind.value:
            case PlayerKind.HUMAN:
                return HumanSpec(name=self.name.value or "Human")
            case PlayerKind.BOT:
                return BotSpec(bot=self.bot.value)
            case _:
                return AISpec(
                    model=self.model.value,
                    mode=self.mode.value or None,
                    fallback_model=self.fallback.value or None,
                    instructions=self.instructions.value or None,
                )


def _new_match_page(service: MatchService, game_id: str) -> None:
    try:
        game_type = service.games[game_id]
    except KeyError:
        ui.label(f"Unknown game: {game_id}")
        return
    info = game_type.info
    ui.label(info.name).classes("text-2xl font-bold")
    ui.markdown(game_type.rules or info.description)
    count = ui.number(
        "Players",
        value=info.min_players,
        min=info.min_players,
        max=info.max_players,
        precision=0,
    )
    count.set_visibility(info.min_players != info.max_players)
    forms: list[_SeatForm] = []

    @ui.refreshable
    def seats() -> None:
        forms.clear()
        game = game_type(int(count.value or info.min_players))
        with ui.row().classes("gap-4"):
            forms.extend(
                _SeatForm(service, game, seat) for seat in range(game.num_players)
            )

    seats()
    count.on_value_change(seats.refresh)
    seed = ui.number("Seed (optional)", precision=0)

    def start() -> None:
        try:
            match = service.create(
                game_id,
                [form.spec() for form in forms],
                seed=int(seed.value) if seed.value is not None else None,
            )
        except Exception as e:  # noqa: BLE001
            ui.notify(
                f"Could not start the match: {e}", type="negative", multi_line=True
            )
            return
        ui.navigate.to(f"/match/{match.id}")

    ui.button("Start match", icon="play_arrow", on_click=start).mark("start")


def _match_page(service: MatchService, match_id: str) -> None:
    match = service.get(match_id)
    if match is None:
        ui.label("This match is no longer live.")
        ui.link("See it in the history", f"/history/{match_id}")
        return
    match_view(match)


def _live_page(service: MatchService) -> None:
    ui.label("Live matches").classes("text-2xl font-bold")

    @ui.refreshable
    def listing() -> None:
        live = service.live()
        if not live:
            ui.label("Nothing is being played right now.")
        for match in live:
            with ui.row().classes("items-center gap-2"):
                ui.link(match.game.info.name, f"/match/{match.id}")
                ui.label(" vs ".join(p.name for p in match.players))
                ui.label(f"turn {match.turn}").classes("text-gray-500")

    listing()
    ui.timer(1.0, listing.refresh)


def _history_page(service: MatchService) -> None:
    ui.label("History").classes("text-2xl font-bold")
    rows = [
        {
            "id": r.id,
            "game": r.game_id,
            "players": " vs ".join(s["player"] for s in r.seats),
            "scores": ", ".join(f"{x:g}" for x in r.scores or []),
            "reason": r.reason or "",
            "turns": r.turns,
            "ai cost": _cost(r.usage()),
            "status": r.status,
            "date": r.created_at.strftime("%Y-%m-%d %H:%M"),
        }
        for r in service.store.recent(limit=200)
    ]
    columns = [
        {"name": k, "label": k.title(), "field": k, "align": "left", "sortable": True}
        for k in (
            "date",
            "game",
            "players",
            "scores",
            "reason",
            "turns",
            "ai cost",
            "status",
        )
    ]
    table = ui.table(columns=columns, rows=rows, row_key="id", pagination=20)
    table.classes("w-full cursor-pointer")
    table.add_slot(
        "body-cell-reason",
        r"""
        <q-td :props="props">
          <div class="max-w-md truncate" :title="props.value">{{ props.value }}</div>
        </q-td>
        """,
    )
    table.on("rowClick", lambda e: ui.navigate.to(f"/history/{e.args[1]['id']}"))


def _history_match_page(service: MatchService, match_id: str) -> None:
    record = service.store.get(match_id)
    if record is None:
        ui.label("No stored match with that id.")
        return
    try:
        match = replay(service.games, record)
    except KeyError:
        ui.label(f"The game {record.game_id!r} is not installed.")
        return
    match_view(match)
    ui.label(f"Seed {record.seed}, {record.turns} turns").classes(
        "text-sm text-gray-500"
    )


def _stats_page(service: MatchService) -> None:
    ui.label("Stats").classes("text-2xl font-bold")
    stats = service.store.stats()
    if not stats:
        ui.label("Play some matches first.")
        return
    keys = (
        "game",
        "player",
        "played",
        "wins",
        "draws",
        "losses",
        "mean_score",
        "cost",
        "cost_per_match",
    )
    columns = [
        {
            "name": k,
            "label": k.replace("_", " ").title(),
            "field": k,
            "align": "left",
            "sortable": True,
        }
        for k in keys
    ]
    rows = [
        {
            "id": f"{s.game_id}/{s.group}",
            "game": s.game_id,
            "player": s.group,
            "played": s.played,
            "wins": s.wins,
            "draws": s.draws,
            "losses": s.losses,
            "mean_score": round(s.mean_score, 3),
            "cost": _cost(s.usage),
            "cost_per_match": _cost(s.usage, per=s.played),
        }
        for s in stats
    ]
    ui.table(columns=columns, rows=rows, row_key="id").classes("w-full")


def _cost(usage: Usage, *, per: int = 1) -> str:
    """A cost for a table: blank when nothing used a model."""
    if usage.requests == 0:
        return ""
    cost = None if usage.cost is None else usage.cost / per
    return format_cost(cost, priced=usage.priced)


def build_root(service: MatchService) -> Callable[[], None]:
    """The NiceGUI root page, routing between the playground's pages."""

    def root() -> None:
        _header(service)
        with ui.column().classes("w-full max-w-7xl mx-auto p-4"):
            ui.sub_pages(
                {
                    "/": partial(_games_page, service),
                    "/play/{game_id}": partial(_new_match_page, service),
                    "/match/{match_id}": partial(_match_page, service),
                    "/live": partial(_live_page, service),
                    "/history": partial(_history_page, service),
                    "/history/{match_id}": partial(_history_match_page, service),
                    "/stats": partial(_stats_page, service),
                }
            ).classes("w-full")

    return root
