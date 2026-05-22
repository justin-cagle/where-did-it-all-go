#!/bin/sh
set -e
if [ "${RUN_MIGRATIONS:-true}" != "false" ]; then
    alembic upgrade head
fi
exec "$@"
