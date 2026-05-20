# Upgrading

## Standard upgrade process

Upgrading WDIAG is straightforward. The process: pull new code, pull new images, restart.

```bash
# Pull the latest code
git pull

# Pull new Docker images
docker compose pull

# Restart services with new images — migrations run automatically
docker compose up -d
```

Migrations run automatically on every start via the `migrate` service, which exits once complete before `app` and the workers start. The migration step is a no-op if you're already on the latest revision.

## How migrations work

WDIAG uses Alembic for database schema migrations. Every schema change ships as a migration file. Migrations are:

- **Additive** — new columns and tables are added; existing data is preserved
- **Safe to run on live data** — migrations are designed to not block reads or writes for extended periods
- **Idempotent** — running `alembic upgrade head` when already at the latest revision does nothing

The System page in the admin panel (`/admin/system`) shows your current Alembic revision, the head revision, and whether you're up to date.

## Rollback procedure

If you need to roll back to a previous revision:

```bash
# Roll back one step
docker compose exec app uv run alembic downgrade -1

# Roll back to a specific revision
docker compose exec app uv run alembic downgrade <revision-id>

# Then switch to the older image
docker compose up -d
```

Check the changelog for the revision IDs associated with each version. Rollbacks are tested but use them cautiously — some migrations may not be reversible without data loss.

## Breaking changes

Breaking changes (API changes, migration changes requiring manual steps) are called out in the [changelog](../changelog.md) with clear upgrade instructions. Before upgrading across a major version, read the changelog for the versions you're skipping.

## Version pinning

To pin to a specific version instead of tracking `latest`, set `IMAGE_TAG` in your `.env`:

```bash
IMAGE_TAG=0.4.0
```

This applies to both published images — `wdiag-backend` and `wdiag-frontend` — which are always released together under the same tag.

Available tags:
- `latest` — the most recent stable release
- `0.4.0`, `0.3.1`, etc. — immutable version tags (see [Changelog](../changelog.md))

## Verifying after upgrade

After upgrading:

1. Check `docker compose ps` — all services should be running
2. Navigate to `/admin/system` — check migration state ("Up to date"), worker pool status
3. Run a quick smoke test: log in, view transactions, check that budgets load

If something looks wrong, check the logs:

```bash
docker compose logs app --tail=50
docker compose logs worker-slow --tail=20
```
