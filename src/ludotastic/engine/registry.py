"""Discovering games through Python entry points."""

from collections.abc import Iterator, Mapping
from importlib.metadata import EntryPoint, entry_points
from typing import Any, override

from loguru import logger

from ludotastic.engine.game import Game

__all__ = ["ENTRY_POINT_GROUP", "GameRegistry", "registry"]

ENTRY_POINT_GROUP = "ludotastic.games"
"""The entry-point group games register under.

A package makes a game available by declaring, in its `pyproject.toml`:

```toml
[project.entry-points."ludotastic.games"]
my-game = "my_package.my_game:MyGame"
```
"""

type GameType = type[Game[Any, Any]]


class GameRegistry(Mapping[str, GameType]):
    """The games available, by id.

    Games are loaded from the [`ludotastic.games`][ludotastic.ENTRY_POINT_GROUP]
    entry-point group the first time the registry is used. Games can also be
    registered by hand, which is handy in tests and notebooks.
    """

    def __init__(self, *, group: str = ENTRY_POINT_GROUP) -> None:
        """Create an empty registry reading from `group`."""
        self.group = group
        self._games: dict[str, GameType] = {}
        self._errors: dict[str, str] = {}
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        for entry_point in entry_points(group=self.group):
            self._load_entry_point(entry_point)

    def _load_entry_point(self, entry_point: EntryPoint) -> None:
        try:
            game = entry_point.load()
            self.register(game)
        except Exception as e:  # noqa: BLE001
            logger.warning("Could not load game {!r}: {}", entry_point.name, e)
            self._errors[entry_point.name] = f"{type(e).__name__}: {e}"

    def register[G: GameType](self, game: G) -> G:
        """Add a game; usable as a class decorator.

        Raises:
            TypeError: If `game` is not a [`Game`][ludotastic.Game] subclass.
            ValueError: If another game already has the same id.
        """
        if not (isinstance(game, type) and issubclass(game, Game)):
            msg = f"{game!r} is not a Game subclass"
            raise TypeError(msg)
        game_id = game.info.id
        if (existing := self._games.get(game_id)) is not None and existing is not game:
            msg = f"Game id {game_id!r} is taken by {existing.__qualname__}"
            raise ValueError(msg)
        self._games[game_id] = game
        return game

    @property
    def errors(self) -> Mapping[str, str]:
        """Entry points that failed to load, with the error."""
        self._load()
        return dict(self._errors)

    @override
    def __getitem__(self, game_id: str) -> GameType:
        """Look a game up by id."""
        self._load()
        return self._games[game_id]

    @override
    def __iter__(self) -> Iterator[str]:
        """Iterate over the game ids, sorted."""
        self._load()
        return iter(sorted(self._games))

    @override
    def __len__(self) -> int:
        """Count the games."""
        self._load()
        return len(self._games)


registry = GameRegistry()
"""The default registry, filled from installed packages."""
