"""2048: slide numbered tiles; equal tiles merge."""

__all__: tuple[str, ...] = (
    "Direction",
    "GreedyBot",
    "Slide",
    "TwentyFortyEight",
    "TwentyFortyEightState",
)

from .game import (
    Direction,
    GreedyBot,
    Slide,
    TwentyFortyEight,
    TwentyFortyEightState,
)
