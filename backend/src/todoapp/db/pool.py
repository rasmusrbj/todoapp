"""Connection pool and transaction helpers.

Everything below deliberately stays close to SQL: queries live in the repository
modules as plain text, and rows come back as ``dict`` via psycopg's ``dict_row``
factory. There is no ORM and no query builder — the schema is the contract.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Self

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from todoapp.config import Settings, get_settings

logger = logging.getLogger("todoapp.db")


class Database:
    """Owns an async psycopg pool and hands out connections and transactions."""

    def __init__(self, settings: Settings) -> None:
        """Creates the wrapper. The pool itself opens in :meth:`open`."""
        self._settings = settings
        self._pool: AsyncConnectionPool | None = None

    async def open(self) -> Self:
        """Opens the pool and waits until it is usable."""
        if self._pool is not None:
            return self
        pool = AsyncConnectionPool(
            conninfo=self._settings.database_url,
            min_size=self._settings.db_pool_min_size,
            max_size=self._settings.db_pool_max_size,
            kwargs={"row_factory": dict_row, "autocommit": True},
            open=False,
        )
        await pool.open(wait=True, timeout=10)
        self._pool = pool
        logger.info("database pool open (max_size=%s)", self._settings.db_pool_max_size)
        return self

    async def close(self) -> None:
        """Drains and closes the pool."""
        if self._pool is None:
            return
        await self._pool.close()
        self._pool = None
        logger.info("database pool closed")

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[psycopg.AsyncConnection]:
        """Yields an autocommit connection for a single read or write.

        Use :meth:`transaction` whenever two statements must succeed together.
        """
        if self._pool is None:
            raise RuntimeError("database pool is not open")
        async with self._pool.connection() as conn:
            yield conn

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[psycopg.AsyncConnection]:
        """Yields a connection wrapped in an explicit transaction.

        The transaction commits on clean exit and rolls back on any exception,
        including the :class:`connectrpc.errors.ConnectError` raised by a failed
        authorization check — a rejected call must never leave partial writes.
        """
        async with self.connection() as conn, conn.transaction():
            yield conn


_database: Database | None = None


def get_database() -> Database:
    """Returns the process-wide :class:`Database`, creating it on first use."""
    global _database
    if _database is None:
        _database = Database(get_settings())
    return _database
