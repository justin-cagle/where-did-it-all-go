# Transactions

## Transaction lifecycle

Every transaction moves through states:

```
pending → posted → reconciled
```

**Pending** — the transaction has appeared in your bank feed but hasn't settled yet. Common for credit card purchases, which typically take 1–3 days to post.

**Posted** — the transaction has settled. This is the normal state for most transactions you'll work with.

**Reconciled** — you have explicitly confirmed this transaction matches your records. Reconciliation is a voluntary step — you do it when you want to verify your books, not automatically.

## Splits (allocations)

A **split** is how you assign a transaction to multiple budget categories. For example, a $120 Costco run might be $80 of Groceries and $40 of Household.

Splits are a tagging layer — the transaction itself stays as one row with one amount. Splits don't create child transactions. Budget and category reports add up your split allocations, not raw transactions.

Rules:
- All split amounts must sum to the full transaction amount.
- You can leave a portion as "Uncategorized" if you don't want to categorize part of it.
- A transaction with no splits is treated as a single allocation to its assigned category.

## Transfer pairing

When money moves between your own accounts (checking → savings), WDIAG detects the two transactions as a transfer and asks you to confirm the pair.

Once confirmed:
- Both transactions are assigned to the **Transfer** system category.
- They net out in spending reports — the outflow from one account cancels the inflow to the other. No double-counting.

You can also mark a transaction as an **external transfer** (wire to a third party with no matching internal account). These stay in the Transfer category but have no counterpart.

## Refund pairing

When a credit appears on your account that matches a previous purchase — same merchant, opposite sign, within a reasonable window — WDIAG surfaces it as a possible refund pair.

Once confirmed, the refund and original purchase net out cleanly in spending reports. Partial refunds (where the refund credit is smaller than the original charge) are handled correctly.

## Deduplication

If you import from both SimpleFIN and a statement file for the same period, you may have duplicate transactions. WDIAG uses a layered deduplication strategy:

1. **Exact ID match** — if the transaction has a bank-provided ID (SimpleFIN ID or OFX FITID), it's matched exactly.
2. **Fuzzy match** — same account, same amount, similar date, similar description. Scored with a confidence value.
3. **Below confidence threshold** → sent to the HITL queue for you to review manually. WDIAG never auto-merges when it's not sure.

When two sources cover the same period, SimpleFIN wins as the canonical source. Statement data is reference-only.

## Adding notes

You can add a note to any transaction — a personal reminder about what it was for, or context that doesn't fit in a category. Notes are private to your household.

## Manual transaction entry

If you track cash purchases or have an account that doesn't sync, you can enter transactions manually. Go to the account detail page and use "Add transaction."

## Filtering and searching

The transaction list can be filtered by:
- Account
- Date range
- Category
- Amount range
- Transaction state (pending / posted / reconciled)
- Tag
- User (in shared households, to see one person's attributed transactions)
- Import job (to see everything from a specific file import)

Transactions can be sorted by date, amount, or merchant name.
