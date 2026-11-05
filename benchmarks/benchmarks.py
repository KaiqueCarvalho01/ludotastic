"""Benchmarking for ludotastic."""

from ludotastic import make_greeting


class TimeSuite:
    """A benchmark suite for timing ludotastic."""

    def setup(self) -> None:
        """Set up the benchmark by initializing the `name` attribute."""
        self.name = "Micael Jarniac"

    def time_make_greeting(self) -> None:
        """Benchmark the `make_greeting` function for its execution time."""
        make_greeting(self.name)


class MemSuite:
    """A benchmark suite for measuring the memory usage of ludotastic."""

    def setup(self) -> None:
        """Set up the benchmark by initializing the `name` attribute."""
        self.name = "Micael Jarniac"

    def mem_make_greeting(self) -> str:
        """Benchmark the `make_greeting` function for its memory usage."""
        return make_greeting(self.name)
