"""Testing for ludotastic."""

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st
from inline_snapshot import snapshot

from ludotastic import make_greeting

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture


def test_make_greeting_benchmark(benchmark: BenchmarkFixture) -> None:
    """Test `make_greeting`."""
    result = benchmark(make_greeting, "Micael Jarniac")
    assert result == "Hello, Micael Jarniac. Welcome to your new project!"


@given(name=st.text())
def test_make_greeting_hypothesis(name: str) -> None:
    """Test `make_greeting`."""
    result = make_greeting(name)
    assert result == f"Hello, {name}. Welcome to your new project!"


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Foo", snapshot("Hello, Foo. Welcome to your new project!")),
        ("Bar", snapshot("Hello, Bar. Welcome to your new project!")),
    ],
)
def test_make_greeting_snapshot(name: str, expected: str) -> None:
    """Test `make_greeting`."""
    result = make_greeting(name)
    assert result == expected
