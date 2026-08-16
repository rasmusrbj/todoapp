"""Connect client construction, error reporting, and id-prefix resolution."""

from __future__ import annotations

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

    def __init__(
        self,
        message: str,
        *,
        hint: str | None = None,
        exit_code: int = 1,
        reason: str | None = None,
    ) -> None:
        """Stores the message, an optional next step, the exit code, and a reason.

        `reason` is an `ErrorReason` name when the failure maps onto one, so the
        `--json` form gives a program the same stable key the server would have sent.
        Locally-detected problems (an ambiguous id prefix, say) leave it unset.
        """
        super().__init__(message)
        self.hint = hint
        self.exit_code = exit_code
        self.reason = reason


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
                "You are not signed in.",
                hint="Run: todoapp auth login --email you@example.com",
                # 3, not the default 1: this is "not allowed", which is what the
                # documented exit-code contract promises and what lets a caller know
                # signing in would fix it.
                exit_code=3,
                reason="ERROR_REASON_NOT_AUTHENTICATED",
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


def _plain_message(error: ConnectError, *, locale: str = "da") -> str:
    """The server's message with no decoration, for the JSON form."""
    del locale  # Reserved, like `describe`: the reason is the localization key.
    return error.message or error.code.name


#: Reasons that mean "you may not do this", as opposed to "that request was wrong".
#: Exit code 3 lets a script or an agent retry after signing in rather than treating it
#: as a bad command.
_AUTH_REASONS: Final = frozenset(
    {
        ErrorReason.ERROR_REASON_NOT_AUTHENTICATED,
        ErrorReason.ERROR_REASON_SESSION_EXPIRED,
        ErrorReason.ERROR_REASON_PERMISSION_DENIED,
        ErrorReason.ERROR_REASON_ADMIN_REQUIRED,
        ErrorReason.ERROR_REASON_OWNER_REQUIRED,
    }
)


def die(error: ConnectError, *, locale: str = "da", as_json_output: bool = False) -> NoReturn:
    """Prints a Connect error and exits.

    In `--json` mode the failure is a JSON object on stderr carrying the machine-readable
    `ErrorReason`, so a program driving the CLI branches on `reason` rather than matching
    localized prose.

    Raises:
        SystemExit: Always. Exit code 3 for an authorization failure so a caller can tell
            "not allowed" apart from "bad usage" (2) and everything else (1).
    """
    detail = detail_of(error)
    auth_failure = detail is not None and detail.reason in _AUTH_REASONS
    exit_code = 3 if auth_failure else 1

    if as_json_output:
        # The bare server message, not the decorated human line: a program does not want
        # "(ERROR_REASON_TASK_NOT_FOUND)" appended to a sentence it will never show.
        output.fail(
            _plain_message(error, locale=locale),
            as_json_output=True,
            reason=ErrorReason.Name(detail.reason) if detail else None,
            field=detail.field if detail and detail.field else None,
            metadata=dict(detail.metadata) if detail and detail.metadata else None,
            hint=_HINTS.get(detail.reason) if detail else None,
            exit_code=exit_code,
        )
        raise SystemExit(exit_code)

    message, hint = describe(error, locale=locale)
    output.fail(message, as_json_output=False, hint=hint)
    raise SystemExit(exit_code)


#: The reason the server would send for "no such <kind>", so a locally-detected
#: not-found is indistinguishable to a caller branching on `reason`.
_NOT_FOUND_REASONS: Final = {
    "task": "ERROR_REASON_TASK_NOT_FOUND",
    "list": "ERROR_REASON_LIST_NOT_FOUND",
    "label": "ERROR_REASON_LABEL_NOT_FOUND",
    "comment": "ERROR_REASON_COMMENT_NOT_FOUND",
    "subtask": "ERROR_REASON_SUBTASK_NOT_FOUND",
    "user": "ERROR_REASON_USER_NOT_FOUND",
    "session": "ERROR_REASON_SESSION_NOT_FOUND",
    "member": "ERROR_REASON_MEMBER_NOT_FOUND",
}


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
            reason=_NOT_FOUND_REASONS.get(kind),
        )
    listed = "\n".join(
        f"  {output.short_id(full)}  {candidates[full]}" for full in sorted(matches)[:10]
    )
    # Ambiguity is the caller's mistake, not a missing row, so it stays reason-less:
    # there is no server reason for "you gave me half an id that fits two things".
    raise CliError(f"{prefix!r} matches {len(matches)} {kind}s:\n{listed}")
