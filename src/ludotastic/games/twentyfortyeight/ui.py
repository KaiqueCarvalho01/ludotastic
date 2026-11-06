"""2048 in NiceGUI."""

from nicegui import ui
from nicegui.events import KeyEventArguments

from ludotastic.engine.render import RenderContext
from ludotastic.games.twentyfortyeight.game import (
    BIG_TILE,
    TILE_COLORS,
    Direction,
    Slide,
    TwentyFortyEightState,
)

__all__ = ["render"]

KEYS = {
    "ArrowUp": Direction.UP,
    "ArrowDown": Direction.DOWN,
    "ArrowLeft": Direction.LEFT,
    "ArrowRight": Direction.RIGHT,
    "w": Direction.UP,
    "s": Direction.DOWN,
    "a": Direction.LEFT,
    "d": Direction.RIGHT,
}
ARROWS = {
    Direction.UP: "keyboard_arrow_up",
    Direction.DOWN: "keyboard_arrow_down",
    Direction.LEFT: "keyboard_arrow_left",
    Direction.RIGHT: "keyboard_arrow_right",
}


def _tile_style(tile: int) -> str:
    background, color = TILE_COLORS.get(tile, BIG_TILE)
    size = "2.2rem" if tile < 100 else "1.9rem" if tile < 1000 else "1.5rem"  # noqa: PLR2004
    return f"background:{background};color:{color};font-size:{size};"


def render(ctx: RenderContext) -> None:
    """Draw the tiles, with keyboard and on-screen controls for a human seat."""
    state = ctx.match.state
    assert isinstance(state, TwentyFortyEightState)  # noqa: S101
    with ui.column().classes("items-center gap-3"):
        with ui.row().classes("gap-6 items-baseline"):
            ui.label(f"Score {state.score}").classes("text-2xl font-bold").mark("score")
            ui.label(f"Best tile {state.best}").classes("text-gray-500")
        with (
            ui.element("div")
            .classes("grid grid-cols-4 grid-rows-4 gap-2 p-2 rounded-xl")
            .style("background:#bbada0; width:min(90vw, 24rem); aspect-ratio:1;")
        ):
            for row in state.board:
                for tile in row:
                    ui.label(str(tile) if tile else "").classes(
                        "w-full h-full rounded-lg flex items-center justify-center "
                        "font-bold select-none"
                    ).style(_tile_style(tile))
        if 0 in ctx.seats and not ctx.match.done:
            _controls(ctx)


def _controls(ctx: RenderContext) -> None:
    def move(direction: Direction) -> None:
        action = Slide(direction=direction)
        # A slide that changes nothing is simply ignored, as in the original game.
        if ctx.can_act(0) and ctx.match.game.is_legal(ctx.match.state, 0, action):
            ctx.submit(0, action)

    def on_key(e: KeyEventArguments) -> None:
        if e.action.keydown and (direction := KEYS.get(e.key.name)) is not None:
            move(direction)

    ui.keyboard(on_key, repeating=False).mark("keys")
    ui.label("Arrow keys or WASD to slide").classes("text-sm text-gray-500")
    with ui.grid(columns=3).classes("gap-1 sm:hidden"):
        pad = (
            (None, Direction.UP, None),
            (Direction.LEFT, None, Direction.RIGHT),
            (None, Direction.DOWN, None),
        )
        for direction in (d for row in pad for d in row):
            if direction is None:
                ui.element("div")
            else:
                ui.button(
                    icon=ARROWS[direction],
                    on_click=lambda _, d=direction: move(d),
                ).props("round outline").mark(f"slide-{direction}")
