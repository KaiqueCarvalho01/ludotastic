"""Snake in NiceGUI."""

__all__: tuple[str, ...] = ("render",)

from typing import Final

from nicegui import ui
from nicegui.events import KeyEventArguments

from ludotastic.engine.render import RenderContext
from ludotastic.games.snake.game import Direction, SnakeState, Turn

KEYS: Final = {
    "ArrowUp": Direction.UP,
    "ArrowDown": Direction.DOWN,
    "ArrowLeft": Direction.LEFT,
    "ArrowRight": Direction.RIGHT,
    "w": Direction.UP,
    "s": Direction.DOWN,
    "a": Direction.LEFT,
    "d": Direction.RIGHT,
}
ARROWS: Final = {
    Direction.UP: "keyboard_arrow_up",
    Direction.DOWN: "keyboard_arrow_down",
    Direction.LEFT: "keyboard_arrow_left",
    Direction.RIGHT: "keyboard_arrow_right",
}


def _cell_class(state: SnakeState, cell: tuple[int, int]) -> str:
    if cell == state.head:
        return "bg-emerald-600 dark:bg-emerald-400 rounded-md"
    if cell in state.body:
        return "bg-emerald-400 dark:bg-emerald-600 rounded-sm"
    if cell == state.food:
        return "bg-rose-500 rounded-full scale-75"
    return "bg-gray-100 dark:bg-gray-800 rounded-sm"


def render(ctx: RenderContext) -> None:
    """Draw the board, with keyboard and on-screen controls for a human seat."""
    state = ctx.match.state
    assert isinstance(state, SnakeState)  # noqa: S101
    with ui.column().classes("items-center gap-3"):
        ui.label(f"Score {state.score}").classes("text-2xl font-bold").mark("score")
        with (
            ui.element("div")
            .classes("grid gap-[2px] p-1 rounded-lg")
            .style(
                f"grid-template-columns: repeat({state.width}, minmax(0, 1fr));"
                "width: min(90vw, 28rem); aspect-ratio: 1;"
            )
            .classes("bg-gray-300 dark:bg-gray-700")
        ):
            for y in range(state.height):
                for x in range(state.width):
                    cls = _cell_class(state, (x, y))
                    ui.element("div").classes(f"w-full h-full {cls}")
        if 0 in ctx.seats and not ctx.match.done:
            _controls(ctx)


def _controls(ctx: RenderContext) -> None:
    def turn(direction: Direction) -> None:
        ctx.submit(0, Turn(direction=direction))

    def on_key(e: KeyEventArguments) -> None:
        if e.action.keydown and (direction := KEYS.get(e.key.name)) is not None:
            turn(direction)

    ui.keyboard(on_key, repeating=False).mark("keys")
    ui.label("Arrow keys or WASD to steer").classes("text-sm text-gray-500")
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
                    on_click=lambda _, d=direction: turn(d),
                ).props("round outline").mark(f"steer-{direction}")
