"""Test fixtures.

The suite runs against a real PostgreSQL database — ``todoapp_test`` by default,
created and migrated once per session. Nothing is mocked below the RPC boundary:
these tests exercise the same SQL, constraints, and enum types that production
does, which is the only way a repository layer written in raw SQL is actually
covered.

Calls go over the wire as Connect JSON through ``httpx``'s ASGI transport, so the
interceptors, routing, and error mapping are all in the path.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import psycopg
import pytest

# Argon2 at production cost makes every registration take ~50 ms; the suite
# registers dozens of users. These must be set before todoapp.config is imported.
os.environ.setdefault("TODOAPP_ENVIRONMENT", "test")
os.environ.setdefault("TODOAPP_LOG_LEVEL", "WARNING")
os.environ.setdefault("TODOAPP_ARGON2_TIME_COST", "1")
os.environ.setdefault("TODOAPP_ARGON2_MEMORY_COST_KIB", "8192")
os.environ.setdefault(
    "TODOAPP_DATABASE_URL",
    os.environ.get(
        "TODOAPP_TEST_DATABASE_URL", "postgresql://postgres@localhost:5432/todoapp_test"
    ),
)

from todoapp.config import get_settings
from todoapp.db.migrate import apply_migrations
from todoapp.db.pool import Database
from todoapp.mail import Message
from todoapp.main import create_app

# Every registered password in the suite. Long and varied enough to satisfy the
# strength policy, so a policy tweak does not break unrelated tests.
PASSWORD = "korrekt-hest-batteri-3"

# Tables truncated between tests. `users` cascades to lists, tasks and sessions;
# the other two have no foreign key into it.
_TRUNCATED_TABLES = "users, activities, login_attempts"


class CapturingMailer:
    """A :class:`todoapp.mail.Mailer` that records instead of sending."""

    def __init__(self) -> None:
        """Starts with an empty outbox."""
        self.outbox: list[Message] = []

    async def send(self, message: Message) -> None:
        """Appends ``message`` to :attr:`outbox`."""
        self.outbox.append(message)

    def last_link(self) -> str:
        """Returns the URL from the most recent message.

        Raises:
            AssertionError: If no message has been sent, or it carries no link.
        """
        assert self.outbox, "no email was sent"
        for line in self.outbox[-1].body.splitlines():
            if line.startswith("http"):
                return line
        raise AssertionError(f"no link in email body: {self.outbox[-1].body!r}")

    def token_from_last_link(self) -> str:
        """Extracts the ``token`` query parameter from the most recent link.

        Parsed properly rather than split on ``token=``: the link also carries a
        ``lang`` parameter, and a naive split would hand the token back with
        ``&lang=da`` glued to the end.
        """
        query = urlparse(self.last_link()).query
        tokens = parse_qs(query).get("token", [])
        assert tokens, f"no token in link query {query!r}"
        return tokens[0]


@pytest.fixture(scope="session")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    """One loop for the whole session, so the pool outlives individual tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def _migrated_database() -> AsyncIterator[None]:
    """Creates and migrates the test database once per session."""
    url = get_settings().database_url
    admin_url, _, database = url.rpartition("/")
    async with await psycopg.AsyncConnection.connect(
        f"{admin_url}/postgres", autocommit=True
    ) as conn:
        await conn.execute(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)')
        await conn.execute(f'CREATE DATABASE "{database}"')
    await apply_migrations(url)
    yield


@pytest.fixture
async def database() -> AsyncIterator[Database]:
    """An open pool, with every table emptied first."""
    db = await Database(get_settings()).open()
    async with db.connection() as conn:
        await conn.execute(f"TRUNCATE {_TRUNCATED_TABLES} CASCADE")
    yield db
    await db.close()


@pytest.fixture
def mailer() -> CapturingMailer:
    """The outbox for the test."""
    return CapturingMailer()


class Client:
    """A thin Connect-over-JSON client for one test.

    Wraps :class:`httpx.AsyncClient` so a call reads as
    ``await client.call("TaskService/CreateTask", {...})`` and returns parsed JSON.
    Errors are returned rather than raised: most tests assert on the failure shape.
    """

    def __init__(self, http: httpx.AsyncClient) -> None:
        """Stores the transport and starts unauthenticated."""
        self._http = http
        self.token: str | None = None

    async def call(self, method: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Invokes ``<Service>/<Method>`` and returns the decoded response."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        response = await self._http.post(f"/todo.v1.{method}", json=body or {}, headers=headers)
        return response.json()

    async def anon(self, method: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Invokes a method without credentials, ignoring any stored token."""
        response = await self._http.post(
            f"/todo.v1.{method}", json=body or {}, headers={"Content-Type": "application/json"}
        )
        return response.json()

    async def get(self, path: str) -> httpx.Response:
        """Issues a plain GET, for the health endpoints."""
        return await self._http.get(path)

    async def register(
        self, email: str = "owner@example.com", name: str = "Rasmus Jensing"
    ) -> dict[str, Any]:
        """Registers a user, stores the session token, and returns the user."""
        result = await self.anon(
            "AuthService/Register",
            {
                "credentials": {"email": email, "password": PASSWORD},
                "displayName": name,
                "locale": "LOCALE_DA",
                "timeZone": "Europe/Copenhagen",
                "client": "SESSION_CLIENT_WEB",
            },
        )
        assert "token" in result, result
        self.token = result["token"]
        return result["user"]

    async def login(self, email: str) -> dict[str, Any]:
        """Signs in and stores the session token."""
        result = await self.anon(
            "AuthService/Login", {"credentials": {"email": email, "password": PASSWORD}}
        )
        assert "token" in result, result
        self.token = result["token"]
        return result

    async def make_verified(self, database: Database, email: str) -> None:
        """Marks an address verified directly, skipping the email round-trip.

        Several features are gated on verification; going through the mailer for each
        of them would test the mailer, not the feature.
        """
        async with database.connection() as conn:
            await conn.execute(
                "UPDATE users SET email_verified = true, status = 'active' WHERE email = %s",
                (email,),
            )

    async def make_admin(self, database: Database, email: str) -> None:
        """Promotes an account to platform admin directly."""
        async with database.connection() as conn:
            await conn.execute(
                "UPDATE users SET role = 'admin', email_verified = true, status = 'active' "
                "WHERE email = %s",
                (email,),
            )


@pytest.fixture
async def client(database: Database, mailer: CapturingMailer) -> AsyncIterator[Client]:
    """An unauthenticated :class:`Client` against a freshly-built app."""
    app = create_app(settings=get_settings(), database=database, mailer=mailer)
    transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield Client(http)


@pytest.fixture
async def user(client: Client, database: Database) -> Client:
    """A signed-in, email-verified member. The common starting point."""
    await client.register()
    await client.make_verified(database, "owner@example.com")
    # The principal is read per call, so the next request already sees `active`.
    return client


@pytest.fixture
async def second_client(database: Database, mailer: CapturingMailer) -> AsyncIterator[Client]:
    """A second signed-in user, for sharing and permission tests."""
    app = create_app(settings=get_settings(), database=database, mailer=mailer)
    transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        other = Client(http)
        await other.register(email="partner@example.com", name="Mette Holm")
        await other.make_verified(database, "partner@example.com")
        yield other


def reason_of(error: dict[str, Any]) -> str:
    """Returns the :class:`todo.v1.ErrorReason` name from a Connect error payload.

    The reason travels as a packed ``ErrorDetail``; ``connect-python`` also renders
    it into a readable ``debug`` object, which is what this reads.
    """
    details = error.get("details") or []
    assert details, f"error carries no details: {error}"
    return details[0]["debug"]["reason"]
