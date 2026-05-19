#!/bin/bash
set -e

DOMAIN_NAME=${DOMAIN_NAME:-localhost}
PERSIST_DATA=${PERSIST_DATA:-false}
DATA_DIR=/var/lib/postgresql/data
KEY_FILE=/data/master.key

# ---------------------------------------------------------------------------
# MASTER_KEY handling
# ---------------------------------------------------------------------------
if [ -z "$MASTER_KEY" ]; then
    mkdir -p /data
    if [ -f "$KEY_FILE" ]; then
        export MASTER_KEY
        MASTER_KEY=$(cat "$KEY_FILE")
        echo "INFO: Loaded MASTER_KEY from $KEY_FILE"
    else
        export MASTER_KEY
        MASTER_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
        echo "$MASTER_KEY" > "$KEY_FILE"
        echo "WARNING: MASTER_KEY not set. A key has been generated and stored"
        echo "         at $KEY_FILE. Mount a volume to persist it, or set"
        echo "         MASTER_KEY explicitly for production use."
    fi
fi

# ---------------------------------------------------------------------------
# Postgres init (first start only)
# ---------------------------------------------------------------------------
if [ ! -f "$DATA_DIR/PG_VERSION" ]; then
    echo "INFO: Initializing Postgres..."
    su -c "initdb -D $DATA_DIR" postgres
    cp /etc/postgresql/pg_hba.conf "$DATA_DIR/pg_hba.conf"

    su -c "pg_ctl start -D $DATA_DIR -o '-k /tmp'" postgres
    sleep 2

    su -c "createdb wdiag" postgres
    su -c "createuser wdiag" postgres
    su -c "psql -c \"ALTER USER wdiag WITH PASSWORD 'wdiag';\"" postgres  # pragma: allowlist secret
    su -c "psql -c \"GRANT ALL PRIVILEGES ON DATABASE wdiag TO wdiag;\"" postgres

    su -c "pg_ctl stop -D $DATA_DIR" postgres

    FIRST_START=true
else
    FIRST_START=false
fi

# ---------------------------------------------------------------------------
# Start Postgres temporarily for migrations + bootstrap
# ---------------------------------------------------------------------------
su -c "pg_ctl start -D $DATA_DIR -o '-k /tmp'" postgres
sleep 2

echo "INFO: Running migrations..."
_DB_URL="postgresql+asyncpg://wdiag:wdiag@localhost/wdiag"  # pragma: allowlist secret
DATABASE_URL="$_DB_URL" uv run alembic upgrade head

# ---------------------------------------------------------------------------
# Bootstrap demo admin on first start
# ---------------------------------------------------------------------------
if [ "$FIRST_START" = "true" ]; then
    BOOTSTRAP_ADMIN_EMAIL=admin@wdiag.local \
    BOOTSTRAP_ADMIN_PASSWORD=admin \
    DATABASE_URL="$_DB_URL" \
        uv run python -c "
import asyncio
from app.households.bootstrap import run_bootstrap
from app.database import get_session_factory

async def _run():
    factory = get_session_factory()
    async with factory() as session:
        await run_bootstrap(session)

asyncio.run(_run())
"

    echo ""
    echo "╔══════════════════════════════════════════════╗"
    echo "║          WDIAG -- DEMO MODE                  ║"
    echo "║                                              ║"
    echo "║  URL:      https://$DOMAIN_NAME"
    echo "║  Email:    admin@wdiag.local                 ║"
    echo "║  Password: admin                             ║"
    echo "║                                              ║"
    echo "║  WARNING: Default credentials are insecure.  ║"
    echo "║  Change them before exposing this instance.  ║"
    echo "╚══════════════════════════════════════════════╝"
    echo ""
fi

# ---------------------------------------------------------------------------
# Stop temporary Postgres — supervisord will restart it
# ---------------------------------------------------------------------------
su -c "pg_ctl stop -D $DATA_DIR" postgres

# ---------------------------------------------------------------------------
# Export env for supervisord children
# ---------------------------------------------------------------------------
export DATABASE_URL="$_DB_URL"
export REDIS_URL="redis://localhost:6379/0"
export DOMAIN_NAME="$DOMAIN_NAME"
export MASTER_KEY="$MASTER_KEY"
export AIO_MODE="true"
export ALLOW_REGISTRATION="false"

exec /usr/bin/supervisord -c /etc/supervisor/conf.d/wdiag.conf
