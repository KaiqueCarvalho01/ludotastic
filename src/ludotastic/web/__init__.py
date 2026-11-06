"""The web app: the NiceGUI playground and the REST API, served together."""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from nicegui import ui

from ludotastic.api import mount_api
from ludotastic.service import MatchService
from ludotastic.web.pages import build_root

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

__all__ = ["build_root", "create_app"]


def create_app(service: MatchService | None = None) -> FastAPI:
    """Build the FastAPI app, with the API under `/api` and the UI at `/`."""
    service = service or MatchService()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        yield
        service.close()

    app = FastAPI(
        title="Ludotastic",
        summary="Where humans and AI come to play.",
        lifespan=lifespan,
    )
    mount_api(app, service)
    settings = service.settings
    ui.run_with(
        app,
        root=build_root(service),
        title=settings.title,
        dark=settings.dark,
        storage_secret=settings.storage_secret,
        show_welcome_message=False,
    )
    return app
