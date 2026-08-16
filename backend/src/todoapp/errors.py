"""Typed error construction.

Every failure leaving this service is a :class:`connectrpc.errors.ConnectError`
carrying a :class:`todo.v1.ErrorDetail` with a machine-readable
:class:`todo.v1.ErrorReason`. Clients localize the reason; the ``message`` string
is English developer text for logs and must never be shown to a user.
"""

from __future__ import annotations

from collections.abc import Mapping

from connectrpc.code import Code
from connectrpc.errors import ConnectError

from todo.v1.errors_pb2 import ErrorDetail, ErrorReason

# Short alias; `Reason.ERROR_REASON_*` reads better at call sites than the full
# generated name, and `ErrorReason` doubles as the annotation type.
Reason = ErrorReason


def _error(
    code: Code,
    reason: ErrorReason,
    message: str,
    *,
    field: str = "",
    metadata: Mapping[str, str] | None = None,
) -> ConnectError:
    detail = ErrorDetail(reason=reason, field=field, metadata=dict(metadata or {}))
    return ConnectError(code, message, details=[detail])


def invalid_argument(
    reason: ErrorReason,
    message: str,
    *,
    field: str = "",
    metadata: Mapping[str, str] | None = None,
) -> ConnectError:
    """A malformed or unacceptable request."""
    return _error(Code.INVALID_ARGUMENT, reason, message, field=field, metadata=metadata)


def unauthenticated(
    reason: ErrorReason = Reason.ERROR_REASON_NOT_AUTHENTICATED,
    message: str = "authentication required",
) -> ConnectError:
    """No usable credentials were presented."""
    return _error(Code.UNAUTHENTICATED, reason, message)


def permission_denied(
    reason: ErrorReason = Reason.ERROR_REASON_PERMISSION_DENIED,
    message: str = "permission denied",
) -> ConnectError:
    """The caller is known but not allowed to do this."""
    return _error(Code.PERMISSION_DENIED, reason, message)


def not_found(
    reason: ErrorReason,
    message: str,
    *,
    metadata: Mapping[str, str] | None = None,
) -> ConnectError:
    """The addressed resource does not exist, or is hidden from this caller.

    Resources the caller may not read are reported as missing rather than
    forbidden, so the API does not leak the existence of other people's data.
    """
    return _error(Code.NOT_FOUND, reason, message, metadata=metadata)


def already_exists(
    reason: ErrorReason,
    message: str,
    *,
    field: str = "",
) -> ConnectError:
    """A uniqueness constraint would be violated."""
    return _error(Code.ALREADY_EXISTS, reason, message, field=field)


def failed_precondition(
    reason: ErrorReason,
    message: str,
    *,
    field: str = "",
) -> ConnectError:
    """The request is well-formed but the system is in the wrong state for it."""
    return _error(Code.FAILED_PRECONDITION, reason, message, field=field)


def resource_exhausted(
    reason: ErrorReason = Reason.ERROR_REASON_RATE_LIMITED,
    message: str = "too many requests",
    *,
    metadata: Mapping[str, str] | None = None,
) -> ConnectError:
    """A rate limit or quota was hit."""
    return _error(Code.RESOURCE_EXHAUSTED, reason, message, metadata=metadata)


def internal(message: str = "internal error") -> ConnectError:
    """An unexpected server-side failure. Details stay in the logs."""
    return _error(Code.INTERNAL, Reason.ERROR_REASON_INTERNAL, message)
