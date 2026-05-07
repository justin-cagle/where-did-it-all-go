"""Classification service — category/tag/rule/income-source CRUD and pipeline.

Classification pipeline (strict order, deterministic):
  1. Transaction-type detection — pattern-match description tokens
  2. IncomeSource match — if payroll and employer matches, lock to Income category
  3. Rules engine — evaluate enabled rules in priority order (ties: older wins)
  4. Fallback — assign Uncategorized

Cross-module DB access: reads/writes SplitAllocation and Transaction from the
transactions module (raw UUID foreign keys, no JOIN to classification tables).
No join between classification and transaction tables is ever issued.

All pure helper functions (detect_type, evaluate_condition, etc.) are importable
without a DB session for Hypothesis property testing.
"""

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, cast

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import ActorType, AuditEvent, AuditOperation
from app.classification.enums import RuleMode, StrictnessMode
from app.classification.models import (
    Category,
    HouseholdClassificationSettings,
    IncomeSource,
    Rule,
    Tag,
)
from app.transactions.models import SplitAllocation, Transaction

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class NotFoundError(Exception):
    """Entity does not exist or is not visible to this household."""


class ConflictError(Exception):
    """Operation would violate a uniqueness or state constraint."""


class ValidationError(Exception):
    """Operation violates a domain invariant."""


class PermissionError(Exception):
    """Actor lacks permission to perform this operation."""


# ---------------------------------------------------------------------------
# Default category template (code-defined, not stored in DB)
# Resulting rows are normal household-scoped editable categories.
# ---------------------------------------------------------------------------

_DEFAULT_CATEGORY_TREE: list[dict[str, Any]] = [
    {
        "name": "Housing",
        "children": [
            "Rent / Mortgage",
            "Utilities",
            "Home Insurance",
            "Home Maintenance",
            "HOA Fees",
        ],
    },
    {
        "name": "Food & Drink",
        "children": ["Groceries", "Dining Out", "Coffee & Snacks", "Alcohol"],
    },
    {
        "name": "Transportation",
        "children": [
            "Gas",
            "Public Transit",
            "Parking & Tolls",
            "Car Insurance",
            "Car Payment",
            "Car Maintenance",
            "Rideshare",
        ],
    },
    {
        "name": "Health & Medical",
        "children": [
            "Health Insurance",
            "Prescriptions",
            "Doctor / Dental",
            "Gym & Fitness",
        ],
    },
    {
        "name": "Entertainment",
        "children": ["Streaming Services", "Movies & Events", "Hobbies", "Games"],
    },
    {
        "name": "Shopping",
        "children": ["Clothing", "Electronics", "Home Goods", "Personal Care"],
    },
    {
        "name": "Education",
        "children": ["Tuition", "Books & Supplies", "Courses & Subscriptions"],
    },
    {
        "name": "Savings & Investments",
        "children": ["Emergency Fund", "Brokerage", "Retirement"],
    },
    {
        "name": "Gifts & Charity",
        "children": ["Gifts", "Donations"],
    },
    {
        "name": "Travel",
        "children": ["Flights", "Hotels", "Activities", "Travel Insurance"],
    },
    {"name": "Subscriptions", "children": []},
    {
        "name": "Fees & Charges",
        "children": ["Bank Fees", "Late Fees", "Service Fees"],
    },
    {
        "name": "Kids & Family",
        "children": ["Childcare", "School", "Kids Activities"],
    },
    {"name": "Pets", "children": ["Pet Food", "Vet", "Pet Grooming"]},
    {
        "name": "Business",
        "children": ["Office Supplies", "Software", "Professional Services"],
    },
]

# ---------------------------------------------------------------------------
# Pure helpers — safe for Hypothesis tests (no DB, no side effects)
# ---------------------------------------------------------------------------

_PAYROLL_TOKEN_RE = re.compile(
    r"\b(?:PAYROLL|SALARY|WAGES|EARNINGS|DIRDEP)\b|DIR\s+DEP|\bDD\b",
    re.IGNORECASE,
)


def detect_type(description: str, direction: str) -> str:
    """Classify transaction type from description + direction. Pure, no DB.

    Returns one of: payroll | regular.
    Only credit-direction transactions can be classified as payroll.
    """
    if direction == "credit" and _PAYROLL_TOKEN_RE.search(description):
        return "payroll"
    return "regular"


@dataclass
class TransactionContext:
    """Snapshot of transaction fields used by the classification pipeline."""

    transaction_id: uuid.UUID
    household_id: uuid.UUID
    account_id: uuid.UUID
    description: str
    merchant_name: str | None
    amount: Decimal
    currency: str
    direction: str
    transaction_type: str | None


def evaluate_condition(condition: dict[str, Any], tx: TransactionContext) -> bool:
    """Evaluate a single rule condition against a transaction. Pure, no DB.

    Operators:
      equals, contains, starts_with, pattern_match (regex) — string fields
      amount_equals, amount_between — amount field only
    All string comparisons are case-insensitive.
    Returns False for unknown fields or operators (safe degradation).
    """
    field_name = condition.get("field", "")
    operator = condition.get("operator", "")

    field_value: str
    match field_name:
        case "merchant_name":
            field_value = tx.merchant_name or ""
        case "description":
            field_value = tx.description
        case "amount":
            raw = condition.get("value")
            if operator == "amount_between":
                try:
                    lo = Decimal(str(condition.get("min", 0)))
                    hi = Decimal(str(condition.get("max", 0)))
                except InvalidOperation:
                    return False
                return lo <= tx.amount <= hi
            if operator == "amount_equals":
                try:
                    return tx.amount == Decimal(str(raw))
                except InvalidOperation:
                    return False
            return False
        case "account":
            field_value = str(tx.account_id)
        case "direction":
            field_value = tx.direction
        case "transaction_type":
            field_value = tx.transaction_type or ""
        case _:
            return False

    value = str(condition.get("value", ""))
    match operator:
        case "equals":
            return field_value.lower() == value.lower()
        case "contains":
            return value.lower() in field_value.lower()
        case "starts_with":
            return field_value.lower().startswith(value.lower())
        case "pattern_match":
            try:
                return bool(re.search(value, field_value, re.IGNORECASE))
            except re.error:
                return False
        case _:
            return False


def evaluate_all_conditions(conditions: list[dict[str, Any]], tx: TransactionContext) -> bool:
    """All conditions must match (AND logic). Pure, no DB."""
    return all(evaluate_condition(c, tx) for c in conditions)


def match_income_source(
    description: str,
    merchant_name: str | None,
    income_sources: list[IncomeSource],
) -> IncomeSource | None:
    """Token-based employer name match. Pure — caller loads income_sources from DB.

    Checks whether the employer_name is a substring of the transaction's
    merchant_name (preferred) or description (fallback). Case-insensitive.
    First match wins; callers should store income sources in priority order
    if disambiguation is needed.
    """
    haystack = (merchant_name or description).upper()
    for source in income_sources:
        if source.employer_name.upper() in haystack:
            return source
    return None


def extract_category_id(rule: Rule) -> uuid.UUID | None:
    """Extract the set_category action's category_id from a rule. Pure."""
    for action in rule.actions:
        if not isinstance(action, dict):
            continue
        typed: dict[str, object] = cast("dict[str, object]", action)
        if typed.get("type") == "set_category":
            raw = typed.get("category_id")
            if raw:
                try:
                    return uuid.UUID(str(raw))
                except ValueError:
                    pass
    return None


# ---------------------------------------------------------------------------
# Pipeline result types
# ---------------------------------------------------------------------------


@dataclass
class AllocationUpdate:
    allocation_id: uuid.UUID
    category_id: uuid.UUID | None
    rule_id: uuid.UUID | None
    rule_fired_at: datetime | None
    manually_categorized: bool


@dataclass
class SuggestionItem:
    allocation_id: uuid.UUID
    suggested_category_id: uuid.UUID
    rule_id: uuid.UUID


@dataclass
class HitlItem:
    allocation_id: uuid.UUID
    matching_rule_ids: list[uuid.UUID] = field(default_factory=list[uuid.UUID])


@dataclass
class ClassificationResult:
    allocation_updates: list[AllocationUpdate] = field(default_factory=list[AllocationUpdate])
    suggestions: list[SuggestionItem] = field(default_factory=list[SuggestionItem])
    hitl_items: list[HitlItem] = field(default_factory=list[HitlItem])
    detected_type: str | None = None


# ---------------------------------------------------------------------------
# Classification pipeline
# ---------------------------------------------------------------------------


async def classify_transaction(
    session: AsyncSession,
    *,
    transaction_id: uuid.UUID,
    household_id: uuid.UUID,
) -> ClassificationResult:
    """Run the 4-step classification pipeline on a single transaction.

    Skips SplitAllocation rows where manually_categorized=True.
    Writes category_id, rule_id, rule_fired_at back to SplitAllocation.
    Updates Transaction.transaction_type if not already set.
    Emits audit events for rule fires and income-source matches.
    """
    tx = await session.get(Transaction, transaction_id)
    if tx is None:
        raise NotFoundError(f"transaction {transaction_id} not found")

    # Load only non-manually-categorized allocations
    alloc_stmt = sa.select(SplitAllocation).where(
        SplitAllocation.transaction_id == transaction_id,
        SplitAllocation.manually_categorized.is_(False),
    )
    alloc_rows = await session.execute(alloc_stmt)
    allocations = list(alloc_rows.scalars().all())

    if not allocations:
        return ClassificationResult()

    # Load household strictness (defaults to strict if no settings row)
    settings = await _get_or_create_settings(session, household_id)
    strictness = StrictnessMode(settings.strictness)

    # -----------------------------------------------------------------------
    # Step 1: Transaction-type detection
    # -----------------------------------------------------------------------
    detected = detect_type(tx.description, tx.direction)
    if tx.transaction_type is None:
        tx.transaction_type = detected
    else:
        detected = tx.transaction_type
    await session.flush()

    # -----------------------------------------------------------------------
    # Step 2: IncomeSource match (only for payroll-type credits)
    # -----------------------------------------------------------------------
    income_category_id: uuid.UUID | None = None
    matched_income_source: IncomeSource | None = None

    if detected == "payroll":
        src_stmt = sa.select(IncomeSource).where(
            IncomeSource.household_id == household_id,
        )
        src_rows = await session.execute(src_stmt)
        income_sources = list(src_rows.scalars().all())
        matched_income_source = match_income_source(
            tx.description, tx.merchant_name, income_sources
        )
        if matched_income_source:
            income_cat = await _get_system_category(session, "Income")
            income_category_id = income_cat.id if income_cat else None

    # -----------------------------------------------------------------------
    # Step 3: Rules engine
    # Load once per transaction (not per allocation)
    # -----------------------------------------------------------------------
    rules_stmt = (
        sa.select(Rule)
        .where(
            Rule.household_id == household_id,
            Rule.enabled.is_(True),
        )
        .order_by(Rule.priority.asc(), Rule.created_at.asc())
    )
    rules_rows = await session.execute(rules_stmt)
    active_rules = list(rules_rows.scalars().all())

    tx_ctx = TransactionContext(
        transaction_id=tx.id,
        household_id=household_id,
        account_id=tx.account_id,
        description=tx.description,
        merchant_name=tx.merchant_name,
        amount=tx.amount,
        currency=tx.currency,
        direction=tx.direction,
        transaction_type=detected,
    )

    # Fallback system category
    uncategorized_cat = await _get_system_category(session, "Uncategorized")
    uncategorized_id = uncategorized_cat.id if uncategorized_cat else None

    # -----------------------------------------------------------------------
    # Process each allocation
    # -----------------------------------------------------------------------
    result = ClassificationResult(detected_type=detected)
    now = datetime.now(tz=UTC)

    for alloc in allocations:
        # Step 2 wins: IncomeSource match locks the category
        if matched_income_source and income_category_id:
            result.allocation_updates.append(
                AllocationUpdate(
                    allocation_id=alloc.id,
                    category_id=income_category_id,
                    rule_id=None,
                    rule_fired_at=now,
                    manually_categorized=False,
                )
            )
            await _write_audit(
                session,
                actor_type=ActorType.AUTOMATION,
                actor_id=None,
                actor_source="income_source_match",
                household_id=household_id,
                entity_type="split_allocation",
                entity_id=alloc.id,
                operation=AuditOperation.APPLY,
                delta=[
                    {
                        "op": "replace",
                        "path": "/category_id",
                        "value": str(income_category_id),
                    },
                    {
                        "op": "replace",
                        "path": "/income_source_id",
                        "value": str(matched_income_source.id),
                    },
                ],
            )
            continue

        # Step 3: evaluate rules
        matching = [r for r in active_rules if evaluate_all_conditions(r.conditions, tx_ctx)]

        if not matching:
            # Step 4: fallback
            result.allocation_updates.append(
                AllocationUpdate(
                    allocation_id=alloc.id,
                    category_id=uncategorized_id,
                    rule_id=None,
                    rule_fired_at=None,
                    manually_categorized=False,
                )
            )
            continue

        if len(matching) == 1 or strictness == StrictnessMode.SILENT:
            # Single match OR silent mode: first rule wins
            winner = matching[0]
            cat_id = extract_category_id(winner)
            if winner.mode == RuleMode.AUTO_APPLY:
                result.allocation_updates.append(
                    AllocationUpdate(
                        allocation_id=alloc.id,
                        category_id=cat_id,
                        rule_id=winner.id,
                        rule_fired_at=now,
                        manually_categorized=False,
                    )
                )
                await _write_audit(
                    session,
                    actor_type=ActorType.AUTOMATION,
                    actor_id=None,
                    actor_source="rule_engine",
                    household_id=household_id,
                    entity_type="split_allocation",
                    entity_id=alloc.id,
                    operation=AuditOperation.APPLY,
                    delta=[
                        {"op": "replace", "path": "/category_id", "value": str(cat_id)},
                        {"op": "replace", "path": "/rule_id", "value": str(winner.id)},
                    ],
                )
            else:
                # Suggest mode: emit suggestion, leave allocation uncategorized
                if cat_id:
                    result.suggestions.append(
                        SuggestionItem(
                            allocation_id=alloc.id,
                            suggested_category_id=cat_id,
                            rule_id=winner.id,
                        )
                    )
                result.allocation_updates.append(
                    AllocationUpdate(
                        allocation_id=alloc.id,
                        category_id=uncategorized_id,
                        rule_id=None,
                        rule_fired_at=None,
                        manually_categorized=False,
                    )
                )

        elif strictness == StrictnessMode.BEST_GUESS:
            # Multi-match + best_guess: first rule wins, flag for review
            winner = matching[0]
            cat_id = extract_category_id(winner)
            if winner.mode == RuleMode.AUTO_APPLY:
                result.allocation_updates.append(
                    AllocationUpdate(
                        allocation_id=alloc.id,
                        category_id=cat_id,
                        rule_id=winner.id,
                        rule_fired_at=now,
                        manually_categorized=False,
                    )
                )
                await _write_audit(
                    session,
                    actor_type=ActorType.AUTOMATION,
                    actor_id=None,
                    actor_source="rule_engine",
                    household_id=household_id,
                    entity_type="split_allocation",
                    entity_id=alloc.id,
                    operation=AuditOperation.APPLY,
                    delta=[
                        {"op": "replace", "path": "/category_id", "value": str(cat_id)},
                        {"op": "replace", "path": "/rule_id", "value": str(winner.id)},
                        {"op": "add", "path": "/multi_match_flag", "value": True},
                    ],
                )
            if cat_id:
                result.suggestions.append(
                    SuggestionItem(
                        allocation_id=alloc.id,
                        suggested_category_id=cat_id,
                        rule_id=winner.id,
                    )
                )

        else:
            # Multi-match + strict (default): send to HITL, leave uncategorized
            result.hitl_items.append(
                HitlItem(
                    allocation_id=alloc.id,
                    matching_rule_ids=[r.id for r in matching],
                )
            )
            result.allocation_updates.append(
                AllocationUpdate(
                    allocation_id=alloc.id,
                    category_id=uncategorized_id,
                    rule_id=None,
                    rule_fired_at=None,
                    manually_categorized=False,
                )
            )

    # Apply all allocation updates in bulk
    for upd in result.allocation_updates:
        await session.execute(
            sa.update(SplitAllocation)
            .where(SplitAllocation.id == upd.allocation_id)
            .values(
                category_id=upd.category_id,
                rule_id=upd.rule_id,
                rule_fired_at=upd.rule_fired_at,
                manually_categorized=upd.manually_categorized,
            )
        )
    await session.flush()
    return result


async def reclassify_transaction(
    session: AsyncSession,
    *,
    transaction_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> ClassificationResult:
    """Re-run pipeline on a single transaction.

    Skips allocations where manually_categorized=True (pipeline invariant).
    Emits an audit event for the reclassification action.
    """
    result = await classify_transaction(
        session, transaction_id=transaction_id, household_id=household_id
    )
    await _write_audit(
        session,
        actor_type=ActorType.USER,
        actor_id=actor_id,
        actor_source="reclassify_transaction",
        household_id=household_id,
        entity_type="transaction",
        entity_id=transaction_id,
        operation=AuditOperation.APPLY,
        delta=[{"op": "replace", "path": "/classification", "value": "reclassified"}],
    )
    return result


async def enqueue_reclassify_all(household_id: uuid.UUID, redis_url: str) -> str:
    """Enqueue a bulk reclassification job via ARQ. Returns the job ID."""
    import arq
    from arq.connections import RedisSettings

    pool = await arq.create_pool(RedisSettings.from_dsn(redis_url))
    job = await pool.enqueue_job("reclassify_all_job", household_id=str(household_id))
    await pool.aclose()
    return job.job_id if job else ""


async def reclassify_all_job(ctx: dict[str, Any], *, household_id: str) -> dict[str, Any]:
    """ARQ job: bulk reclassify all non-manually-categorized allocations.

    Idempotent — safe to re-run. Processes one transaction at a time to
    avoid holding a single large DB transaction.
    """
    _ = ctx  # ARQ provides ctx; this job does not need it
    from app.database import get_session_factory

    hh_id = uuid.UUID(household_id)
    factory = get_session_factory()
    processed = 0

    # Load all transaction IDs outside the per-tx session
    async with factory() as session:
        tx_stmt = sa.select(Transaction.id).where(
            Transaction.household_id == hh_id,
            Transaction.archived_at.is_(None),
        )
        tx_result = await session.execute(tx_stmt)
        tx_ids = list(tx_result.scalars().all())

    for tx_id in tx_ids:
        async with factory() as session:
            try:
                await classify_transaction(session, transaction_id=tx_id, household_id=hh_id)
                await session.commit()
                processed += 1
            except Exception:
                await session.rollback()

    return {"processed": processed, "total": len(tx_ids)}


# ---------------------------------------------------------------------------
# Category CRUD
# ---------------------------------------------------------------------------


async def create_category(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    name: str,
    parent_id: uuid.UUID | None = None,
    color: str | None = None,
    sort_order: int = 0,
) -> Category:
    """Create a household-scoped category. Enforces 2-level max depth."""
    if parent_id is not None:
        parent = await session.get(Category, parent_id)
        if parent is None or parent.household_id != household_id:
            raise NotFoundError("parent category not found in this household")
        if parent.system:
            raise ValidationError("cannot create children of system categories")
        if parent.parent_id is not None:
            raise ValidationError("categories may only be nested 2 levels deep")

    cat = Category(
        household_id=household_id,
        name=name,
        parent_id=parent_id,
        color=color,
        sort_order=sort_order,
    )
    session.add(cat)
    await session.flush()
    await _write_audit(
        session,
        actor_type=ActorType.USER,
        actor_id=actor_id,
        actor_source="user_action",
        household_id=household_id,
        entity_type="category",
        entity_id=cat.id,
        operation=AuditOperation.CREATE,
        delta=[{"op": "add", "path": "/name", "value": name}],
    )
    return cat


async def list_categories(session: AsyncSession, *, household_id: uuid.UUID) -> list[Category]:
    """Return all active categories visible to a household.

    Includes global system categories (household_id IS NULL) and
    household-scoped categories.
    """
    stmt = sa.select(Category).where(
        sa.or_(
            Category.household_id == household_id,
            Category.household_id.is_(None),
        )
    )
    rows = await session.execute(stmt)
    return list(rows.scalars().all())


async def get_category(
    session: AsyncSession, *, category_id: uuid.UUID, household_id: uuid.UUID
) -> Category:
    """Return a category visible to the household."""
    cat = await session.get(Category, category_id)
    if cat is None or cat.archived_at is not None:
        raise NotFoundError("category not found")
    if cat.household_id is not None and cat.household_id != household_id:
        raise NotFoundError("category not found")
    return cat


async def update_category(
    session: AsyncSession,
    *,
    category_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    name: str | None = None,
    parent_id: uuid.UUID | None = None,
    color: str | None = None,
    sort_order: int | None = None,
) -> Category:
    """Update a household-scoped category. System categories block rename."""
    cat = await get_category(session, category_id=category_id, household_id=household_id)
    if cat.system:
        raise PermissionError("system categories cannot be modified")
    if cat.household_id is None:
        raise PermissionError("system categories cannot be modified")

    delta: list[dict[str, Any]] = []

    if name is not None:
        if not cat.renameable:
            raise PermissionError("this category cannot be renamed")
        delta.append({"op": "replace", "path": "/name", "value": name})
        cat.name = name

    if parent_id is not None:
        new_parent = await session.get(Category, parent_id)
        if new_parent is None or new_parent.household_id != household_id:
            raise NotFoundError("parent category not found in this household")
        if new_parent.system:
            raise ValidationError("cannot nest under a system category")
        if new_parent.parent_id is not None:
            raise ValidationError("categories may only be nested 2 levels deep")
        delta.append({"op": "replace", "path": "/parent_id", "value": str(parent_id)})
        cat.parent_id = parent_id

    if color is not None:
        delta.append({"op": "replace", "path": "/color", "value": color})
        cat.color = color

    if sort_order is not None:
        delta.append({"op": "replace", "path": "/sort_order", "value": sort_order})
        cat.sort_order = sort_order

    await session.flush()
    if delta:
        await _write_audit(
            session,
            actor_type=ActorType.USER,
            actor_id=actor_id,
            actor_source="user_action",
            household_id=household_id,
            entity_type="category",
            entity_id=cat.id,
            operation=AuditOperation.UPDATE,
            delta=delta,
        )
    return cat


async def archive_category(
    session: AsyncSession,
    *,
    category_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    """Soft-delete a category. Reassigns referencing allocations to Uncategorized.

    System categories and non-deletable categories are blocked.
    """
    cat = await get_category(session, category_id=category_id, household_id=household_id)
    if not cat.deletable or cat.system:
        raise PermissionError("this category cannot be deleted")
    if cat.household_id is None:
        raise PermissionError("system categories cannot be deleted")

    uncategorized = await _get_system_category(session, "Uncategorized")
    if uncategorized:
        await session.execute(
            sa.update(SplitAllocation)
            .where(SplitAllocation.category_id == category_id)
            .values(category_id=uncategorized.id, rule_id=None, rule_fired_at=None)
        )

    now = datetime.now(tz=UTC)
    cat.archived_at = now
    cat.archived_by = actor_id
    await session.flush()
    await _write_audit(
        session,
        actor_type=ActorType.USER,
        actor_id=actor_id,
        actor_source="user_action",
        household_id=household_id,
        entity_type="category",
        entity_id=cat.id,
        operation=AuditOperation.ARCHIVE,
        delta=[{"op": "replace", "path": "/archived_at", "value": now.isoformat()}],
    )


# ---------------------------------------------------------------------------
# Tag CRUD
# ---------------------------------------------------------------------------


async def create_tag(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    name: str,
    color: str | None = None,
) -> Tag:
    tag = Tag(household_id=household_id, name=name, color=color)
    session.add(tag)
    await session.flush()
    await _write_audit(
        session,
        actor_type=ActorType.USER,
        actor_id=actor_id,
        actor_source="user_action",
        household_id=household_id,
        entity_type="tag",
        entity_id=tag.id,
        operation=AuditOperation.CREATE,
        delta=[{"op": "add", "path": "/name", "value": name}],
    )
    return tag


async def list_tags(session: AsyncSession, *, household_id: uuid.UUID) -> list[Tag]:
    rows = await session.execute(
        sa.select(Tag).where(Tag.household_id == household_id).order_by(Tag.name)
    )
    return list(rows.scalars().all())


async def get_tag(session: AsyncSession, *, tag_id: uuid.UUID, household_id: uuid.UUID) -> Tag:
    tag = await session.get(Tag, tag_id)
    if tag is None or tag.archived_at is not None or tag.household_id != household_id:
        raise NotFoundError("tag not found")
    return tag


async def update_tag(
    session: AsyncSession,
    *,
    tag_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    name: str | None = None,
    color: str | None = None,
) -> Tag:
    tag = await get_tag(session, tag_id=tag_id, household_id=household_id)
    delta: list[dict[str, Any]] = []
    if name is not None:
        delta.append({"op": "replace", "path": "/name", "value": name})
        tag.name = name
    if color is not None:
        delta.append({"op": "replace", "path": "/color", "value": color})
        tag.color = color
    await session.flush()
    if delta:
        await _write_audit(
            session,
            actor_type=ActorType.USER,
            actor_id=actor_id,
            actor_source="user_action",
            household_id=household_id,
            entity_type="tag",
            entity_id=tag.id,
            operation=AuditOperation.UPDATE,
            delta=delta,
        )
    return tag


async def archive_tag(
    session: AsyncSession,
    *,
    tag_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    tag = await get_tag(session, tag_id=tag_id, household_id=household_id)
    now = datetime.now(tz=UTC)
    tag.archived_at = now
    tag.archived_by = actor_id
    await session.flush()
    await _write_audit(
        session,
        actor_type=ActorType.USER,
        actor_id=actor_id,
        actor_source="user_action",
        household_id=household_id,
        entity_type="tag",
        entity_id=tag.id,
        operation=AuditOperation.ARCHIVE,
        delta=[{"op": "replace", "path": "/archived_at", "value": now.isoformat()}],
    )


# ---------------------------------------------------------------------------
# Rule CRUD
# ---------------------------------------------------------------------------


async def create_rule(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    name: str,
    priority: int,
    conditions: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    mode: str = "auto_apply",
    enabled: bool = True,
) -> Rule:
    rule = Rule(
        household_id=household_id,
        name=name,
        priority=priority,
        conditions=conditions,
        actions=actions,
        mode=mode,
        enabled=enabled,
    )
    session.add(rule)
    await session.flush()
    await _write_audit(
        session,
        actor_type=ActorType.USER,
        actor_id=actor_id,
        actor_source="user_action",
        household_id=household_id,
        entity_type="rule",
        entity_id=rule.id,
        operation=AuditOperation.CREATE,
        delta=[{"op": "add", "path": "/name", "value": name}],
    )
    return rule


async def list_rules(session: AsyncSession, *, household_id: uuid.UUID) -> list[Rule]:
    rows = await session.execute(
        sa.select(Rule)
        .where(Rule.household_id == household_id)
        .order_by(Rule.priority.asc(), Rule.created_at.asc())
    )
    return list(rows.scalars().all())


async def get_rule(session: AsyncSession, *, rule_id: uuid.UUID, household_id: uuid.UUID) -> Rule:
    rule = await session.get(Rule, rule_id)
    if rule is None or rule.archived_at is not None or rule.household_id != household_id:
        raise NotFoundError("rule not found")
    return rule


async def update_rule(
    session: AsyncSession,
    *,
    rule_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    name: str | None = None,
    priority: int | None = None,
    conditions: list[dict[str, Any]] | None = None,
    actions: list[dict[str, Any]] | None = None,
    mode: str | None = None,
    enabled: bool | None = None,
) -> Rule:
    rule = await get_rule(session, rule_id=rule_id, household_id=household_id)
    delta: list[dict[str, Any]] = []
    if name is not None:
        delta.append({"op": "replace", "path": "/name", "value": name})
        rule.name = name
    if priority is not None:
        delta.append({"op": "replace", "path": "/priority", "value": priority})
        rule.priority = priority
    if conditions is not None:
        delta.append({"op": "replace", "path": "/conditions", "value": conditions})
        rule.conditions = conditions
    if actions is not None:
        delta.append({"op": "replace", "path": "/actions", "value": actions})
        rule.actions = actions
    if mode is not None:
        delta.append({"op": "replace", "path": "/mode", "value": mode})
        rule.mode = mode
    if enabled is not None:
        delta.append({"op": "replace", "path": "/enabled", "value": enabled})
        rule.enabled = enabled
    await session.flush()
    if delta:
        await _write_audit(
            session,
            actor_type=ActorType.USER,
            actor_id=actor_id,
            actor_source="user_action",
            household_id=household_id,
            entity_type="rule",
            entity_id=rule.id,
            operation=AuditOperation.UPDATE,
            delta=delta,
        )
    return rule


async def archive_rule(
    session: AsyncSession,
    *,
    rule_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    rule = await get_rule(session, rule_id=rule_id, household_id=household_id)
    now = datetime.now(tz=UTC)
    rule.archived_at = now
    rule.archived_by = actor_id
    await session.flush()
    await _write_audit(
        session,
        actor_type=ActorType.USER,
        actor_id=actor_id,
        actor_source="user_action",
        household_id=household_id,
        entity_type="rule",
        entity_id=rule.id,
        operation=AuditOperation.ARCHIVE,
        delta=[{"op": "replace", "path": "/archived_at", "value": now.isoformat()}],
    )


async def reorder_rules(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    items: list[dict[str, Any]],
) -> list[Rule]:
    """Bulk-update priorities for a list of rules.

    items: [{"rule_id": UUID, "priority": int}, ...]
    """
    updated: list[Rule] = []
    for item in items:
        rule_id = uuid.UUID(str(item["rule_id"]))
        new_priority = int(item["priority"])
        rule = await get_rule(session, rule_id=rule_id, household_id=household_id)
        rule.priority = new_priority
        updated.append(rule)
    await session.flush()
    await _write_audit(
        session,
        actor_type=ActorType.USER,
        actor_id=actor_id,
        actor_source="user_action",
        household_id=household_id,
        entity_type="rule",
        entity_id=household_id,
        operation=AuditOperation.UPDATE,
        delta=[{"op": "replace", "path": "/priorities", "value": items}],
    )
    return updated


async def test_rule(
    session: AsyncSession,
    *,
    rule_id: uuid.UUID,
    household_id: uuid.UUID,
    limit: int = 50,
) -> tuple[list[uuid.UUID], int]:
    """Dry-run a rule against recent transactions. Returns (matching_ids, sample_count).

    No writes. Loads the last `limit` transactions for the household, evaluates
    rule conditions, returns IDs of those that would match.
    """
    rule = await get_rule(session, rule_id=rule_id, household_id=household_id)

    tx_stmt = (
        sa.select(Transaction)
        .where(
            Transaction.household_id == household_id,
            Transaction.archived_at.is_(None),
        )
        .order_by(Transaction.posted_date.desc())
        .limit(limit)
    )
    tx_rows = await session.execute(tx_stmt)
    transactions = list(tx_rows.scalars().all())

    matching_ids: list[uuid.UUID] = []
    for tx in transactions:
        ctx = TransactionContext(
            transaction_id=tx.id,
            household_id=household_id,
            account_id=tx.account_id,
            description=tx.description,
            merchant_name=tx.merchant_name,
            amount=tx.amount,
            currency=tx.currency,
            direction=tx.direction,
            transaction_type=tx.transaction_type,
        )
        if evaluate_all_conditions(rule.conditions, ctx):
            matching_ids.append(tx.id)

    return matching_ids, len(transactions)


# ---------------------------------------------------------------------------
# IncomeSource CRUD
# ---------------------------------------------------------------------------


async def create_income_source(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    attributed_to_user_id: uuid.UUID,
    employer_name: str,
    sub_type: str,
    expected_amount_min: Decimal,
    expected_amount_max: Decimal,
    currency: str = "USD",
    expected_cadence: str | None = None,
    account_id: uuid.UUID | None = None,
    variability_model: str = "fixed",
    deposit_split_pattern: list[Any] | None = None,
) -> IncomeSource:
    src = IncomeSource(
        household_id=household_id,
        attributed_to_user_id=attributed_to_user_id,
        employer_name=employer_name,
        sub_type=sub_type,
        expected_amount_min=expected_amount_min,
        expected_amount_max=expected_amount_max,
        currency=currency.upper(),
        expected_cadence=expected_cadence,
        account_id=account_id,
        variability_model=variability_model,
        deposit_split_pattern=deposit_split_pattern or [],
    )
    session.add(src)
    await session.flush()
    await _write_audit(
        session,
        actor_type=ActorType.USER,
        actor_id=actor_id,
        actor_source="user_action",
        household_id=household_id,
        entity_type="income_source",
        entity_id=src.id,
        operation=AuditOperation.CREATE,
        delta=[{"op": "add", "path": "/employer_name", "value": employer_name}],
    )
    return src


async def list_income_sources(
    session: AsyncSession, *, household_id: uuid.UUID
) -> list[IncomeSource]:
    rows = await session.execute(
        sa.select(IncomeSource)
        .where(IncomeSource.household_id == household_id)
        .order_by(IncomeSource.employer_name)
    )
    return list(rows.scalars().all())


async def get_income_source(
    session: AsyncSession, *, source_id: uuid.UUID, household_id: uuid.UUID
) -> IncomeSource:
    src = await session.get(IncomeSource, source_id)
    if src is None or src.archived_at is not None or src.household_id != household_id:
        raise NotFoundError("income source not found")
    return src


async def update_income_source(
    session: AsyncSession,
    *,
    source_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    employer_name: str | None = None,
    sub_type: str | None = None,
    expected_amount_min: Decimal | None = None,
    expected_amount_max: Decimal | None = None,
    currency: str | None = None,
    expected_cadence: str | None = None,
    account_id: uuid.UUID | None = None,
    variability_model: str | None = None,
    deposit_split_pattern: list[Any] | None = None,
) -> IncomeSource:
    src = await get_income_source(session, source_id=source_id, household_id=household_id)
    delta: list[dict[str, Any]] = []

    for attr, val in [
        ("employer_name", employer_name),
        ("sub_type", sub_type),
        ("expected_amount_min", expected_amount_min),
        ("expected_amount_max", expected_amount_max),
        ("currency", currency),
        ("expected_cadence", expected_cadence),
        ("account_id", account_id),
        ("variability_model", variability_model),
        ("deposit_split_pattern", deposit_split_pattern),
    ]:
        if val is not None:
            delta.append({"op": "replace", "path": f"/{attr}", "value": str(val)})
            setattr(src, attr, val)

    await session.flush()
    if delta:
        await _write_audit(
            session,
            actor_type=ActorType.USER,
            actor_id=actor_id,
            actor_source="user_action",
            household_id=household_id,
            entity_type="income_source",
            entity_id=src.id,
            operation=AuditOperation.UPDATE,
            delta=delta,
        )
    return src


async def archive_income_source(
    session: AsyncSession,
    *,
    source_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    src = await get_income_source(session, source_id=source_id, household_id=household_id)
    now = datetime.now(tz=UTC)
    src.archived_at = now
    src.archived_by = actor_id
    await session.flush()
    await _write_audit(
        session,
        actor_type=ActorType.USER,
        actor_id=actor_id,
        actor_source="user_action",
        household_id=household_id,
        entity_type="income_source",
        entity_id=src.id,
        operation=AuditOperation.ARCHIVE,
        delta=[{"op": "replace", "path": "/archived_at", "value": now.isoformat()}],
    )


# ---------------------------------------------------------------------------
# Household settings
# ---------------------------------------------------------------------------


async def get_household_settings(
    session: AsyncSession, *, household_id: uuid.UUID
) -> HouseholdClassificationSettings:
    return await _get_or_create_settings(session, household_id)


async def update_household_settings(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
    strictness: str,
) -> HouseholdClassificationSettings:
    settings = await _get_or_create_settings(session, household_id)
    old = settings.strictness
    settings.strictness = strictness
    await session.flush()
    await _write_audit(
        session,
        actor_type=ActorType.USER,
        actor_id=actor_id,
        actor_source="user_action",
        household_id=household_id,
        entity_type="household_classification_settings",
        entity_id=settings.id,
        operation=AuditOperation.UPDATE,
        delta=[{"op": "replace", "path": "/strictness", "from": old, "value": strictness}],
    )
    return settings


# ---------------------------------------------------------------------------
# Default category seed
# ---------------------------------------------------------------------------


async def seed_default_categories(session: AsyncSession, household_id: uuid.UUID) -> None:
    """Copy the standard category template into household-scoped rows.

    Called via platform.events after household creation. Resulting rows are
    normal editable categories — not system categories. Also creates the
    default classification settings row (strictness=strict).
    """
    for i, entry in enumerate(_DEFAULT_CATEGORY_TREE):
        parent = Category(
            household_id=household_id,
            name=entry["name"],
            sort_order=i,
        )
        session.add(parent)
        await session.flush()

        for j, child_name in enumerate(entry.get("children", [])):
            child = Category(
                household_id=household_id,
                name=child_name,
                parent_id=parent.id,
                sort_order=j,
            )
            session.add(child)

    settings_row = HouseholdClassificationSettings(
        household_id=household_id,
        strictness="strict",
    )
    session.add(settings_row)
    await session.flush()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _get_system_category(session: AsyncSession, name: str) -> Category | None:
    result = await session.execute(
        sa.select(Category).where(
            Category.name == name,
            Category.system.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def _get_or_create_settings(
    session: AsyncSession, household_id: uuid.UUID
) -> HouseholdClassificationSettings:
    result = await session.execute(
        sa.select(HouseholdClassificationSettings).where(
            HouseholdClassificationSettings.household_id == household_id,
        )
    )
    settings = result.scalar_one_or_none()
    if settings is None:
        settings = HouseholdClassificationSettings(
            household_id=household_id,
            strictness="strict",
        )
        session.add(settings)
        await session.flush()
    return settings


async def _write_audit(
    session: AsyncSession,
    *,
    actor_type: ActorType,
    actor_id: uuid.UUID | None,
    actor_source: str,
    household_id: uuid.UUID | None,
    entity_type: str,
    entity_id: uuid.UUID,
    operation: AuditOperation,
    delta: list[dict[str, Any]],
    rationale: str | None = None,
) -> None:
    event = AuditEvent(
        actor_type=str(actor_type),
        actor_id=actor_id,
        actor_source=actor_source,
        household_id=household_id,
        entity_type=entity_type,
        entity_id=entity_id,
        operation=str(operation),
        delta=delta,
        rationale=rationale,
    )
    session.add(event)
    await session.flush()


# ---------------------------------------------------------------------------
# Budget interfaces
# ---------------------------------------------------------------------------


async def get_categories_budget_roles(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    category_ids: list[uuid.UUID],
) -> dict[uuid.UUID, str]:
    """Return budget_role for each requested category_id.

    Returns only categories visible to the household (own + system).
    Missing category_ids are absent from the result (not an error).
    """
    if not category_ids:
        return {}
    result = await session.execute(
        sa.select(Category.id, Category.budget_role).where(
            Category.id.in_(category_ids),
            sa.or_(
                Category.household_id == household_id,
                Category.household_id.is_(None),
            ),
        )
    )
    return {row[0]: row[1] for row in result.all()}


async def get_income_sources_projected_amount(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    period_start: date,
    period_end: date,
) -> Decimal:
    """Return projected income for a household in a period.

    v1: sum of midpoint (min+max)/2 for all active income sources.
    Cadence-based pro-rating is deferred to a future iteration.
    period_start/period_end are accepted for future cadence-aware implementation.
    """
    del period_start, period_end
    sources = await list_income_sources(session, household_id=household_id)
    return sum(
        ((src.expected_amount_min + src.expected_amount_max) / 2 for src in sources),
        Decimal("0"),
    )
