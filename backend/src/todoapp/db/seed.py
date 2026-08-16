"""Development seed data.

Creates a small but *realistic* dataset — a shared list with two members, mixed
statuses and priorities, labels, subtasks, comments, an overdue task and a
recurring one — so every screen in the web app has something to render and every
filter has something to filter.

Idempotent: running it twice re-creates the demo accounts from scratch rather than
piling up duplicates. It refuses to run against a production environment.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import logging
import os
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Final, NamedTuple

from connectrpc.errors import ConnectError

from todoapp.auth import passwords
from todoapp.config import get_settings
from todoapp.db.pool import Database
from todoapp.domain import validation
from todoapp.logging_config import configure_logging
from todoapp.repositories import activity as activity_repo
from todoapp.repositories import lists as lists_repo
from todoapp.repositories import tasks as tasks_repo
from todoapp.repositories import users as users_repo

logger = logging.getLogger("todoapp.db.seed")


class DemoAccount(NamedTuple):
    """The account you will sign in as. Chosen when the seed runs, never hardcoded.

    Deliberately not a constant in this file: a real address next to a plaintext
    password is the one thing a public repository should not carry, and a *shared*
    default password is worse — anyone who deploys this and seeds it would inherit a
    known admin.
    """

    email: str
    password: str
    display_name: str


class SeedUser(NamedTuple):
    """One demo account. `key` is how the fixtures below refer to it."""

    key: str
    email: str
    display_name: str
    role: str
    locale: str
    bio: str


#: The two collaborators the fixtures need, so sharing, assignment and comment
#: threads have somebody other than you in them. `example.com` is reserved by RFC
#: 2606 precisely so sample data cannot reach a real inbox.
COLLABORATORS: Final = (
    SeedUser(
        "partner",
        "partner@example.com",
        "Mette Holm",
        "member",
        "da",
        "Holder styr på detaljerne.",
    ),
    SeedUser(
        "colleague",
        "colleague@example.com",
        "Alex Weber",
        "member",
        "en",
        "Working across time zones.",
    ),
)


def seed_users(account: DemoAccount) -> tuple[SeedUser, ...]:
    """Every account the seed writes: yours as admin, plus the two collaborators."""
    return (
        SeedUser("owner", account.email, account.display_name, "admin", "da", ""),
        *COLLABORATORS,
    )


def _now() -> datetime:
    return datetime.now(tz=UTC)


async def _reset_demo_users(database: Database, users: tuple[SeedUser, ...]) -> None:
    """Deletes the demo accounts, cascading to everything they own."""
    async with database.transaction() as conn:
        await conn.execute(
            "DELETE FROM users WHERE email = ANY(%s::citext[])",
            ([user.email for user in users],),
        )


async def _create_users(
    database: Database, users: tuple[SeedUser, ...], password: str
) -> dict[str, str]:
    """Creates the demo accounts and returns key -> id."""
    password_hash = passwords.hash_password(password)
    ids: dict[str, str] = {}
    async with database.transaction() as conn:
        for seed in users:
            row = await users_repo.create(
                conn,
                email=seed.email,
                password_hash=password_hash,
                display_name=seed.display_name,
                role=seed.role,
                status="active",
                locale=seed.locale,
                time_zone="Europe/Copenhagen" if seed.locale == "da" else "Europe/Berlin",
            )
            user_id = str(row["id"])
            await users_repo.mark_email_verified(conn, user_id)
            await users_repo.update(conn, user_id, {"bio": seed.bio})
            ids[seed.key] = user_id
    return ids


async def _seed_household(database: Database, ids: dict[str, str]) -> None:
    """A shared household list: mixed statuses, an overdue item, a recurring bill."""
    owner = ids["owner"]
    partner = ids["partner"]

    async with database.transaction() as conn:
        list_id = await lists_repo.create(
            conn,
            owner_id=owner,
            name="Hjemmet",
            description="Det vi deler om huset.",
            color="green",
            visibility="shared",
        )
        await lists_repo.add_member(
            conn, list_id=list_id, user_id=partner, role="editor", invited_by_id=owner
        )
        urgent = await lists_repo.create_label(conn, list_id=list_id, name="Haster", color="red")
        errands = await lists_repo.create_label(conn, list_id=list_id, name="Ærinder", color="blue")

        overdue_id = await tasks_repo.create(
            conn,
            list_id=list_id,
            created_by_id=owner,
            title="Ring til VVS'eren",
            description="Bruseren drypper stadig. Nummeret ligger på køleskabet.",
            status="blocked",
            priority="urgent",
            assignee_id=owner,
            due_at=_now() - timedelta(days=3),
            due_has_time=False,
            starts_at=None,
            estimate_minutes=15,
            recurrence_frequency="none",
            recurrence_interval=1,
            recurrence_until=None,
        )
        await tasks_repo.set_labels(conn, overdue_id, [urgent])
        await tasks_repo.create_comment(
            conn,
            task_id=overdue_id,
            author_id=partner,
            body="Jeg prøvede i går, de ringer tilbage i morgen.",
        )

        groceries_id = await tasks_repo.create(
            conn,
            list_id=list_id,
            created_by_id=partner,
            title="Storkøb til weekenden",
            description="",
            status="todo",
            priority="medium",
            assignee_id=partner,
            due_at=_now() + timedelta(days=2),
            due_has_time=True,
            starts_at=None,
            estimate_minutes=45,
            recurrence_frequency="weekly",
            recurrence_interval=1,
            recurrence_until=None,
        )
        await tasks_repo.set_labels(conn, groceries_id, [errands])
        await tasks_repo.create_subtasks(
            conn,
            task_id=groceries_id,
            titles=["Havremælk", "Kaffe", "Rugbrød", "Frugt til ugen"],
        )
        subtasks = await tasks_repo.subtasks_for_tasks(conn, [groceries_id])
        for done in subtasks[groceries_id][:2]:
            await tasks_repo.update_subtask(
                conn, str(done["id"]), title=None, completed=True, position=None
            )

        rent_id = await tasks_repo.create(
            conn,
            list_id=list_id,
            created_by_id=owner,
            title="Betal husleje",
            description="Overføres den sidste hverdag i måneden.",
            status="todo",
            priority="high",
            assignee_id=owner,
            due_at=_now().replace(day=28) + timedelta(days=2),
            due_has_time=False,
            starts_at=None,
            estimate_minutes=5,
            recurrence_frequency="monthly",
            recurrence_interval=1,
            recurrence_until=None,
        )

        finished_id = await tasks_repo.create(
            conn,
            list_id=list_id,
            created_by_id=partner,
            title="Skift filter i emhætten",
            description="",
            status="done",
            priority="low",
            assignee_id=partner,
            due_at=_now() - timedelta(days=10),
            due_has_time=False,
            starts_at=None,
            estimate_minutes=20,
            recurrence_frequency="none",
            recurrence_interval=1,
            recurrence_until=None,
        )

        for task_id, title in (
            (overdue_id, "Ring til VVS'eren"),
            (groceries_id, "Storkøb til weekenden"),
            (rent_id, "Betal husleje"),
            (finished_id, "Skift filter i emhætten"),
        ):
            await activity_repo.record(
                conn,
                actor_id=owner,
                action="created",
                target_type="task",
                target_id=task_id,
                target_label=title,
                list_id=list_id,
                task_id=task_id,
            )
        await activity_repo.record(
            conn,
            actor_id=partner,
            action="status_changed",
            target_type="task",
            target_id=finished_id,
            target_label="Skift filter i emhætten",
            list_id=list_id,
            task_id=finished_id,
            field="status",
            from_value="in_progress",
            to_value="done",
        )
        await activity_repo.record(
            conn,
            actor_id=owner,
            action="member_added",
            target_type="membership",
            target_id=partner,
            target_label="Mette Holm",
            list_id=list_id,
            field="role",
            to_value="editor",
        )


async def _seed_work(database: Database, ids: dict[str, str]) -> None:
    """A work list in English, to exercise the second locale and a third member."""
    owner = ids["colleague"]
    reviewer = ids["owner"]

    async with database.transaction() as conn:
        list_id = await lists_repo.create(
            conn,
            owner_id=owner,
            name="Product launch",
            description="Everything blocking the beta.",
            color="violet",
            visibility="shared",
        )
        await lists_repo.add_member(
            conn, list_id=list_id, user_id=reviewer, role="commenter", invited_by_id=owner
        )
        blocked_label = await lists_repo.create_label(
            conn, list_id=list_id, name="Blocked", color="amber"
        )

        specs: tuple[tuple[str, str, str, int, int], ...] = (
            ("Finish onboarding copy", "todo", "high", 2, 120),
            ("Review the pricing page", "in_progress", "medium", 5, 60),
            ("Wire up analytics", "todo", "low", 12, 240),
            ("Fix the mobile nav", "blocked", "urgent", -1, 90),
            ("Ship the changelog", "done", "medium", -6, 30),
        )
        for title, status, priority, due_in_days, estimate in specs:
            task_id = await tasks_repo.create(
                conn,
                list_id=list_id,
                created_by_id=owner,
                title=title,
                description="",
                status=status,
                priority=priority,
                assignee_id=owner if status != "done" else reviewer,
                due_at=_now() + timedelta(days=due_in_days),
                due_has_time=False,
                starts_at=None,
                estimate_minutes=estimate,
                recurrence_frequency="none",
                recurrence_interval=1,
                recurrence_until=None,
            )
            if status == "blocked":
                await tasks_repo.set_labels(conn, task_id, [blocked_label])
                await tasks_repo.create_comment(
                    conn,
                    task_id=task_id,
                    author_id=reviewer,
                    body="Waiting on the design tokens before I can finish this.",
                )
            await activity_repo.record(
                conn,
                actor_id=owner,
                action="created",
                target_type="task",
                target_id=task_id,
                target_label=title,
                list_id=list_id,
                task_id=task_id,
            )


async def _seed_personal(database: Database, ids: dict[str, str]) -> None:
    """A private list and a public one, so visibility filters have data."""
    owner = ids["owner"]
    async with database.transaction() as conn:
        private_id = await lists_repo.create(
            conn,
            owner_id=owner,
            name="Læselisten",
            description="Bøger og artikler jeg vender tilbage til.",
            color="zinc",
            visibility="private",
        )
        for title in ("Læs kapitel 4 færdig", "Find den artikel om SQL-indekser"):
            await tasks_repo.create(
                conn,
                list_id=private_id,
                created_by_id=owner,
                title=title,
                description="",
                status="todo",
                priority="none",
                assignee_id=None,
                due_at=None,
                due_has_time=False,
                starts_at=None,
                estimate_minutes=0,
                recurrence_frequency="none",
                recurrence_interval=1,
                recurrence_until=None,
            )

        public_id = await lists_repo.create(
            conn,
            owner_id=owner,
            name="Fredagsbar-plan",
            description="Alle med en konto kan læse den.",
            color="pink",
            visibility="public",
        )
        await tasks_repo.create(
            conn,
            list_id=public_id,
            created_by_id=owner,
            title="Book lokalet",
            description="",
            status="todo",
            priority="high",
            assignee_id=None,
            due_at=_now() + timedelta(days=6),
            due_has_time=True,
            starts_at=None,
            estimate_minutes=15,
            recurrence_frequency="none",
            recurrence_interval=1,
            recurrence_until=None,
        )


async def seed(account: DemoAccount, *, reset: bool = True) -> dict[str, Any]:
    """Writes the demo dataset and returns a short summary.

    Args:
        account: The admin account to create and sign in as.
        reset: Delete the demo accounts first. Off only when adding to a dataset
            that was seeded already.

    Raises:
        RuntimeError: If the environment is production.
    """
    settings = get_settings()
    if settings.is_production:
        raise RuntimeError("refusing to seed a production database")

    users = seed_users(account)
    database = await Database(settings).open()
    try:
        if reset:
            await _reset_demo_users(database, users)
        ids = await _create_users(database, users, account.password)
        await _seed_household(database, ids)
        await _seed_work(database, ids)
        await _seed_personal(database, ids)

        async with database.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT (SELECT count(*) FROM users) AS users, "
                "(SELECT count(*) FROM lists) AS lists, "
                "(SELECT count(*) FROM tasks) AS tasks, "
                "(SELECT count(*) FROM comments) AS comments"
            )
            counts = await cur.fetchone() or {}
    finally:
        await database.close()
    return dict(counts)


# --- Choosing the account -------------------------------------------------------


def _display_name_from(email: str) -> str:
    """A readable name from an address: `rasmus.jensing@x.dk` -> `Rasmus Jensing`."""
    local = email.split("@", 1)[0]
    words = [part for part in re.split(r"[._\-+]+", local) if part]
    return " ".join(word.capitalize() for word in words) or "Owner"


def _check(email: str, password: str) -> str | None:
    """Returns a human-readable complaint, or None when the pair is usable.

    Runs the *server's* own validators rather than a second opinion, so the seed
    cannot create an account the API would have rejected.
    """
    try:
        validation.email(email)
    except ConnectError:
        return f"{email!r} is not a valid email address."
    try:
        passwords.validate_strength(password)
    except ConnectError as error:
        return error.message or "That password is not acceptable."
    return None


def _prompt_account() -> DemoAccount:
    """Asks for the account to sign in as.

    The password is read without echo and confirmed — a typo here is invisible and
    surfaces later as "wrong email or password", which sends you looking in entirely
    the wrong place.
    """
    print("Which account should the demo data belong to?")
    print("It becomes the admin you sign in as. Nothing is written outside this database.")
    for _attempt in range(3):
        email = input("  Email:    ").strip()
        password = getpass.getpass("  Password: ")
        again = getpass.getpass("  Repeat:   ")
        if password != again:
            print("  The two passwords differ. Try again.\n")
            continue
        complaint = _check(email, password)
        if complaint:
            print(f"  {complaint}\n")
            continue
        return DemoAccount(email, password, _display_name_from(email))
    raise SystemExit("Gave up after three attempts.")


def resolve_account(args: argparse.Namespace) -> DemoAccount:
    """Flags, then environment, then an interactive prompt.

    The environment path is what lets CI and `make setup` run unattended. When
    nothing is supplied and there is no terminal to ask, this fails loudly rather
    than inventing a password — a silent default is how a known credential ends up
    on a real deployment.
    """
    email = args.email or os.environ.get("TODOAPP_DEMO_EMAIL", "")
    password = args.password or os.environ.get("TODOAPP_DEMO_PASSWORD", "")

    if email and password:
        complaint = _check(email, password)
        if complaint:
            raise SystemExit(complaint)
        return DemoAccount(email, password, args.name or _display_name_from(email))

    if not sys.stdin.isatty():
        raise SystemExit(
            "No account given and no terminal to ask. Pass --email and --password, "
            "or set TODOAPP_DEMO_EMAIL and TODOAPP_DEMO_PASSWORD."
        )
    account = _prompt_account()
    return account._replace(display_name=args.name or account.display_name)


def write_credentials(path: Path, account: DemoAccount) -> None:
    """Saves the pair where the dev tooling can find it, at mode 0600.

    `make cli-coverage` and the iOS end-to-end tests need these credentials, and the
    alternative is hardcoding them in seven files — which is exactly what this change
    removes. The file is gitignored.
    """
    path.write_text(
        "# Written by `make seed`. Local only, gitignored — do not commit.\n"
        f"TODOAPP_DEMO_EMAIL={account.email}\n"
        f"TODOAPP_DEMO_PASSWORD={account.password}\n"
    )
    path.chmod(0o600)


def main() -> int:
    """CLI entry point: ``todoapp-seed [--email … --password …] [--keep-existing]``."""
    parser = argparse.ArgumentParser(description="Write development seed data.")
    parser.add_argument("--email", help="the admin account to create (otherwise asks)")
    parser.add_argument("--password", help="its password (otherwise asks, without echo)")
    parser.add_argument("--name", help="display name (otherwise derived from the email)")
    parser.add_argument(
        "--credentials-file",
        type=Path,
        help="write the chosen email and password here, for the dev tooling to read",
    )
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="do not delete the demo accounts first",
    )
    args = parser.parse_args()

    account = resolve_account(args)
    configure_logging(get_settings())
    counts = asyncio.run(seed(account, reset=not args.keep_existing))
    if args.credentials_file:
        write_credentials(args.credentials_file, account)
    logger.info(
        "seeded %s users, %s lists, %s tasks, %s comments",
        counts.get("users"),
        counts.get("lists"),
        counts.get("tasks"),
        counts.get("comments"),
    )
    logger.info("sign in as %s (admin)", account.email)
    logger.info(
        "collaborators (same password): %s",
        ", ".join(u.email for u in COLLABORATORS),
    )
    if args.credentials_file:
        logger.info("credentials written to %s", args.credentials_file)
    # The password is deliberately not logged: it is the one thing here that might be
    # reused somewhere real, and logs get pasted into issues.
    return 0


if __name__ == "__main__":
    sys.exit(main())
