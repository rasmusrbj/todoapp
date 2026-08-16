"""Per-call authenticated principal.

``connectrpc``'s :class:`~connectrpc.request.RequestContext` has no user-extensible
slot, so the principal resolved by :mod:`todoapp.auth.interceptor` is kept in a
:class:`weakref.WeakKeyDictionary` keyed by the context object. That keeps the
generated code untouched and lets the entry disappear with the request rather than
leaking for the process lifetime.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final
from weakref import WeakKeyDictionary

from connectrpc.request import RequestContext

from todoapp.errors import Reason, permission_denied, unauthenticated


@dataclass(frozen=True, slots=True)
class Principal:
    """The authenticated caller of one RPC.

    Immutable on purpose: a handler must not be able to widen its own permissions
    halfway through a call.

    Attributes:
        user_id: The user's UUID as text.
        session_id: The session used for this call, as text.
        email: The user's email address.
        display_name: Name for activity attribution.
        role: PostgreSQL ``user_role`` label — ``member`` or ``admin``.
        status: PostgreSQL ``user_status`` label.
        locale: PostgreSQL ``locale`` label, used to pick an email language.
        email_verified: Whether the address has been confirmed.
        session_expires_at: When the session stops being valid.
    """

    user_id: str
    session_id: str
    email: str
    display_name: str
    role: str
    status: str
    locale: str
    email_verified: bool
    session_expires_at: datetime

    @property
    def is_admin(self) -> bool:
        """Whether this caller holds the platform admin role."""
        return self.role == "admin"


_principals: Final[WeakKeyDictionary[RequestContext, Principal]] = WeakKeyDictionary()


def bind_principal(ctx: RequestContext, principal: Principal) -> None:
    """Associates ``principal`` with ``ctx`` for the duration of the call."""
    _principals[ctx] = principal


def current_principal(ctx: RequestContext) -> Principal | None:
    """Returns the caller, or ``None`` for an anonymous call."""
    return _principals.get(ctx)


def require_principal(ctx: RequestContext) -> Principal:
    """Returns the caller, rejecting anonymous and non-signed-in-able accounts.

    Raises:
        ConnectError: ``UNAUTHENTICATED`` when no valid session was presented,
            ``PERMISSION_DENIED`` when the account exists but is suspended or
            deactivated.
    """
    principal = _principals.get(ctx)
    if principal is None:
        raise unauthenticated()
    if principal.status == "suspended":
        raise permission_denied(Reason.ERROR_REASON_ACCOUNT_SUSPENDED, "account is suspended")
    if principal.status == "deactivated":
        raise permission_denied(Reason.ERROR_REASON_ACCOUNT_DEACTIVATED, "account is deactivated")
    return principal


def require_admin(ctx: RequestContext) -> Principal:
    """Returns the caller, requiring the platform admin role.

    Raises:
        ConnectError: ``PERMISSION_DENIED`` for a non-admin caller.
    """
    principal = require_principal(ctx)
    if not principal.is_admin:
        raise permission_denied(Reason.ERROR_REASON_ADMIN_REQUIRED, "admin role required")
    return principal


def require_verified_email(ctx: RequestContext) -> Principal:
    """Returns the caller, requiring a confirmed email address.

    Used by the RPCs that reach other people — sharing a list, in particular — so
    an unverified address cannot be used to spam invitations.

    Raises:
        ConnectError: ``PERMISSION_DENIED`` when the address is unconfirmed.
    """
    principal = require_principal(ctx)
    if not principal.email_verified:
        raise permission_denied(
            Reason.ERROR_REASON_EMAIL_NOT_VERIFIED, "email address is not verified"
        )
    return principal
