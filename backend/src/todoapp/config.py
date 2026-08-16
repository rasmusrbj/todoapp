"""Application settings, resolved once at startup from the environment."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration.

    Every value is overridable by an environment variable of the same name,
    upper-cased and prefixed with ``TODOAPP_``. A local ``.env`` is read when
    present, which is why nothing here carries a production-safe default that
    would silently mask a missing variable.
    """

    model_config = SettingsConfigDict(
        env_prefix="TODOAPP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    host: str = "127.0.0.1"
    port: int = 8081

    database_url: str = "postgresql://postgres@localhost:5432/todoapp"
    db_pool_min_size: int = 2
    db_pool_max_size: int = 10

    # Browsers must be listed explicitly: Connect sends custom headers, so every
    # call is preflighted and a wildcard origin cannot carry credentials.
    #
    # `NoDecode` turns off pydantic-settings' automatic JSON parsing of complex
    # types, which would otherwise reject the plain comma-separated form before
    # `_split_origins` below ever runs.
    cors_allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    # Where the web app lives. Used to build the links in outgoing email, so it must
    # match the deployment or every verification link will 404.
    web_base_url: str = "http://localhost:3000"

    # Set on the session cookie. Off in development because localhost is plain HTTP;
    # a production deployment must serve HTTPS and leave this on.
    session_cookie_secure: bool = False
    session_cookie_domain: str = ""

    session_ttl_hours: int = 24 * 30
    password_reset_ttl_minutes: int = 60
    email_verification_ttl_hours: int = 48
    min_password_length: int = 10

    # Argon2id parameters. The defaults follow the OWASP "second recommended"
    # configuration (19 MiB, t=2, p=1) and are lowered only under `test`.
    argon2_time_cost: int = 2
    argon2_memory_cost_kib: int = 19_456
    argon2_parallelism: int = 1

    # How many failed logins one email address may accumulate before the endpoint
    # starts refusing, and the window those failures are counted over.
    login_max_attempts: int = 10
    login_attempt_window_minutes: int = 15

    # Reserved for future stateless tokens. Sessions are opaque and stored
    # server-side, so verifying one needs no secret.
    secret_key: SecretStr = SecretStr("dev-only-change-me")

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept a comma-separated string as well as a JSON list."""
        if isinstance(value, str) and not value.strip().startswith("["):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def is_production(self) -> bool:
        """True when running with production hardening enabled."""
        return self.environment == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Returns the process-wide settings, parsed on first use."""
    return Settings()
