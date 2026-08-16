"""ASGI entry point.

``connect-python`` generates one ASGI application per service, each answering under
its own ``/<package>.<Service>/`` prefix. :class:`Router` mounts all four behind a
single callable, adds the CORS handling a browser Connect client needs, and serves
``/healthz`` and ``/readyz``.

Run it with::

    uv run uvicorn todoapp.main:app --port 8080
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable, Iterable
from typing import Any, Final

from connectrpc.interceptor import Interceptor

from todo.v1.auth_connect import AuthServiceASGIApplication
from todo.v1.list_connect import ListServiceASGIApplication
from todo.v1.task_connect import TaskServiceASGIApplication
from todo.v1.user_connect import UserServiceASGIApplication
from todoapp.auth.interceptor import (
    AuthenticationInterceptor,
    DatabaseErrorInterceptor,
    LoggingInterceptor,
)
from todoapp.config import Settings, get_settings
from todoapp.db.pool import Database, get_database
from todoapp.logging_config import configure_logging
from todoapp.mail import LoggingMailer, Mailer
from todoapp.services.auth_service import AuthService
from todoapp.services.list_service import ListService
from todoapp.services.task_service import TaskService
from todoapp.services.user_service import UserService

logger = logging.getLogger("todoapp.main")

Scope = dict[str, Any]
Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]

# Headers a Connect browser client sends, and the ones it needs to read back.
# `Authorization` is included for non-browser clients; the web app uses a cookie.
_CORS_REQUEST_HEADERS: Final = (
    "Content-Type, Connect-Protocol-Version, Connect-Timeout-Ms, Authorization, "
    "X-User-Agent, Connect-Content-Encoding, Connect-Accept-Encoding"
)
_CORS_EXPOSE_HEADERS: Final = (
    "Content-Encoding, Connect-Content-Encoding, Connect-Accept-Encoding, Grpc-Status, Grpc-Message"
)
_CORS_MAX_AGE: Final = "7200"


class Router:
    """Dispatches ASGI requests to the right Connect application.

    Also the place CORS is handled. It is not middleware over the Connect apps
    because a preflight ``OPTIONS`` must be answered *without* reaching a handler —
    the generated applications only accept ``POST``.
    """

    def __init__(
        self,
        *,
        applications: Iterable[Any],
        allowed_origins: Iterable[str],
        database: Database,
    ) -> None:
        """Builds the path table from each application's own ``path`` property."""
        self._routes = {app.path.rstrip("/"): app for app in applications}
        self._allowed_origins = frozenset(allowed_origins)
        # The pool is held rather than looked up globally, so the readiness probe
        # and the lifespan hooks act on the same pool the services were given.
        self._database = database
        logger.info("serving %d Connect services", len(self._routes))
        for path in sorted(self._routes):
            logger.debug("route %s", path)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Routes one ASGI event stream."""
        if scope["type"] == "lifespan":
            await self._lifespan(scope, receive, send)
            return
        if scope["type"] != "http":
            return

        path: str = scope["path"]
        headers = {key.decode(): value.decode() for key, value in scope.get("headers", [])}
        origin = headers.get("origin", "")

        if scope["method"] == "OPTIONS":
            await self._preflight(origin, send)
            return

        if path in ("/healthz", "/readyz"):
            await self._health(path, send)
            return

        # Longest-prefix match: a service path is `/todo.v1.Foo/Method`.
        service_path = "/" + path.lstrip("/").split("/")[0]
        application = self._routes.get(service_path)
        if application is None:
            await _send_json(send, 404, {"code": "not_found", "message": f"no route for {path}"})
            return

        await application(scope, receive, self._with_cors(send, origin))

    # --- Internals ----------------------------------------------------------

    def _allow(self, origin: str) -> str | None:
        """Returns the origin to echo back, or ``None`` if it is not allowed."""
        return origin if origin and origin in self._allowed_origins else None

    def _with_cors(self, send: Send, origin: str) -> Send:
        """Wraps ``send`` so the response start carries the CORS headers."""
        allowed = self._allow(origin)
        if allowed is None:
            return send

        async def send_with_cors(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                message = {
                    **message,
                    "headers": [
                        *message.get("headers", []),
                        (b"access-control-allow-origin", allowed.encode()),
                        (b"access-control-allow-credentials", b"true"),
                        (b"access-control-expose-headers", _CORS_EXPOSE_HEADERS.encode()),
                        # The allowed origin varies per request, so caches must not
                        # reuse one origin's response for another.
                        (b"vary", b"Origin"),
                    ],
                }
            await send(message)

        return send_with_cors

    async def _preflight(self, origin: str, send: Send) -> None:
        """Answers a CORS preflight."""
        allowed = self._allow(origin)
        if allowed is None:
            await _send_json(
                send, 403, {"code": "permission_denied", "message": "origin not allowed"}
            )
            return
        await send(
            {
                "type": "http.response.start",
                "status": 204,
                "headers": [
                    (b"access-control-allow-origin", allowed.encode()),
                    (b"access-control-allow-credentials", b"true"),
                    (b"access-control-allow-methods", b"POST, GET, OPTIONS"),
                    (b"access-control-allow-headers", _CORS_REQUEST_HEADERS.encode()),
                    (b"access-control-max-age", _CORS_MAX_AGE.encode()),
                    (b"vary", b"Origin"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": b""})

    async def _health(self, path: str, send: Send) -> None:
        """Answers a liveness or readiness probe.

        ``/healthz`` says the process is up. ``/readyz`` also checks that the pool
        can reach PostgreSQL, so a rolling deploy does not send traffic to an
        instance whose database is unreachable.
        """
        if path == "/healthz":
            await _send_json(send, 200, {"status": "ok"})
            return
        try:
            async with self._database.connection() as conn:
                await conn.execute("SELECT 1")
        except Exception as err:
            logger.warning("readiness check failed: %s", err)
            await _send_json(send, 503, {"status": "unavailable", "database": "unreachable"})
            return
        await _send_json(send, 200, {"status": "ok", "database": "ok"})

    async def _lifespan(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Opens the pool on startup and closes it on shutdown."""
        del scope
        database = self._database
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                try:
                    await database.open()
                except Exception as err:
                    logger.exception("startup failed")
                    await send({"type": "lifespan.startup.failed", "message": str(err)})
                    return
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await database.close()
                await send({"type": "lifespan.shutdown.complete"})
                return


async def _send_json(send: Send, status: int, payload: dict[str, Any]) -> None:
    """Writes a small JSON response."""
    body = json.dumps(payload).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


def create_app(
    *,
    settings: Settings | None = None,
    database: Database | None = None,
    mailer: Mailer | None = None,
) -> Router:
    """Builds the ASGI application.

    Everything is injectable so the test suite can hand in a test database and a
    capturing mailer without touching the environment.

    Args:
        settings: Resolved configuration. Defaults to the process settings.
        database: Connection pool wrapper. Defaults to the process pool.
        mailer: Email transport. Defaults to :class:`LoggingMailer`.

    Returns:
        The composed :class:`Router`.
    """
    settings = settings or get_settings()
    database = database or get_database()
    mailer = mailer or LoggingMailer()
    configure_logging(settings)

    # Order matters, outermost first: the error mask must see everything the other
    # two can raise, logging must still record a rejected call, and authentication
    # runs last so the principal is bound before any handler executes.
    interceptors: list[Interceptor] = [
        DatabaseErrorInterceptor(),
        LoggingInterceptor(),
        AuthenticationInterceptor(database),
    ]

    return Router(
        applications=[
            AuthServiceASGIApplication(
                AuthService(database=database, settings=settings, mailer=mailer),
                interceptors=interceptors,
            ),
            UserServiceASGIApplication(
                UserService(database=database, settings=settings),
                interceptors=interceptors,
            ),
            ListServiceASGIApplication(ListService(database=database), interceptors=interceptors),
            TaskServiceASGIApplication(TaskService(database=database), interceptors=interceptors),
        ],
        allowed_origins=settings.cors_allowed_origins,
        database=database,
    )


app = create_app()
