"""Interceptors: authentication, and request logging.

The auth interceptor resolves a bearer token into a :class:`Principal` and binds it
to the request context. It deliberately does *not* reject anonymous calls — some
RPCs (login, register, password reset) are public. Enforcement is per-handler,
through :func:`todoapp.auth.context.require_principal` and its stricter siblings, so
a new RPC is anonymous only when its implementation says so out loud.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, Final

from connectrpc.errors import ConnectError
from connectrpc.request import RequestContext

from todoapp.auth import tokens
from todoapp.auth.context import Principal, bind_principal
from todoapp.db.pool import Database
from todoapp.errors import internal
from todoapp.repositories import sessions as sessions_repo

logger = logging.getLogger("todoapp.rpc")

_BEARER_PREFIX: Final = "bearer "
# Browsers cannot attach an Authorization header to a Connect call without custom
# fetch plumbing, so the web client sends the session in a cookie instead.
SESSION_COOKIE_NAME: Final = "todoapp_session"


def _token_from_headers(ctx: RequestContext) -> str | None:
    """Extracts a session token from ``Authorization`` or the session cookie."""
    headers = ctx.request_headers()

    authorization = headers.get("authorization", "")
    if authorization.lower().startswith(_BEARER_PREFIX):
        token = authorization[len(_BEARER_PREFIX) :].strip()
        if token:
            return token

    cookie_header = headers.get("cookie", "")
    for part in cookie_header.split(";"):
        name, _, value = part.strip().partition("=")
        if name == SESSION_COOKIE_NAME and value:
            return value.strip()
    return None


class AuthenticationInterceptor:
    """Resolves the caller's session once per request.

    One database round-trip per authenticated call. That is the honest cost of
    server-side sessions, and it buys instant revocation — the alternative, a
    self-describing token, cannot be withdrawn before it expires.
    """

    def __init__(self, database: Database) -> None:
        """Stores the pool the interceptor reads sessions from."""
        self._database = database

    async def intercept_unary(
        self,
        call_next: Callable[[Any, RequestContext], Awaitable[Any]],
        request: Any,
        ctx: RequestContext,
    ) -> Any:
        """Binds a :class:`Principal` when a valid session token is present."""
        token = _token_from_headers(ctx)
        if token is not None:
            row = await self._resolve(token)
            if row is not None:
                bind_principal(
                    ctx,
                    Principal(
                        user_id=str(row["user_id"]),
                        session_id=str(row["session_id"]),
                        email=str(row["email"]),
                        display_name=row["display_name"],
                        role=row["role"],
                        status=row["status"],
                        locale=row["locale"],
                        email_verified=row["email_verified"],
                        session_expires_at=row["session_expires_at"],
                    ),
                )
        return await call_next(request, ctx)

    async def _resolve(self, token: str) -> dict[str, Any] | None:
        """Looks up a session, tolerating a database blip on an anonymous path."""
        try:
            async with self._database.connection() as conn:
                return await sessions_repo.resolve(conn, tokens.hash_token(token))
        except Exception:
            # A failure here must not turn every public RPC into a 500; the handler's
            # own guard will reject the call as unauthenticated instead.
            logger.exception("failed to resolve session token")
            return None


class DatabaseErrorInterceptor:
    """Turns an unhandled database error into a plain ``INTERNAL``.

    Without this, ``connect-python`` reports an unexpected exception's ``str()`` to
    the client — which for a psycopg error is the failing SQL, complete with column
    names and a caret pointing at the offending parameter. That belongs in the log,
    not on the wire.

    Placed outermost so it also catches a failure raised inside another interceptor.
    """

    async def intercept_unary(
        self,
        call_next: Callable[[Any, RequestContext], Awaitable[Any]],
        request: Any,
        ctx: RequestContext,
    ) -> Any:
        """Passes :class:`ConnectError` through and masks anything else."""
        try:
            return await call_next(request, ctx)
        except ConnectError:
            # Already a deliberate, client-safe failure.
            raise
        except Exception as err:
            logger.exception(
                "unhandled error in %s/%s",
                ctx.method().service_name,
                ctx.method().name,
            )
            raise internal("an unexpected error occurred") from err


class LoggingInterceptor:
    """Logs one structured line per RPC, with its outcome and duration.

    Deliberately records the caller's id but never the request body: task titles
    and comments are user content and do not belong in an operational log.
    """

    async def intercept_unary(
        self,
        call_next: Callable[[Any, RequestContext], Awaitable[Any]],
        request: Any,
        ctx: RequestContext,
    ) -> Any:
        """Times the call and logs its result."""
        from todoapp.auth.context import current_principal  # Avoids a circular import.

        started = time.perf_counter()
        method = ctx.method().name
        service = ctx.method().service_name
        try:
            response = await call_next(request, ctx)
        except ConnectError as err:
            principal = current_principal(ctx)
            logger.warning(
                "%s/%s failed: %s",
                service,
                method,
                err.code.name,
                extra={
                    "rpc_service": service,
                    "rpc_method": method,
                    "rpc_code": err.code.name,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                    "user_id": principal.user_id if principal else None,
                },
            )
            raise
        except Exception:
            logger.exception(
                "%s/%s raised",
                service,
                method,
                extra={"rpc_service": service, "rpc_method": method},
            )
            raise

        principal = current_principal(ctx)
        logger.info(
            "%s/%s ok",
            service,
            method,
            extra={
                "rpc_service": service,
                "rpc_method": method,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                "user_id": principal.user_id if principal else None,
            },
        )
        return response
