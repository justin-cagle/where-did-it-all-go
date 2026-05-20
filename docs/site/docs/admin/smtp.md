# SMTP Setup

## Why SMTP matters

Email delivery enables two things in WDIAG:

1. **Invitations** — when you invite someone to your household, they receive an email with the accept link.
2. **Admin notifications** — alerts about unassigned registrations, backup failures, and worker issues.

Without SMTP, invitations still work — you get a link to copy and share manually. But email-based notifications are unavailable.

## Supported providers

WDIAG uses standard SMTP, which works with any mail provider:

- **Mailgun** — port 587, STARTTLS
- **SendGrid** — port 587, STARTTLS
- **AWS SES** — port 587, STARTTLS
- **Postmark** — port 587, STARTTLS
- **Fastmail, Gmail (App Password), Proton Mail Bridge** — any standard SMTP server
- **Self-hosted (Postfix, Maddy, etc.)** — if you run your own mail server

## Configuration

SMTP can be configured two ways:

### Via environment variables (`.env`)

```bash
SMTP_HOST=smtp.mailgun.org
SMTP_PORT=587
SMTP_USERNAME=postmaster@your-domain.com
SMTP_PASSWORD=your-smtp-password
SMTP_FROM_ADDRESS=wdiag@your-domain.com
SMTP_USE_TLS=true
APP_BASE_URL=https://your-domain.com
```

### Via the admin panel

Go to **Admin → SMTP**. Fill in the configuration form and click Save. Admin panel config overrides env var config.

Configuration fields:
- **Host** (required) — your SMTP server hostname
- **Port** (default 587)
- **Username** — SMTP authentication username
- **Password** — SMTP authentication password (stored encrypted)
- **From address** (required) — the "From" address on outgoing mail
- **Use TLS** (default: on) — enables STARTTLS

## Testing the connection

After saving configuration, click **Send test email**. WDIAG sends a test email to the admin's email address and shows the result inline:

- Success: "Test email sent to [email]"
- Failure: "Failed: [error detail]"

The last test result and timestamp are shown in the SMTP panel so you can see at a glance whether your configuration is working.

## What happens without SMTP

Invitations work — they generate a copyable link that you can share by any means. The invite panel shows: "Email delivery isn't set up. Invitations will work — you'll share the link manually."

Admin notifications appear in the admin panel notification feed but are not sent by email.

## Deleting SMTP configuration

In the admin panel SMTP page, click **Delete config**. This removes the saved database configuration. If env vars are set, they become the active configuration again. If no env vars are set, email delivery is disabled.
