# Backup & Restore

## Backup location

Local backups are stored inside the Postgres Docker volume. The exact path is shown in the admin panel under **Admin → Backup**.

If you're using the default volume configuration, backups are accessible at:
```bash
docker compose exec postgres ls /var/lib/postgresql/backups/
```

Or mount the backup directory to the host in `docker-compose.yml`:
```yaml
volumes:
  - ./backups:/var/lib/postgresql/backups
```

## Backup format

Backups are standard Postgres logical dumps (`.sql.gz`), optionally encrypted with your `BACKUP_ENCRYPTION_KEY`. This is a plain SQL dump that any standard Postgres tooling can restore from.

## Restore procedure

!!! warning "Restore overwrites all existing data"
    Restoring from a backup replaces your current database. Test your restore process before you need it.

**Step 1 — Stop the app (keep Postgres running)**

```bash
docker compose stop app worker-fast worker-slow
```

**Step 2 — Drop and recreate the database**

```bash
docker compose exec postgres psql -U wdiag -c "DROP DATABASE wdiag;"
docker compose exec postgres psql -U wdiag -c "CREATE DATABASE wdiag;"
```

**Step 3 — Restore from backup**

If the backup is unencrypted:
```bash
docker compose exec postgres bash -c \
  "gunzip -c /path/to/backup.sql.gz | psql -U wdiag wdiag"
```

If the backup is encrypted (using the built-in restore tool):
```bash
docker compose exec app uv run python -m app.backup restore /path/to/backup.sql.gz
```

**Step 4 — Run migrations to verify state**

```bash
docker compose exec app uv run alembic upgrade head
```

This is a no-op if migrations are already at head. Running it confirms the schema matches the code.

**Step 5 — Restart everything**

```bash
docker compose up -d
```

**Step 6 — Verify**

Log in, check that data looks correct, check the admin System page for worker and migration status.

## Testing your restore

A restore procedure that has never been tested is not a procedure. Test restore at least:
- When you first set up WDIAG
- After any major upgrade
- Periodically (every few months)

Recommended test approach: restore to a separate instance (different port or different server), verify the data looks correct, then tear it down. Don't wait until you need it to find out it's broken.

## Point-in-time recovery

WDIAG uses logical backups (SQL dumps), not WAL-based continuous archiving. This means:

- You can restore to any point in time where a backup exists
- You cannot restore to an arbitrary moment between backups (e.g., "I want the database as of 2pm yesterday")

If you need point-in-time recovery, set up Postgres WAL archiving separately. This is outside the scope of WDIAG's built-in backup — use your infrastructure tooling.
