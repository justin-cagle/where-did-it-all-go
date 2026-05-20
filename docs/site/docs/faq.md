# FAQ

## Is my financial data sent to Anthropic or anyone else?

By default, no. WDIAG is self-hosted — your data stays on your server.

If you configure an AI provider (Anthropic, OpenAI), some data may be sent depending on your configured privacy level. The default for all cloud providers is `generalizations_only` — abstract patterns with no amounts and no merchant names. See [Privacy Levels](ai/privacy.md) for exactly what each level sends.

If you use a local AI model (Ollama, llama.cpp), nothing leaves your server at any privacy level.

SimpleFIN Bridge receives your bank credentials (not WDIAG — you connect to SimpleFIN directly). WDIAG only receives transaction data via an access token.

## Can I use WDIAG without SimpleFIN?

Yes. SimpleFIN is optional. You can import transactions from any bank using OFX, QFX, or CSV files exported from your bank's website. See [File Import](data/file-import.md).

Many users combine both: SimpleFIN for automatic daily syncing, and file import when they need today's transactions.

## What happens to my data if I stop self-hosting?

Your data lives in your Postgres database. You can export it at any time using standard Postgres dump tools:

```bash
docker compose exec postgres pg_dump -U wdiag wdiag > my-export.sql
```

WDIAG does not have a proprietary export format — it's a standard relational database. You can also trigger a backup from the admin panel and download the dump file.

## Does WDIAG support multiple currencies?

Yes, from day one. You set a home currency for your household; all aggregation, budgets, and net worth roll up to that currency. Foreign currency accounts display in their native currency on individual views and convert to home currency on aggregation surfaces.

Exchange rates are fetched from the Frankfurter API (European Central Bank data, ~33 major currencies). Manual rate override is available per transaction.

## Can I import historical data?

Yes. File import (OFX, QFX, CSV) accepts any date range including past years. On first SimpleFIN connection, WDIAG automatically imports the last 90 days of history. For older history, export statements from your bank and import them as files.

## Is there a mobile app?

Not yet. WDIAG is a web app. It is a PWA (Progressive Web App) — you can install it to your phone's home screen from the browser and it behaves like a native app. A native React Native app is planned for a future major version.

## How is WDIAG different from YNAB / Monarch / Copilot?

The main difference is self-hosting. WDIAG runs on your server; your data never goes to a third-party SaaS. No subscription fees to WDIAG, no ads, no data selling.

Beyond that:

- **Household awareness** is built in from the ground up, not added on
- **Local AI** option — use a local model for insights, no cloud API required
- **Open source** — you can inspect the code, contribute, and self-modify
- **No lock-in** — standard Postgres database, standard export formats

The trade-off: you're responsible for running and maintaining the server.

## Can multiple people use one instance?

Yes. A household can have multiple members. Multiple households can exist on one WDIAG instance (e.g., you run it for your family and a friend). Each household's data is isolated from others.

The App Admin manages who can register and assigns users to households. See [Registration Control](admin/registration.md).

## What banks does SimpleFIN support?

SimpleFIN supports most major US banks and credit unions. See [bridge.simplefin.org](https://bridge.simplefin.org) for the current supported institution list — it's maintained by SimpleFIN directly.

If your bank isn't supported, use file import instead.

## How do I back up my data?

WDIAG runs automatic nightly backups stored locally in the Docker volume. You can also configure S3-compatible offsite backup and trigger manual backups from the admin panel.

See [Backup](admin/backup.md) and [Backup & Restore](deployment/backup-restore.md).

## Can I export my data?

Yes — standard Postgres dump (`pg_dump`) exports everything. You can also download backup files from the admin panel. All financial data (transactions, accounts, budgets, goals) is in a standard relational format, not a proprietary format.

## What if SimpleFIN goes down?

WDIAG continues working normally. No syncing happens while SimpleFIN is unavailable, but all existing data remains accessible. File import is always available as an alternative. When SimpleFIN comes back, syncing resumes automatically.

## Is WDIAG open source?

Yes. The code is on GitHub at [github.com/justin-cagle/where-did-it-all-go](https://github.com/justin-cagle/where-did-it-all-go). See the LICENSE file for terms.

## How do I report a bug?

Open an issue on GitHub: [github.com/justin-cagle/where-did-it-all-go/issues](https://github.com/justin-cagle/where-did-it-all-go/issues).

Include: your WDIAG version (shown in Admin → System), steps to reproduce, and what you expected vs. what happened. For data-related bugs, redact any sensitive information before sharing.

## What's the roadmap to v1.0?

The full feature set is implemented. The path to v1.0 is stabilization: API stability, test coverage targets, performance hardening, and user-facing polish. Breaking changes before 1.0 will be called out in the changelog with clear migration guidance.
