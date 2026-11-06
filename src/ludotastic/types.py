"""Constrained types shared across Ludotastic.

The constraints are checked wherever Pydantic validates a value: model fields,
settings and API bodies. Elsewhere, such as plain function arguments, they
are hints for developers about the values to expect, and are not checked.
"""

__all__: tuple[str, ...] = (
    "Byte",
    "Count",
    "NonNegativeFloat",
    "Pixels",
    "PortNumber",
    "PositiveFloat",
    "PositiveInt",
    "Seat",
)

from typing import Annotated

from annotated_types import Ge, Gt, Interval

type PositiveInt = Annotated[int, Gt(0)]
"""A whole number above zero."""

type PositiveFloat = Annotated[float, Gt(0)]
"""A number above zero."""

type NonNegativeFloat = Annotated[float, Ge(0)]
"""A number of zero or more."""

type Count = Annotated[int, Ge(0)]
"""How many of something: zero or more."""

type Seat = Annotated[int, Ge(0)]
"""A player's seat in a match, numbered from 0 in turn order."""

type PortNumber = Annotated[int, Interval(ge=1, le=65535)]
"""A TCP port."""

type Pixels = Annotated[int, Gt(0)]
"""A length on a picture, in pixels."""

type Byte = Annotated[int, Interval(ge=0, le=255)]
"""One color channel, from 0 to 255."""
