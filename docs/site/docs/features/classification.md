# Classification

## What categories and tags are

**Categories** are the primary way to organize transactions for budgeting and reporting. Every transaction (or split allocation) belongs to exactly one category.

**Tags** are a secondary, flexible labeling system. A transaction can have multiple tags, and tags don't have hierarchy. Use tags for cross-cutting concerns — "business expense," "tax-deductible," or "vacation" — that don't fit cleanly into your category tree.

## System categories

Four categories are built into every household and cannot be deleted or renamed:

| Category | Why it exists |
|----------|--------------|
| **Transfer** | Internal moves between your own accounts. These don't count as spending — they're just money moving. |
| **Uncategorized** | The fallback for transactions that nothing matched. |
| **Income** | All income: salary, freelance, dividends, reimbursements. |
| **Refund** | Credits that represent a reversal of prior spending. Paired with the original purchase. |

These categories exist because they are meaningful to financial reporting in ways that user-defined categories can't replicate.

## Building your category tree

Categories have two levels: parent and child. You can't go deeper.

*Example:*
```
Food
  ├── Groceries
  ├── Dining Out
  └── Coffee

Transportation
  ├── Gas
  ├── Parking
  └── Public Transit
```

The default tree is seeded when you create your household from an editable template. You can rename, delete, and reorganize anything that isn't a system category. Adding your own top-level categories and subcategories is straightforward.

**Budget roles** — each category can be tagged as Needs, Wants, or Savings. This is used by the 50/30/20 budget method to enforce aggregate spending ratios.

## Rules engine

The rules engine automatically categorizes transactions as they arrive. A rule says: "IF these conditions are true, THEN take these actions."

### How rules work

A rule has conditions and actions, evaluated in priority order against each new transaction.

**Conditions you can match on:**

| Field | Match types |
|-------|------------|
| Merchant name | Equals, contains, starts with, Advanced pattern match (regex) |
| Transaction description | Equals, contains, starts with, Advanced pattern match (regex) |
| Amount | Equals, between a range |
| Account | Specific account |
| Direction | Debit or credit |
| Transaction type | Payroll, refund, transfer, fee, interest, dividend, regular |

**Actions a rule can take:**

| Action | What it does |
|--------|-------------|
| Set category | Assigns the transaction to a category |
| Add tag | Attaches a tag to the transaction |
| Set merchant name | Normalizes the merchant display name |
| Set transaction type | Overrides the auto-detected type |

### Rule priority

Rules are evaluated in priority order. Lower number = higher priority. If two rules match the same transaction, the lower-numbered rule wins. Ties are broken by creation date (older rule wins).

You can drag rules to reorder them or edit their priority number directly.

### Auto-apply vs. suggest mode

Each rule can be set to:

- **Auto-apply** — fires immediately on ingest; the category is set without your review
- **Suggest** — fires but routes the suggestion to the HITL queue; you confirm before the category is set

Use suggest mode for rules you're not confident in yet.

### Testing a rule before saving

Before saving a new rule, use the **Test** button. It shows you which transactions in your history would match the rule — name, date, amount, and description — so you can verify it does what you expect before letting it run on incoming data.

### Once a transaction is manually categorized

If you manually set a transaction's category (overriding a rule or categorizing from scratch), the rules engine won't re-categorize that transaction. Manual categorization takes permanent precedence.

## Classification pipeline order

Classification runs in this exact order on every transaction:

1. **Type detection** — built-in classifier assigns payroll, refund, transfer, fee, interest, dividend, or regular.
2. **Income source match** — if the transaction matches a known income source, it's locked to an income category. Rules cannot override this.
3. **User rules** — evaluated in priority order.
4. **Fallback** — if nothing matched, the transaction goes to Uncategorized.

This order is deterministic. You can reason about why any transaction was classified the way it was.

## Income sources

An income source is a declared, known income stream — your salary, freelance client, etc. Declaring an income source tells WDIAG to always classify matching transactions as income, regardless of any other rules.

Fields: employer name, which household member it belongs to, expected amount range, expected cadence, which account receives the deposit.

For paychecks split across multiple accounts (80% to checking, 20% to savings), WDIAG can detect and remember the split-deposit pattern so both deposits count as one income event.

## Reclassifying transactions

To change a transaction's category manually: click the transaction, click the category field, and choose a new category. This sets `manually_categorized = true` — the rules engine won't touch it again.

To re-run rules on historical transactions, use the "Re-run rules" option in classification settings. This evaluates all rules against all transactions that were NOT manually categorized.
