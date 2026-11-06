"""Configuration, read from the environment and `.env` files."""

from functools import cache
from pathlib import Path

from platformdirs import user_data_path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["Settings", "get_settings"]


class Settings(BaseSettings):
    """Ludotastic's settings.

    Every field can be set through a `LUDOTASTIC_`-prefixed environment variable,
    such as `LUDOTASTIC_PORT=9000`, or in a `.env` file. Model provider API keys
    use their usual variables, such as `OPENAI_API_KEY` or `TYPESAFE_API_KEY`.
    """

    model_config = SettingsConfigDict(
        env_prefix="LUDOTASTIC_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "127.0.0.1"
    """Address the server listens on."""
    port: int = Field(default=8080, ge=1, le=65535)
    """Port the server listens on."""
    title: str = "Ludotastic"
    """Title shown in the browser."""
    dark: bool | None = None
    """Dark mode: on, off, or `None` to follow the system."""
    storage_secret: str = "ludotastic-dev-secret"  # noqa: S105
    """Secret for NiceGUI's browser storage; change it when exposing the server."""
    data_dir: Path = Field(default_factory=lambda: user_data_path("ludotastic"))
    """Where match history is stored."""
    database_url: str | None = None
    """SQLAlchemy URL for match history; defaults to SQLite in `data_dir`."""
    default_model: str = "typesafe:jev-latest"
    """The model suggested for new AI players."""
    suggested_models: list[str] = Field(
        default_factory=lambda: [
            "typesafe:jev-latest",
            "openai-decisions:gpt-6-luna",
            "openai:gpt-6.1-sol",
            "anthropic:claude-opus-5-5",
            "google:gemini-3.8-flash",
            "test",
        ]
    )
    """Models offered in the UI; any Pydantic AI model name also works."""
    ai_delay: float = Field(default=0.5, ge=0)
    """Seconds to pause between turns when no human is playing."""
    turn_timeout: float | None = Field(default=None, gt=0)
    """Seconds a player may think in step-based games before forfeiting."""
    max_turns: int | None = Field(default=1000, gt=0)
    """Turns after which a match is called a draw."""

    @property
    def resolved_database_url(self) -> str:
        """The database URL, defaulting to SQLite in the data directory."""
        if self.database_url is not None:
            return self.database_url
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{self.data_dir / 'ludotastic.db'}"


@cache
def get_settings() -> Settings:
    """The settings, read once."""
    return Settings()
