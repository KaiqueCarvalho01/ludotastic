"""What AI players spend: requests, tokens and money."""

__all__: tuple[str, ...] = (
    "Usage",
    "format_cost",
    "format_tokens",
)

from collections.abc import Iterable
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class Usage(BaseModel):
    """Model usage, for one move or added up over many.

    `cost` is in US dollars, estimated by Pydantic AI from its price data. It is
    `None` when no price is known for a model, such as Pydantic AI's test
    model. Once any part of a total has no price, `priced` says so, and the
    cost covers only what was priced.
    """

    model_config = ConfigDict(frozen=True)

    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost: Decimal | None = None
    """Estimated cost in US dollars, or `None` if no price is known."""
    priced: bool = True
    """Whether every request counted has a known price."""

    @property
    def tokens(self) -> int:
        """Input and output tokens together."""
        return self.input_tokens + self.output_tokens

    def __add__(self, other: Usage) -> Usage:
        """Add two usages up.

        Examples:
            >>> a = Usage(requests=1, input_tokens=10, cost=Decimal("0.5"))
            >>> b = Usage(requests=1, output_tokens=5)
            >>> total = a + b
            >>> total.requests, total.tokens, total.cost, total.priced
            (2, 15, Decimal('0.5'), False)
        """
        if self.cost is None and other.cost is None:
            cost = None
        else:
            cost = (self.cost or Decimal(0)) + (other.cost or Decimal(0))
        return Usage(
            requests=self.requests + other.requests,
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cost=cost,
            priced=self._fully_priced and other._fully_priced,
        )

    @property
    def _fully_priced(self) -> bool:
        return self.priced and (self.cost is not None or self.requests == 0)

    @staticmethod
    def total(usages: Iterable[Usage]) -> Usage:
        """Add any number of usages up.

        Examples:
            >>> Usage.total([]).requests
            0
        """
        result = Usage()
        for usage in usages:
            result += usage
        return result


def format_cost(cost: Decimal | None, *, priced: bool = True) -> str:
    """Show a cost in dollars: cents for big amounts, 3 significant digits for small.

    Examples:
        >>> format_cost(Decimal("0.000011466"))
        '$0.0000115'
        >>> format_cost(Decimal("0.0421"))
        '$0.0421'
        >>> format_cost(Decimal("12.5"))
        '$12.50'
        >>> format_cost(Decimal(0))
        '$0'
        >>> format_cost(None)
        'n/a'
        >>> format_cost(Decimal("0.5"), priced=False)
        '≥ $0.5'
    """
    if cost is None:
        return "n/a"
    if cost == 0:
        text = "$0"
    elif cost >= 1:
        text = f"${cost:,.2f}"
    else:
        # Enough decimals to keep 3 significant digits, without exponents.
        decimals = 2 - cost.adjusted()
        text = f"${cost:.{decimals}f}".rstrip("0").rstrip(".")
    return text if priced else f"≥ {text}"


def format_tokens(tokens: int) -> str:
    """Show a token count compactly.

    Examples:
        >>> format_tokens(950), format_tokens(12_345), format_tokens(3_400_000)
        ('950', '12.3k', '3.4M')
    """
    if tokens < 1000:  # noqa: PLR2004
        return str(tokens)
    if tokens < 1_000_000:  # noqa: PLR2004
        return f"{tokens / 1000:.1f}k"
    return f"{tokens / 1_000_000:.1f}M"
