# File Import

## Supported formats

| Format | Extension | What it is |
|--------|-----------|-----------|
| OFX | `.ofx` | Open Financial Exchange — standard format most US banks support |
| QFX | `.qfx` | Quicken Financial Exchange — OFX variant from Quicken-affiliated banks |
| CSV | `.csv` | Comma-separated — available from nearly every bank and credit card |

## When to use file import

- Your bank isn't supported by SimpleFIN
- You need **today's transactions** (SimpleFIN data is from the previous business day; file exports include today)
- You're importing historical data from before you set up WDIAG
- You want to import a one-time statement

## OFX / QFX import walkthrough

1. Export an OFX or QFX file from your bank's website (usually under "Download transactions" or "Export").
2. In WDIAG, go to **Settings → Connected Accounts** and drag the file to the import zone (or click "Browse files").
3. WDIAG reads the file and shows a summary: format, institution name, and detected accounts.
4. Map each detected account to an existing WDIAG account or create a new one.
5. Click **Import**.
6. You're redirected to the import job detail page showing progress and results.

OFX/QFX files include bank-provided transaction IDs, which makes deduplication reliable — importing the same file twice is safe.

## CSV import walkthrough

CSV files vary by bank — different column names, date formats, and amount conventions. WDIAG walks you through mapping.

1. Export a CSV from your bank's website.
2. Drag the file to the import zone.
3. WDIAG shows the first 5 rows as a preview.
4. Map each column:

| Column | Required? | Notes |
|--------|-----------|-------|
| Date | Yes | The transaction date |
| Amount | Yes | The transaction amount |
| Description | Yes | Transaction description / memo |
| Merchant name | No | Separate from description if your bank includes it |
| Any other column | — | Set to "Ignore" |

5. Set the **date format** (auto-detect works for most banks; specify manually if not):
   - `MM/DD/YYYY` — US format
   - `DD/MM/YYYY` — European format
   - `YYYY-MM-DD` — ISO format

6. Set the **amount convention**:
   - "Positive = money in (credit)" — credit line items are positive
   - "Positive = money out (debit)" — most US checking accounts

7. Choose the **account** these transactions belong to (required — CSV files don't include account information).

8. Click **Import**.

### Saved column mappings

After a successful CSV import, WDIAG saves the column mapping for that institution. Next time you import from the same bank, the mapping is pre-applied automatically. Changes during import update the saved mapping.

## Reviewing import results

The import job detail page shows:

- **Imported** — transactions successfully added
- **Duplicates** — transactions that matched existing records (not imported again)
- **Errors** — rows that couldn't be parsed (row number, content, and error shown)

If duplicates need review, a "Review duplicates" sheet opens inline. If the import looks correct, click **View imported transactions** to see them in the transaction list.

## Handling duplicates after import

WDIAG's deduplication matches imported transactions against existing ones. If it's confident in a match (bank-provided ID or high fuzzy score), the duplicate is silently skipped. If it's uncertain, the potential duplicate appears in the HITL queue for you to review.

Importing the same OFX/QFX file twice is always safe — bank-provided IDs make deduplication exact. For CSV files, deduplication is fuzzy (amount + date + description similarity), so importing overlapping periods may produce some HITL queue items.
