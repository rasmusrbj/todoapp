"""Proto enums must match the PostgreSQL enum types exactly.

This is the test that keeps the "enums everywhere" design honest. Adding a value to
a proto enum without a migration, or to a migration without the proto, fails here
rather than at runtime in a query nobody ran yet.
"""

from __future__ import annotations

import pytest

from todo.v1 import enums_pb2
from todoapp.db.pool import Database
from todoapp.domain import enums


async def _pg_labels(database: Database, type_name: str) -> list[str]:
    """Returns a PostgreSQL enum type's labels in declaration order."""
    async with database.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT e.enumlabel AS label
            FROM pg_enum e
            JOIN pg_type t ON t.oid = e.enumtypid
            WHERE t.typname = %s
            ORDER BY e.enumsortorder
            """,
            (type_name,),
        )
        return [row["label"] for row in await cur.fetchall()]


@pytest.mark.parametrize("pg_type", sorted(enums.PG_BACKED_CODECS))
async def test_label_sets_match(database: Database, pg_type: str) -> None:
    codec = enums.PG_BACKED_CODECS[pg_type]
    pg = await _pg_labels(database, pg_type)
    assert pg, f"PostgreSQL type {pg_type} does not exist"
    assert set(pg) == codec.labels, (
        f"{codec.proto_name} and {pg_type} disagree: "
        f"only in proto {sorted(codec.labels - set(pg))}, "
        f"only in PostgreSQL {sorted(set(pg) - codec.labels)}"
    )


@pytest.mark.parametrize("pg_type", ["task_priority", "member_role"])
async def test_declaration_order_matches(database: Database, pg_type: str) -> None:
    """Order matters for the enums that are sorted or compared on.

    ``ORDER BY priority DESC`` must put ``urgent`` first, and the role sets in
    :mod:`todoapp.domain.enums` read as a privilege ladder.
    """
    codec = enums.PG_BACKED_CODECS[pg_type]
    pg = await _pg_labels(database, pg_type)
    proto_order = [
        codec.to_db(value.number, field=pg_type)
        for value in _descriptor_for(codec.proto_name).values
        if value.number != enums.UNSPECIFIED
    ]
    assert pg == proto_order


def _descriptor_for(proto_name: str):
    return getattr(enums_pb2, proto_name).DESCRIPTOR


def test_round_trip_every_value() -> None:
    """Every non-sentinel value survives proto -> PostgreSQL -> proto."""
    for codec in enums.PG_BACKED_CODECS.values():
        for label in codec.labels:
            number = codec.from_db(label)
            assert number != enums.UNSPECIFIED
            assert codec.to_db(number, field="x") == label


def test_unspecified_is_rejected() -> None:
    """The zero sentinel is never storable — callers must apply a default first."""
    from connectrpc.errors import ConnectError

    with pytest.raises(ConnectError):
        enums.TASK_STATUS.to_db(enums.UNSPECIFIED, field="status")


def test_unspecified_maps_from_null() -> None:
    """A nullable enum column surfaces as the sentinel, not as an error."""
    assert enums.MEMBER_ROLE.from_db(None) == enums.UNSPECIFIED


def test_unknown_label_is_a_deployment_error() -> None:
    """A label the contract does not know about raises, rather than silently zeroing.

    Reaching this means storage holds a value newer than the running code — better
    to fail loudly than to serialise it as ``UNSPECIFIED`` and confuse a client.
    """
    with pytest.raises(ValueError, match="unknown task_status label"):
        enums.TASK_STATUS.from_db("teleported")


def test_terminal_statuses_match_the_check_constraint() -> None:
    """The Python grouping and the SQL ``CHECK`` must agree on "finished"."""
    assert {"done", "cancelled"} == enums.TERMINAL_TASK_STATUSES
    assert enums.TASK_STATUS.labels > enums.TERMINAL_TASK_STATUSES


def test_role_ladder_is_nested() -> None:
    assert enums.WRITE_ROLES < enums.COMMENT_ROLES < enums.READ_ROLES
    assert enums.MEMBER_ROLE.labels == enums.READ_ROLES
