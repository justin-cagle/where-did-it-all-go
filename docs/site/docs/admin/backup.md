# Backup

## What gets backed up

WDIAG performs a **Postgres logical dump** — a complete export of your database in standard SQL format, compressed and (optionally) encrypted. This includes all households, transactions, budgets, goals, accounts, and configuration.

What is NOT in the backup: Redis cache and job queue data. Redis is ephemeral — it's used for caching and queuing, not source-of-truth data storage. Losing Redis data on restore is expected and safe.

## Local backup (always on)

Every night, WDIAG runs an automated backup and stores it locally inside the Docker volume. The backup file is a standard Postgres dump (`.sql.gz`).

Local backups are retained for 30 days by default (configurable in the admin panel). Older backups are automatically pruned.

## S3-compatible backup (optional)

In addition to local storage, WDIAG can upload each backup to an S3-compatible object storage bucket for offsite redundancy.

Supported providers:
- **AWS S3** — endpoint: `https://s3.amazonaws.com`
- **Backblaze B2** — your B2 endpoint URL
- **Wasabi** — your Wasabi endpoint URL
- **MinIO** — your MinIO endpoint URL
- Any S3-compatible API

Configure S3 backup in **Admin → Backup** under the "Cloud backup (optional)" section:

- S3 endpoint URL
- Bucket name
- Path prefix (default: `wdiag-backups`)
- Access key and secret key (stored encrypted)
- Enable S3 backup toggle

Use **Test connection** to verify your credentials by listing the bucket before enabling.

## Manual backup trigger

In **Admin → Backup**, click **Back up now** to trigger an immediate backup. The backup runs in the background; the run list refreshes when it completes.

## Backup run history

The last 20 backup runs are shown with:
- Status (running / success / failed)
- Triggered by (scheduled or admin name)
- Started at, duration, file size
- Error detail (if failed, expandable)

If the last backup is over 24 hours old or failed, a warning banner appears at the top of the backup page and in the admin overview.

## Retention settings

Local retention is configurable in the backup panel — set how many days to keep local backups. The default is 30 days.

S3 retention is managed by your S3 provider's lifecycle rules — WDIAG does not delete S3 backups automatically.

## Bring your own backup solution

If you prefer your own backup process (e.g., borgbackup, restic, or your VPS provider's snapshot feature), the nightly dump is a standard Postgres `.sql.gz` file stored at the path shown in the backup panel. Mount this path in your Docker configuration to access it from the host and include it in your backup tooling.
