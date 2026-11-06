"""Shared fixtures."""

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from ludotastic.service import MatchService
from ludotastic.settings import Settings
from ludotastic.storage import Store
from ludotastic.web.pages import build_root

pytest_plugins = ["nicegui.testing.general_fixtures"]


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Settings that keep everything in a temporary directory."""
    return Settings(
        _env_file=None,
        data_dir=tmp_path,
        ai_delay=0.0,
        suggested_models=["test"],
        default_model="test",
    )


@pytest.fixture
def store() -> Iterator[Store]:
    """An in-memory store."""
    store = Store("sqlite://")
    yield store
    store.close()


@pytest.fixture
def service(settings: Settings, store: Store) -> Iterator[MatchService]:
    """A match service with in-memory storage."""
    service = MatchService(settings=settings, store=store)
    yield service
    service.shutdown()


@pytest.fixture
async def user(service: MatchService) -> AsyncIterator[User]:
    """A simulated browser user, on the playground."""
    async with user_simulation(build_root(service)) as user:
        yield user
