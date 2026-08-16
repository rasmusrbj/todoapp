"""Where the CLI keeps its server address and session token.

``~/.config/todoapp/config.json``, honouring ``XDG_CONFIG_HOME``. The file holds a
live bearer token, so it is created with owner-only permissions and re-chmodded on
every write in case it was created by an older version.
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

DEFAULT_BASE_URL: Final = "http://127.0.0.1:8081"

_ENV_BASE_URL: Final = "TODOAPP_CLI_BASE_URL"
_ENV_TOKEN: Final = "TODOAPP_CLI_TOKEN"
_ENV_LOCALE: Final = "TODOAPP_CLI_LOCALE"


def config_path() -> Path:
    """Returns the config file's location."""
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / "todoapp" / "config.json"


@dataclass(slots=True)
class Config:
    """Persisted CLI state.

    Attributes:
        base_url: Server address, scheme included.
        token: Session bearer token, or ``None`` when signed out.
        email: The signed-in address, kept only so ``whoami`` can answer offline.
        locale: Language for enum display names and dates.
    """

    base_url: str = DEFAULT_BASE_URL
    token: str | None = None
    email: str | None = None
    locale: str = "da"

    @classmethod
    def load(cls) -> Config:
        """Reads the config file, then applies environment overrides.

        A missing or unreadable file is not an error: the CLI must work on a fresh
        machine, and the defaults point at a local development server.
        """
        config = cls()
        path = config_path()
        if path.exists():
            try:
                stored = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                stored = {}
            for field in ("base_url", "token", "email", "locale"):
                if stored.get(field) is not None:
                    setattr(config, field, stored[field])

        # The environment wins, so CI and scripts need no file at all.
        config.base_url = os.environ.get(_ENV_BASE_URL, config.base_url)
        config.token = os.environ.get(_ENV_TOKEN, config.token)
        config.locale = os.environ.get(_ENV_LOCALE, config.locale)
        return config

    def save(self) -> Path:
        """Writes the config file with ``0600`` permissions and returns its path."""
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        return path

    def clear_token(self) -> None:
        """Forgets the session without discarding the server address."""
        self.token = None
        self.email = None
