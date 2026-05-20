# Quick Start

The fastest way to try WDIAG is the all-in-one (AIO) image. It bundles everything — Postgres, Redis, the app, background workers, and a reverse proxy — into a single container.

## Run it

```bash
docker run -p 80:80 -p 443:443 \
  ghcr.io/justin-cagle/wdiag-aio:latest
```

Then open **https://localhost** in your browser.

## Accept the certificate warning

Because this is running on `localhost`, the TLS certificate is self-signed by Caddy's local CA. Your browser will show a security warning. This is expected and safe to bypass for local use:

- **Chrome/Edge:** click "Advanced" then "Proceed to localhost (unsafe)"
- **Firefox:** click "Advanced..." then "Accept the Risk and Continue"
- **Safari:** click "Show Details" then "visit this website"

## Default credentials

```
Email:    admin@wdiag.local
Password: admin
```

These are printed in the container logs and shown on the login page. Change them immediately in **Settings → Profile**.

## What you'll see first

1. **Login page** — shows a demo mode banner with the default credentials.

2. **Admin panel** — your first login lands in `/admin`. From here you can see the system overview and manage users.

3. **Create a household** — navigate to the main app and create your household. Give it a name, choose a visibility mode (fully shared is simplest for a solo user or couple), and set your home currency.

4. **Add an account** — go to Accounts and add your first account. You can connect to your bank via SimpleFIN or add a manual account.

5. **Dashboard** — once you have an account and some transactions, the dashboard shows your net worth, recent activity, and budget status.

## Keep your data between restarts

By default, data is wiped when the container is removed. To keep it:

```bash
docker run -p 80:80 -p 443:443 \
  -v wdiag-data:/var/lib/postgresql/data \
  -e PERSIST_DATA=true \
  ghcr.io/justin-cagle/wdiag-aio:latest
```

## AIO limitations

The AIO image is for demo, evaluation, and single-person personal use. It is **not recommended for multi-user production deployments** because:

- All services share one container — no process isolation
- No horizontal scaling
- The auto-generated `MASTER_KEY` is less secure than an explicitly configured one

For production, use the full docker-compose stack: [Installation guide](installation.md).
