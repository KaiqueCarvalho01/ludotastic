"""Constrained types shared across Ludotastic."""

__all__: tuple[str, ...] = (
    "NonNegativeFloat",
    "PortNumber",
    "PositiveFloat",
    "PositiveInt",
)

from typing import Annotated

from annotated_types import Ge, Gt, Interval

type PositiveInt = Annotated[int, Gt(0)]
"""A whole number above zero."""

type PositiveFloat = Annotated[float, Gt(0)]
"""A number above zero."""

type NonNegativeFloat = Annotated[float, Ge(0)]
"""A number of zero or more."""

type PortNumber = Annotated[int, Interval(ge=1, le=65535)]
"""A TCP port."""
