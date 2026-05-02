"""UUIDv7 primary key generation — time-ordered, app-side."""

import uuid

import uuid_utils


def new_uuid() -> uuid.UUID:
    """Generate a new UUIDv7 primary key.

    UUIDv7 is time-ordered (monotonically increasing within a millisecond) which
    keeps Postgres B-tree indexes compact and avoids page fragmentation from purely
    random UUIDs. Not enumerable — knowing one ID gives no information about others.
    """
    return uuid.UUID(str(uuid_utils.uuid7()))
