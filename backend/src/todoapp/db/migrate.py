"""Forward-only SQL migration runner.

Migrations are plain ``.sql`` files in ``migrations/``, named ``NNNN_slug.sql`` and
applied in filename order inside one transaction each. Applied versions are
recorded in ``schema_migrations`` together with a checksum, so an edited migration
is caught instead of silently diverging from what is deployed.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
import sys
from pathlib import Path
from typing import NamedTuple

import psycopg

from todoapp.config import get_settings
from todoapp.logging_config import configure_logging

logger = logging.getLogger("todoapp.db.migrate")

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

_CREATE_TRACKING_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    text PRIMARY KEY,
    checksum   text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
)
"""


class Migration(NamedTuple):
    """One migration file on disk."""

    version: str
    path: Path
    sql: str

    @property
    def checksum(self) -> str:
        """SHA-256 of the file body, used to detect edits after the fact."""
        return hashlib.sha256(self.sql.encode("utf-8")).hexdigest()


def discover_migrations(directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    """Reads every migration from ``directory``, ordered by filename."""
    migrations = [
        Migration(version=path.stem, path=path, sql=path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.sql"))
    ]
    if not migrations:
        raise RuntimeError(f"no migrations found in {directory}")
    return migrations


async def apply_migrations(database_url: str, *, dry_run: bool = False) -> list[str]:
    """Applies every pending migration and returns the versions applied.

    Args:
        database_url: libpq connection string.
        dry_run: When true, report what would run without writing anything.

    Returns:
        The versions applied, in order.

    Raises:
        RuntimeError: If an already-applied migration's checksum has changed.
    """
    migrations = discover_migrations()
    applied: list[str] = []

    async with await psycopg.AsyncConnection.connect(database_url, autocommit=True) as conn:
        async with conn.cursor() as cur:
            await cur.execute(_CREATE_TRACKING_TABLE)
            await cur.execute("SELECT version, checksum FROM schema_migrations")
            recorded = {row[0]: row[1] for row in await cur.fetchall()}

        for migration in migrations:
            previous = recorded.get(migration.version)
            if previous is not None:
                if previous != migration.checksum:
                    raise RuntimeError(
                        f"migration {migration.version} changed after it was applied "
                        f"({migration.path}); write a new migration instead of editing it"
                    )
                logger.debug("skipping already-applied migration %s", migration.version)
                continue

            if dry_run:
                logger.info("would apply %s", migration.version)
                applied.append(migration.version)
                continue

            logger.info("applying %s", migration.version)
            async with conn.transaction(), conn.cursor() as cur:
                await cur.execute(migration.sql)  # type: ignore[arg-type]
                await cur.execute(
                    "INSERT INTO schema_migrations (version, checksum) VALUES (%s, %s)",
                    (migration.version, migration.checksum),
                )
            applied.append(migration.version)

    return applied


async def reset_database(database_url: str) -> None:
    """Drops and recreates the ``public`` schema. Never available in production."""
    if get_settings().is_production:
        raise RuntimeError("refusing to reset the database in production")
    async with await psycopg.AsyncConnection.connect(database_url, autocommit=True) as conn:
        await conn.execute("DROP SCHEMA public CASCADE")
        await conn.execute("CREATE SCHEMA public")
    logger.warning("dropped and recreated schema public")


def main() -> int:
    """CLI entry point: ``todoapp-migrate [--dry-run] [--reset]``."""
    parser = argparse.ArgumentParser(description="Apply pending SQL migrations.")
    parser.add_argument("--dry-run", action="store_true", help="report without applying")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="drop the public schema first (development and test only)",
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings)

    async def run() -> list[str]:
        if args.reset:
            await reset_database(settings.database_url)
        return await apply_migrations(settings.database_url, dry_run=args.dry_run)

    applied = asyncio.run(run())
    if applied:
        logger.info("%d migration(s) %s", len(applied), "pending" if args.dry_run else "applied")
    else:
        logger.info("database is up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
