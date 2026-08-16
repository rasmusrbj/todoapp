"""Bridge between proto enums and PostgreSQL enum types.

The mapping is *derived* rather than written out: a proto value ``TASK_STATUS_TODO``
on enum ``TaskStatus`` maps to the PostgreSQL label ``todo``, and the ``_UNSPECIFIED``
sentinel maps to nothing at all. Because the tables come from the generated
descriptors, a proto value can never silently disagree with the Python mapping —
either the label exists in the database enum or :meth:`EnumCodec.to_db` raises.

``tests/test_enum_parity.py`` closes the loop by asserting that each codec's label
set equals the corresponding ``pg_enum`` label set.
"""

from __future__ import annotations

import re
from typing import Final

from google.protobuf.descriptor import EnumDescriptor

from todo.v1 import enums_pb2
from todoapp.errors import Reason, invalid_argument

_CAMEL_BOUNDARY = re.compile(r"(?<!^)(?=[A-Z])")

UNSPECIFIED: Final = 0


def _screaming_snake(camel: str) -> str:
    """``TaskStatus`` -> ``TASK_STATUS``."""
    return _CAMEL_BOUNDARY.sub("_", camel).upper()


class EnumCodec:
    """Two-way mapping between one proto enum and one PostgreSQL enum type.

    Attributes:
        proto_name: The proto enum's simple name, e.g. ``TaskStatus``.
        pg_type: The PostgreSQL type name, e.g. ``task_status``.
    """

    def __init__(self, descriptor: EnumDescriptor, *, pg_type: str | None = None) -> None:
        """Builds the mapping tables from ``descriptor``.

        Args:
            descriptor: Generated descriptor of the proto enum.
            pg_type: PostgreSQL type name. Defaults to the snake_case proto name.

        Raises:
            ValueError: If the enum has no ``_UNSPECIFIED`` zero value, or a value
                does not carry the expected ``<ENUM_NAME>_`` prefix.
        """
        self.proto_name = descriptor.name
        screaming = _screaming_snake(descriptor.name)
        self.pg_type = pg_type or screaming.lower()

        prefix = f"{screaming}_"
        to_db: dict[int, str] = {}
        from_db: dict[str, int] = {}

        for value in descriptor.values:
            if value.number == UNSPECIFIED:
                if value.name != f"{prefix}UNSPECIFIED":
                    raise ValueError(
                        f"{descriptor.name}: zero value must be {prefix}UNSPECIFIED, "
                        f"got {value.name}"
                    )
                continue
            if not value.name.startswith(prefix):
                raise ValueError(f"{descriptor.name}: {value.name} lacks prefix {prefix}")
            label = value.name.removeprefix(prefix).lower()
            to_db[value.number] = label
            from_db[label] = value.number

        if not to_db:
            raise ValueError(f"{descriptor.name}: no values besides UNSPECIFIED")

        self._to_db = to_db
        self._from_db = from_db

    def __repr__(self) -> str:
        """Shows the proto and PostgreSQL names."""
        return f"EnumCodec({self.proto_name} <-> {self.pg_type})"

    @property
    def labels(self) -> frozenset[str]:
        """Every PostgreSQL label this enum can produce."""
        return frozenset(self._from_db)

    def to_db(self, value: int, *, field: str) -> str:
        """Converts a proto enum number to its PostgreSQL label.

        Args:
            value: Proto enum number.
            field: Request field name, used in the error and for form highlighting.

        Returns:
            The PostgreSQL enum label.

        Raises:
            ConnectError: ``INVALID_ARGUMENT`` when the value is unspecified or
                unknown. Callers wanting a default must apply it first, via
                :meth:`to_db_or`.
        """
        label = self._to_db.get(value)
        if label is not None:
            return label
        if value == UNSPECIFIED:
            raise invalid_argument(
                Reason.ERROR_REASON_FIELD_REQUIRED, f"{field} is required", field=field
            )
        raise invalid_argument(
            Reason.ERROR_REASON_INVALID_ENUM_VALUE,
            f"{field} has unknown {self.proto_name} value {value}",
            field=field,
            metadata={"enum": self.proto_name, "value": str(value)},
        )

    def to_db_or(self, value: int, default: int, *, field: str = "") -> str:
        """Like :meth:`to_db` but substitutes ``default`` for the zero value.

        This is how proto3's "an absent scalar looks like zero" problem is handled
        for enums on create requests: the client may omit the field and get the
        documented default rather than an error.
        """
        return self.to_db(default if value == UNSPECIFIED else value, field=field or self.pg_type)

    def from_db(self, label: str | None) -> int:
        """Converts a PostgreSQL label back to its proto enum number.

        ``None`` maps to the ``_UNSPECIFIED`` sentinel, which is what a nullable
        enum column should surface as over the wire.

        Raises:
            ValueError: If the label is not part of this enum. That means storage
                holds a value the contract does not know about — a deployment
                error, not a user error, so it is not a ``ConnectError``.
        """
        if label is None:
            return UNSPECIFIED
        try:
            return self._from_db[label]
        except KeyError:
            raise ValueError(f"database returned unknown {self.pg_type} label {label!r}") from None

    def many_to_db(self, values: object, *, field: str) -> list[str]:
        """Converts a repeated enum filter, dropping unspecified entries.

        An empty result means "no filter", which is what every listing RPC
        documents for an empty repeated field.
        """
        return [
            self.to_db(value, field=field)
            for value in tuple(values)  # type: ignore[call-overload]
            if value != UNSPECIFIED
        ]


USER_ROLE: Final = EnumCodec(enums_pb2.UserRole.DESCRIPTOR)
USER_STATUS: Final = EnumCodec(enums_pb2.UserStatus.DESCRIPTOR)
LOCALE: Final = EnumCodec(enums_pb2.Locale.DESCRIPTOR)
THEME_PREFERENCE: Final = EnumCodec(enums_pb2.ThemePreference.DESCRIPTOR)
SESSION_CLIENT: Final = EnumCodec(enums_pb2.SessionClient.DESCRIPTOR)
LIST_VISIBILITY: Final = EnumCodec(enums_pb2.ListVisibility.DESCRIPTOR)
LIST_COLOR: Final = EnumCodec(enums_pb2.ListColor.DESCRIPTOR)
MEMBER_ROLE: Final = EnumCodec(enums_pb2.MemberRole.DESCRIPTOR)
TASK_STATUS: Final = EnumCodec(enums_pb2.TaskStatus.DESCRIPTOR)
TASK_PRIORITY: Final = EnumCodec(enums_pb2.TaskPriority.DESCRIPTOR)
RECURRENCE_FREQUENCY: Final = EnumCodec(enums_pb2.RecurrenceFrequency.DESCRIPTOR)
ACTIVITY_ACTION: Final = EnumCodec(enums_pb2.ActivityAction.DESCRIPTOR)
ACTIVITY_TARGET_TYPE: Final = EnumCodec(enums_pb2.ActivityTargetType.DESCRIPTOR)

# Every codec backed by a PostgreSQL type, keyed by that type name. The sort-field
# and direction enums are query-only and intentionally absent.
PG_BACKED_CODECS: Final[dict[str, EnumCodec]] = {
    codec.pg_type: codec
    for codec in (
        USER_ROLE,
        USER_STATUS,
        LOCALE,
        THEME_PREFERENCE,
        SESSION_CLIENT,
        LIST_VISIBILITY,
        LIST_COLOR,
        MEMBER_ROLE,
        TASK_STATUS,
        TASK_PRIORITY,
        RECURRENCE_FREQUENCY,
        ACTIVITY_ACTION,
        ACTIVITY_TARGET_TYPE,
    )
}

# --- Semantic groupings used by business rules -------------------------------

# Statuses meaning "this task is finished", matching the tasks_completed_at CHECK
# constraint in 0001_init.sql. Keep the two in step.
TERMINAL_TASK_STATUSES: Final[frozenset[str]] = frozenset({"done", "cancelled"})

# Membership roles, grouped by capability. Each set is a superset of the one above.
WRITE_ROLES: Final[frozenset[str]] = frozenset({"owner", "editor"})
COMMENT_ROLES: Final[frozenset[str]] = WRITE_ROLES | {"commenter"}
READ_ROLES: Final[frozenset[str]] = COMMENT_ROLES | {"viewer"}

# Account statuses that may hold a session. A suspended or deactivated account
# keeps its rows but cannot authenticate.
SIGNIN_ALLOWED_STATUSES: Final[frozenset[str]] = frozenset({"pending_verification", "active"})
