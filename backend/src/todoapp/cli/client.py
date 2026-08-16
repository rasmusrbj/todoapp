"""Connect client construction, error reporting, and id-prefix resolution."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Final, NoReturn

from connectrpc.codec import proto_json_codec
from connectrpc.errors import ConnectError

from todo.v1.auth_connect import AuthServiceClientSync
from todo.v1.errors_pb2 import ErrorDetail, ErrorReason
from todo.v1.list_connect import ListServiceClientSync
from todo.v1.task_connect import TaskServiceClientSync
from todo.v1.user_connect import UserServiceClientSync
from todoapp.cli import output
from todoapp.cli.config import Config

# The CLI sends and receives JSON rather than binary protobuf. It costs a little
# bandwidth and buys the ability to reproduce any call with curl from a log line.
_CODEC: Final = proto_json_codec()


class CliError(Exception):
    """A failure that should print as one line and exit non-zero."""

    def __init__(self, message: str, *, hint: str | None = None, exit_code: int = 1) -> None:
        """Stores the message, an optional next step, and the exit code."""
        super().__init__(message)
        self.hint = hint
        self.exit_code = exit_code


@dataclass(slots=True)
class Api:
    """The four service clients, sharing one address and one session token."""

    auth: AuthServiceClientSync
    users: UserServiceClientSync
    lists: ListServiceClientSync
    tasks: TaskServiceClientSync
    config: Config

    @property
    def headers(self) -> dict[str, str]:
        """The auth header for a call, or an empty mapping when signed out."""
        return {"Authorization": f"Bearer {self.config.token}"} if self.config.token else {}

    def require_token(self) -> dict[str, str]:
        """Returns the auth header, refusing to proceed when signed out.

        Raises:
            CliError: When no token is stored.
        """
        if not self.config.token:
            raise CliError(
                "You are not signed in.", hint="Run: todoapp auth login --email you@example.com"
            )
        return self.headers


def build(config: Config) -> Api:
    """Builds the service clients for ``config``."""
    kwargs = {"codec": _CODEC, "timeout_ms": 30_000}
    return Api(
        auth=AuthServiceClientSync(config.base_url, **kwargs),  # type: ignore[arg-type]
        users=UserServiceClientSync(config.base_url, **kwargs),  # type: ignore[arg-type]
        lists=ListServiceClientSync(config.base_url, **kwargs),  # type: ignore[arg-type]
        tasks=TaskServiceClientSync(config.base_url, **kwargs),  # type: ignore[arg-type]
        config=config,
    )


# Reasons worth a specific next step rather than the generic message.
_HINTS: Final[dict[int, str]] = {
    ErrorReason.ERROR_REASON_NOT_AUTHENTICATED: "Run: todoapp auth login",
    ErrorReason.ERROR_REASON_SESSION_EXPIRED: "Your session expired. Run: todoapp auth login",
    ErrorReason.ERROR_REASON_EMAIL_NOT_VERIFIED: (
        "Confirm your email first. Run: todoapp auth resend-verification"
    ),
    ErrorReason.ERROR_REASON_ADMIN_REQUIRED: "This needs the admin role.",
    ErrorReason.ERROR_REASON_OWNER_REQUIRED: "Only the list owner can do this.",
    ErrorReason.ERROR_REASON_RATE_LIMITED: "Too many attempts. Wait a few minutes.",
}


def detail_of(error: ConnectError) -> ErrorDetail | None:
    """Extracts the :class:`todo.v1.ErrorDetail` from a Connect error, if present."""
    for packed in error.details:
        if packed.type_url.endswith("todo.v1.ErrorDetail"):
            detail = ErrorDetail()
            packed.Unpack(detail)
            return detail
    return None


def describe(error: ConnectError, *, locale: str = "da") -> tuple[str, str | None]:
    """Turns a Connect error into a message and an optional hint.

    The server's ``message`` is English developer text; a real product would show a
    localized string keyed on the reason. The CLI prints the developer text — its
    audience is the developer — but still surfaces the reason and a concrete next
    step, and the field name when one input is at fault.
    """
    del locale  # Reserved: the reason is the key a localized catalogue would use.
    detail = detail_of(error)
    message = error.message or error.code.name

    if detail is None:
        return message, None

    reason_name = ErrorReason.Name(detail.reason)
    parts = [message, output.paint(f"({reason_name})", "dim")]
    if detail.field:
        parts.insert(1, output.paint(f"[{detail.field}]", "dim"))
    return " ".join(parts), _HINTS.get(detail.reason)


def die(error: ConnectError, *, locale: str = "da") -> NoReturn:
    """Prints a Connect error and exits.

    Raises:
        SystemExit: Always. Exit code 3 for an authorization failure so a script can
            tell "not allowed" apart from "bad usage" (2) and everything else (1).
    """
    message, hint = describe(error, locale=locale)
    output.error(message)
    if hint:
        print(f"  {output.paint(hint, 'dim')}", file=sys.stderr)
    detail = detail_of(error)
    auth_failure = detail is not None and detail.reason in {
        ErrorReason.ERROR_REASON_NOT_AUTHENTICATED,
        ErrorReason.ERROR_REASON_SESSION_EXPIRED,
        ErrorReason.ERROR_REASON_PERMISSION_DENIED,
        ErrorReason.ERROR_REASON_ADMIN_REQUIRED,
        ErrorReason.ERROR_REASON_OWNER_REQUIRED,
    }
    raise SystemExit(3 if auth_failure else 1)


def resolve_id(prefix: str, candidates: dict[str, str], *, kind: str) -> str:
    """Expands a short id prefix to a full one.

    Listings print truncated ids, so the CLI accepts them back. A prefix matching
    several rows is rejected rather than guessed at — picking one silently would
    eventually delete the wrong thing.

    Args:
        prefix: What the user typed. A full UUID passes straight through.
        candidates: Full id to a human label, for the ambiguity message.
        kind: Noun used in the error, e.g. ``task``.

    Returns:
        The full id.

    Raises:
        CliError: When nothing or more than one thing matches.
    """
    if prefix in candidates:
        return prefix

    matches = [full for full in candidates if full.startswith(prefix)]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise CliError(
            f"No {kind} matches {prefix!r}.",
            hint=f"Run: todoapp {kind}s list",
        )
    listed = "\n".join(
        f"  {output.short_id(full)}  {candidates[full]}" for full in sorted(matches)[:10]
    )
    raise CliError(f"{prefix!r} matches {len(matches)} {kind}s:\n{listed}")
