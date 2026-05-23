"""Insights service layer.

Public interface:
    get_active_provider(session, household_id, master_key)
        -> tuple[InsightProvider, InsightProviderConfig] | tuple[None, None]
    check_budget(session, household_id, estimated_tokens) -> bool
    complete(session, household_id, ...) -> str | None
    get_or_create_budget(session, household_id) -> TokenBudget
    list_provider_configs(session, household_id) -> list[InsightProviderConfig]
    create_provider_config(session, household_id, ...) -> InsightProviderConfig
    update_provider_config(session, config_id, household_id, ...) -> InsightProviderConfig
    archive_provider_config(session, config_id, household_id, actor_id)
    get_provider_config(session, config_id, household_id) -> InsightProviderConfig
    update_budget(session, household_id, ...) -> TokenBudget
    list_audit_log(session, household_id, ...) -> list[InsightAuditLog]
    generate_anomaly_insights(session, household_id, master_key)
    generate_pattern_insights(session, household_id, master_key)
    generate_forecast_narrative(session, household_id, projection_run_id, master_key)
    generate_categorization_suggestion(session, household_id, transaction_id, master_key)
    answer_question(session, household_id, question, master_key) -> AnswerResult
"""

import hashlib
import json
import time
import uuid
from datetime import date
from decimal import Decimal
from typing import Any, TypedDict

import sqlalchemy as sa
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import ActorType, AuditOperation
from app.audit import service as audit_service
from app.insights.enums import (
    REMOTE_PROVIDERS,
    AiDataSharing,
    InsightCategory,
    OverageBehavior,
)
from app.insights.enums import (
    InsightProvider as InsightProviderEnum,
)
from app.insights.models import InsightAuditLog, InsightProviderConfig, TokenBudget
from app.insights.providers.base import CompletionResult, InsightProvider
from app.insights.providers.disabled import DisabledProvider, InsightProviderDisabled
from app.insights.providers.llamacpp import LlamaCppProvider
from app.insights.providers.ollama import OllamaProvider
from app.insights.redaction import RedactionError, redact
from app.recommendations.enums import RecommendationSource
from app.security.encryption import DecryptionError, decrypt_dict, encrypt_dict

logger = structlog.get_logger(__name__)

_SYSTEM_PROMPT = (
    "You are a personal finance assistant. "
    "Be concise, factual, and specific. Avoid generic advice. "
    "Base all observations on the provided data only."
)

_ANOMALY_TEMPLATE = """\
Compare current-period vs prior-period spending by category:

{data}

Identify categories where spending has changed by more than 2 standard deviations
from the typical variance. For each anomaly, describe: category, direction, magnitude.
Respond in plain English. Be brief."""

_PATTERN_TEMPLATE = """\
Analyze 90 days of spending data:

{data}

Surface non-obvious behavioral patterns the user may not have noticed.
Avoid stating the obvious (e.g. "you spend money on groceries").
Focus on: timing patterns, category interactions, recurring anomalies, trend shifts.
Respond in plain English. Be brief."""

_FORECAST_TEMPLATE = """\
Upcoming cash-flow risk events:

{data}

Summarize the most significant cash-flow risks in plain English.
Include: breach date, affected account, risk magnitude.
Order by urgency. Be concise."""

_CATEGORIZATION_TEMPLATE = """\
Uncategorized transaction:

{data}

Suggest the most likely category for this transaction.
Respond with exactly one category name and a one-sentence rationale.
Format: CATEGORY: <name> | REASON: <reason>"""

_QA_TEMPLATE = """\
Financial data summary:

{data}
{history_block}
User question: {question}

Answer the question based only on the provided data. Be concise and factual."""


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class NotFoundError(Exception):
    """Config or budget row not found for this household."""


class ConflictError(Exception):
    """Operation violates a state constraint."""


class ValidationError(Exception):
    """Input rejected by business rules."""


# ---------------------------------------------------------------------------
# Answer result
# ---------------------------------------------------------------------------


class AnswerResult(TypedDict):
    answer: str | None
    provider_used: str | None
    reason: str | None


# ---------------------------------------------------------------------------
# Provider construction
# ---------------------------------------------------------------------------


def _build_provider(config: InsightProviderConfig, master_key: str) -> InsightProvider:
    """Construct a provider instance from a config row."""
    try:
        provider_enum = InsightProviderEnum(config.provider)
    except ValueError:
        return DisabledProvider()

    if provider_enum == InsightProviderEnum.DISABLED:
        return DisabledProvider()

    model = config.model_name or ""

    if provider_enum == InsightProviderEnum.LOCAL_OLLAMA:
        if not config.base_url:
            return DisabledProvider()
        return OllamaProvider(base_url=config.base_url, model_name=model)

    if provider_enum == InsightProviderEnum.LOCAL_LLAMACPP:
        if not config.base_url:
            return DisabledProvider()
        return LlamaCppProvider(base_url=config.base_url, model_name=model)

    if provider_enum in (InsightProviderEnum.ANTHROPIC, InsightProviderEnum.OPENAI):
        if not config.credentials_encrypted:
            return DisabledProvider()
        try:
            creds = decrypt_dict(config.credentials_encrypted, master_key)
            api_key = str(creds.get("api_key", ""))
        except DecryptionError:
            logger.warning(
                "insights.provider.credential_decrypt_failed",
                config_id=str(config.id),
            )
            return DisabledProvider()

        if provider_enum == InsightProviderEnum.ANTHROPIC:
            from app.insights.providers.anthropic import AnthropicProvider

            return AnthropicProvider(api_key=api_key, model_name=model)
        else:
            from app.insights.providers.openai import OpenAIProvider

            return OpenAIProvider(api_key=api_key, model_name=model)

    return DisabledProvider()


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------


async def get_active_provider(
    session: AsyncSession,
    household_id: uuid.UUID,
    master_key: str,
) -> tuple[InsightProvider, InsightProviderConfig] | tuple[None, None]:
    """Walk provider_priority list; return first available enabled provider.

    Returns (provider, config) or (None, None) if all unavailable.
    """
    result = await session.execute(
        sa.select(InsightProviderConfig)
        .where(
            InsightProviderConfig.household_id == household_id,
            InsightProviderConfig.enabled.is_(True),
            InsightProviderConfig.archived_at.is_(None),
        )
        .order_by(InsightProviderConfig.priority)
    )
    configs = list(result.scalars().all())

    for config in configs:
        provider = _build_provider(config, master_key)
        if await provider.is_available():
            return provider, config

    return None, None


# ---------------------------------------------------------------------------
# Budget management
# ---------------------------------------------------------------------------


async def get_or_create_budget(
    session: AsyncSession,
    household_id: uuid.UUID,
    provider_config_id: uuid.UUID | None = None,
) -> TokenBudget:
    """Fetch the current-period budget for a provider, creating it if new month.

    Scoped to provider_config_id so each provider tracks its own usage independently.
    """
    today = date.today()
    period_start = today.replace(day=1)

    result = await session.execute(
        sa.select(TokenBudget).where(
            TokenBudget.household_id == household_id,
            TokenBudget.period_start == period_start,
            TokenBudget.provider_config_id == provider_config_id,
        )
    )
    budget = result.scalar_one_or_none()
    if budget is None:
        budget = TokenBudget(
            household_id=household_id,
            period_start=period_start,
            provider_config_id=provider_config_id,
        )
        session.add(budget)
        await session.flush()
    return budget


async def check_budget(
    session: AsyncSession,
    household_id: uuid.UUID,
    estimated_tokens: int,
    provider_config_id: uuid.UUID | None = None,
) -> bool:
    """Return True if the call should proceed, False if budget is exhausted (block mode).

    Applies overage_behavior: block returns False; warn_and_continue and silent return True.
    """
    budget = await get_or_create_budget(session, household_id, provider_config_id)

    overage = OverageBehavior(budget.overage_behavior)

    if budget.token_limit is not None:
        projected = budget.tokens_used + estimated_tokens
        if projected > budget.token_limit:
            if overage == OverageBehavior.BLOCK:
                logger.info(
                    "insights.budget.blocked",
                    household_id=str(household_id),
                    tokens_used=budget.tokens_used,
                    token_limit=budget.token_limit,
                    estimated=estimated_tokens,
                )
                return False
            if overage == OverageBehavior.WARN_AND_CONTINUE:
                logger.warning(
                    "insights.budget.token_overage",
                    household_id=str(household_id),
                    tokens_used=budget.tokens_used,
                    token_limit=budget.token_limit,
                    estimated=estimated_tokens,
                )

    if budget.cost_limit is not None and budget.cost_used >= budget.cost_limit:
        if overage == OverageBehavior.BLOCK:
            logger.info(
                "insights.budget.cost_blocked",
                household_id=str(household_id),
                cost_used=str(budget.cost_used),
                cost_limit=str(budget.cost_limit),
            )
            return False
        if overage == OverageBehavior.WARN_AND_CONTINUE:
            logger.warning(
                "insights.budget.cost_overage",
                household_id=str(household_id),
                cost_used=str(budget.cost_used),
                cost_limit=str(budget.cost_limit),
            )

    return True


async def _record_audit_and_update_budget(
    session: AsyncSession,
    household_id: uuid.UUID,
    config: InsightProviderConfig,
    model_name: str,
    prompt_template: str,
    prompt_fingerprint: str,
    result: CompletionResult | None,
    insight_category: InsightCategory,
    duration_ms: int,
    error_detail: str | None,
    provider_config_id: uuid.UUID | None = None,
) -> None:
    success = result is not None
    response_fingerprint: str | None = None
    tokens_used = 0
    cost = Decimal("0")

    if result is not None:
        response_fingerprint = hashlib.sha256(result.text.encode()).hexdigest()
        tokens_used = result.tokens_used
        cost = result.cost

    log_entry = InsightAuditLog(
        household_id=household_id,
        provider=config.provider,
        model_name=model_name,
        prompt_template=prompt_template,
        prompt_fingerprint=prompt_fingerprint,
        response_fingerprint=response_fingerprint,
        tokens_used=tokens_used,
        cost=cost,
        currency="USD",
        insight_category=str(insight_category),
        duration_ms=duration_ms,
        success=success,
        error_detail=error_detail,
    )
    session.add(log_entry)

    if success and tokens_used > 0:
        budget = await get_or_create_budget(session, household_id, provider_config_id)
        budget.tokens_used += tokens_used
        budget.cost_used += cost

    await session.flush()


# ---------------------------------------------------------------------------
# Core completion
# ---------------------------------------------------------------------------


async def complete(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    prompt_template: str,
    template_vars: dict[str, Any],
    insight_category: InsightCategory,
    estimated_tokens: int = 500,
    master_key: str,
    max_tokens: int = 1024,
) -> str | None:
    """Orchestrate an LLM call. Returns None on any failure — never raises.

    Pipeline:
        1. Check budget (return None if blocked)
        2. Select active provider (return None if none available)
        3. Redact template_vars per provider's ai_data_sharing level
        4. Render prompt
        5. Call provider
        6. Record InsightAuditLog (always — success or failure)
        7. Update TokenBudget
        8. Return response text or None
    """
    try:
        provider, config = await get_active_provider(session, household_id, master_key)
        if provider is None or config is None:
            return None

        if not await check_budget(
            session, household_id, estimated_tokens, provider_config_id=config.id
        ):
            return None

        sharing_level = config.ai_data_sharing
        try:
            redacted_vars = redact(
                template_vars,
                sharing_level,
                household_salt=str(household_id),
            )
        except RedactionError as exc:
            logger.error(
                "insights.complete.redaction_error",
                household_id=str(household_id),
                error=str(exc),
            )
            return None

        rendered_data = json.dumps(redacted_vars, default=str, indent=2)
        prompt = prompt_template.format(
            data=rendered_data,
            **{k: v for k, v in template_vars.items() if k not in ("data",) and isinstance(v, str)},
        )
        prompt_fingerprint = hashlib.sha256(prompt.encode()).hexdigest()

        model_name = provider.get_model_name()
        start = time.monotonic()
        result: CompletionResult | None = None
        error_detail: str | None = None

        try:
            result = await provider.complete(prompt, _SYSTEM_PROMPT, max_tokens)
        except InsightProviderDisabled:
            error_detail = "provider disabled"
        except Exception as exc:
            error_detail = str(exc)
            logger.warning(
                "insights.complete.provider_error",
                household_id=str(household_id),
                provider=config.provider,
                error=str(exc),
            )

        duration_ms = int((time.monotonic() - start) * 1000)

        await _record_audit_and_update_budget(
            session,
            household_id=household_id,
            config=config,
            model_name=model_name,
            prompt_template=prompt_template,
            prompt_fingerprint=prompt_fingerprint,
            result=result,
            insight_category=insight_category,
            duration_ms=duration_ms,
            error_detail=error_detail,
            provider_config_id=config.id,
        )

        return result.text if result is not None else None

    except Exception as exc:
        logger.error(
            "insights.complete.unexpected_error",
            household_id=str(household_id),
            error=str(exc),
        )
        return None


# ---------------------------------------------------------------------------
# Insight generators
# ---------------------------------------------------------------------------


async def generate_anomaly_insights(
    session: AsyncSession,
    household_id: uuid.UUID,
    master_key: str,
) -> None:
    """Compare last 30 days vs prior 30 days per category; surface >2sigma deviations.

    Emits Recommendation objects via recommendations.service for each anomaly found.
    Returns without effect if no provider available or budget exhausted.
    """
    from app.recommendations import service as rec_service

    rows = await session.execute(
        sa.text(
            """
            WITH periods AS (
                SELECT
                    c.name AS category,
                    CASE
                        WHEN t.posted_date >= CURRENT_DATE - INTERVAL '30 days' THEN 'current'
                        ELSE 'prior'
                    END AS period,
                    SUM(CASE WHEN t.direction = 'debit' THEN t.amount ELSE 0 END) AS total,
                    COUNT(*) AS cnt,
                    t.currency
                FROM transactions_transaction t
                JOIN classification_category c ON c.id = t.category_id
                WHERE t.household_id = :hh_id
                  AND t.posted_date >= CURRENT_DATE - INTERVAL '60 days'
                  AND t.archived_at IS NULL
                GROUP BY c.name, period, t.currency
            )
            SELECT
                p_cur.category,
                p_cur.currency,
                COALESCE(p_cur.total, 0) AS current_total,
                COALESCE(p_prior.total, 0) AS prior_total,
                COALESCE(p_cur.cnt, 0) AS current_count,
                COALESCE(p_prior.cnt, 0) AS prior_count
            FROM periods p_cur
            LEFT JOIN periods p_prior
                ON p_prior.category = p_cur.category
               AND p_prior.currency = p_cur.currency
               AND p_prior.period = 'prior'
            WHERE p_cur.period = 'current'
            ORDER BY category
            """
        ),
        {"hh_id": household_id},
    )
    category_rows = rows.fetchall()

    if not category_rows:
        return

    categories: list[dict[str, Any]] = []
    for row in category_rows:
        current = float(row.current_total)
        prior = float(row.prior_total)
        direction = "up" if current > prior else ("down" if current < prior else "stable")
        change_pct: float | None = round((current - prior) / prior * 100, 1) if prior > 0 else None
        categories.append(
            {
                "name": row.category,
                "total": str(row.current_total),
                "count": row.current_count,
                "currency": row.currency,
                "direction": direction,
                "change_pct": change_pct,
                "prior_total": str(row.prior_total),
            }
        )

    period_today = date.today()
    template_vars: dict[str, Any] = {
        "period": {"year": period_today.year, "month": period_today.month},
        "categories": categories,
        "transactions": [],
        "accounts": [],
        "income_sources": [],
        "patterns": {},
        "household_name": "",
    }

    response = await complete(
        session,
        household_id=household_id,
        prompt_template=_ANOMALY_TEMPLATE,
        template_vars=template_vars,
        insight_category=InsightCategory.ANOMALY,
        estimated_tokens=800,
        master_key=master_key,
    )

    if response:
        await rec_service.create(
            session,
            household_id=household_id,
            source=RecommendationSource.AI_INSIGHTS,
            target_subsystem="insights",
            proposed_value={"insight_text": response, "category": "anomaly"},
            rationale_text=response,
        )
        logger.info("insights.anomaly.generated", household_id=str(household_id))


async def generate_pattern_insights(
    session: AsyncSession,
    household_id: uuid.UUID,
    master_key: str,
) -> None:
    """Fetch 90-day transaction summary; ask LLM to surface non-obvious patterns.

    Emits Recommendation via recommendations.service.
    """
    from app.recommendations import service as rec_service

    rows = await session.execute(
        sa.text(
            """
            SELECT
                c.name AS category,
                t.currency,
                SUM(t.amount) AS total,
                COUNT(*) AS cnt,
                t.direction
            FROM transactions_transaction t
            JOIN classification_category c ON c.id = t.category_id
            WHERE t.household_id = :hh_id
              AND t.posted_date >= CURRENT_DATE - INTERVAL '90 days'
              AND t.archived_at IS NULL
            GROUP BY c.name, t.currency, t.direction
            ORDER BY total DESC
            """
        ),
        {"hh_id": household_id},
    )
    category_rows = rows.fetchall()

    if not category_rows:
        return

    categories: list[dict[str, Any]] = []
    for row in category_rows:
        categories.append(
            {
                "name": row.category,
                "total": str(row.total),
                "count": row.cnt,
                "currency": row.currency,
                "direction": row.direction,
                "change_pct": None,
            }
        )

    period_today = date.today()
    template_vars: dict[str, Any] = {
        "period": {"year": period_today.year, "month": period_today.month},
        "categories": categories,
        "transactions": [],
        "accounts": [],
        "income_sources": [],
        "patterns": {},
        "household_name": "",
    }

    response = await complete(
        session,
        household_id=household_id,
        prompt_template=_PATTERN_TEMPLATE,
        template_vars=template_vars,
        insight_category=InsightCategory.PATTERN,
        estimated_tokens=800,
        master_key=master_key,
    )

    if response:
        await rec_service.create(
            session,
            household_id=household_id,
            source=RecommendationSource.AI_INSIGHTS,
            target_subsystem="insights",
            proposed_value={"insight_text": response, "category": "pattern"},
            rationale_text=response,
        )
        logger.info("insights.pattern.generated", household_id=str(household_id))


async def generate_forecast_narrative(
    session: AsyncSession,
    household_id: uuid.UUID,
    projection_run_id: uuid.UUID,
    master_key: str,
) -> None:
    """Fetch ProjectionBreachEvents for a run; generate plain-language cash-flow risk summary.

    Emits Recommendation via recommendations.service.
    """
    from app.recommendations import service as rec_service

    rows = await session.execute(
        sa.text(
            """
            SELECT
                pb.breach_type,
                pb.breach_date,
                pb.amount,
                pb.currency,
                pb.description
            FROM projections_breach_event pb
            WHERE pb.run_id = :run_id
              AND pb.household_id = :hh_id
            ORDER BY pb.breach_date
            LIMIT 20
            """
        ),
        {"run_id": projection_run_id, "hh_id": household_id},
    )
    breach_rows = rows.fetchall()

    if not breach_rows:
        return

    breaches: list[dict[str, Any]] = [
        {
            "breach_type": row.breach_type,
            "breach_date": str(row.breach_date),
            "amount": str(row.amount),
            "currency": row.currency,
            "description": row.description or "",
        }
        for row in breach_rows
    ]

    period_today = date.today()
    template_vars: dict[str, Any] = {
        "period": {"year": period_today.year, "month": period_today.month},
        "breach_events": breaches,
        "categories": [],
        "transactions": [],
        "accounts": [],
        "income_sources": [],
        "patterns": {},
        "household_name": "",
    }

    response = await complete(
        session,
        household_id=household_id,
        prompt_template=_FORECAST_TEMPLATE,
        template_vars=template_vars,
        insight_category=InsightCategory.FORECAST,
        estimated_tokens=600,
        master_key=master_key,
    )

    if response:
        await rec_service.create(
            session,
            household_id=household_id,
            source=RecommendationSource.AI_INSIGHTS,
            target_subsystem="projections",
            target_entity_id=projection_run_id,
            proposed_value={
                "insight_text": response,
                "category": "forecast",
                "projection_run_id": str(projection_run_id),
            },
            rationale_text=response,
        )
        logger.info(
            "insights.forecast.generated",
            household_id=str(household_id),
            run_id=str(projection_run_id),
        )


async def generate_categorization_suggestion(
    session: AsyncSession,
    household_id: uuid.UUID,
    transaction_id: uuid.UUID,
    master_key: str,
) -> None:
    """Suggest a category for an uncategorized transaction.

    Emits Recommendation with target=transactions, source=ai_insights.
    """
    from app.recommendations import service as rec_service

    row = await session.execute(
        sa.text(
            """
            SELECT
                t.id,
                t.amount,
                t.currency,
                t.direction,
                t.description,
                t.merchant_name,
                t.posted_date
            FROM transactions_transaction t
            WHERE t.id = :txn_id
              AND t.household_id = :hh_id
              AND t.category_id IS NULL
              AND t.archived_at IS NULL
            """
        ),
        {"txn_id": transaction_id, "hh_id": household_id},
    )
    txn = row.fetchone()
    if txn is None:
        return

    template_vars: dict[str, Any] = {
        "period": {"year": date.today().year, "month": date.today().month},
        "categories": [],
        "transactions": [
            {
                "amount": str(txn.amount),
                "currency": txn.currency,
                "date": str(txn.posted_date),
                "direction": txn.direction,
                "merchant": txn.merchant_name or "",
                "description": txn.description or "",
                "category": "",
                "account_id": "",
            }
        ],
        "accounts": [],
        "income_sources": [],
        "patterns": {},
        "household_name": "",
    }

    response = await complete(
        session,
        household_id=household_id,
        prompt_template=_CATEGORIZATION_TEMPLATE,
        template_vars=template_vars,
        insight_category=InsightCategory.CATEGORIZATION,
        estimated_tokens=300,
        master_key=master_key,
    )

    if response:
        await rec_service.create(
            session,
            household_id=household_id,
            source=RecommendationSource.AI_INSIGHTS,
            target_subsystem="transactions",
            target_entity_id=transaction_id,
            proposed_value={"suggestion": response, "category": "categorization"},
            rationale_text=response,
        )
        logger.info(
            "insights.categorization.generated",
            household_id=str(household_id),
            transaction_id=str(transaction_id),
        )


async def answer_question(
    session: AsyncSession,
    household_id: uuid.UUID,
    question: str,
    master_key: str,
    history: list[dict[str, str]] | None = None,
) -> AnswerResult:
    """Synchronous Q&A: answer a natural language question about the household's finances.

    Returns AnswerResult with answer=None and a reason string if unavailable.
    Never routes through HITL — direct synchronous response.
    Never raises — all errors are caught and returned as reason strings.
    """
    try:
        provider, config = await get_active_provider(session, household_id, master_key)
        if provider is None or config is None:
            # Distinguish disabled vs unavailable
            any_config_result = await session.execute(
                sa.select(InsightProviderConfig).where(
                    InsightProviderConfig.household_id == household_id,
                    InsightProviderConfig.archived_at.is_(None),
                )
            )
            has_any = any_config_result.scalar_one_or_none() is not None
            if not has_any:
                return AnswerResult(answer=None, provider_used=None, reason="disabled")
            return AnswerResult(answer=None, provider_used=None, reason="no_provider")

        budget_ok = await check_budget(
            session, household_id, estimated_tokens=500, provider_config_id=config.id
        )
        if not budget_ok:
            return AnswerResult(answer=None, provider_used=None, reason="budget_exceeded")

        rows = await session.execute(
            sa.text(
                """
                SELECT
                    c.name AS category,
                    t.currency,
                    SUM(s.amount) AS total,
                    COUNT(DISTINCT t.id) AS cnt,
                    t.direction
                FROM transactions_transaction t
                JOIN transactions_split_allocation s
                    ON s.transaction_id = t.id AND s.archived_at IS NULL
                JOIN classification_category c ON c.id = s.category_id
                WHERE t.household_id = :hh_id
                  AND t.posted_date >= CURRENT_DATE - INTERVAL '90 days'
                  AND t.archived_at IS NULL
                  AND s.category_id IS NOT NULL
                GROUP BY c.name, t.currency, t.direction
                ORDER BY total DESC
                LIMIT 50
                """
            ),
            {"hh_id": household_id},
        )
        cat_rows = rows.fetchall()

        period_today = date.today()
        template_vars: dict[str, Any] = {
            "period": {"year": period_today.year, "month": period_today.month},
            "categories": [
                {
                    "name": row.category,
                    "total": str(row.total),
                    "count": row.cnt,
                    "currency": row.currency,
                    "direction": row.direction,
                    "change_pct": None,
                }
                for row in cat_rows
            ],
            "transactions": [],
            "accounts": [],
            "income_sources": [],
            "patterns": {},
            "household_name": "",
        }

        qa_template = _QA_TEMPLATE
        sharing_level = config.ai_data_sharing
        try:
            redacted_vars = redact(template_vars, sharing_level, household_salt=str(household_id))
        except RedactionError:
            return AnswerResult(answer=None, provider_used=None, reason="disabled")

        rendered_data = json.dumps(redacted_vars, default=str, indent=2)
        history_block = ""
        if history:
            lines: list[str] = []
            for turn in history:
                label = "User" if turn["role"] == "user" else "Assistant"
                lines.append(f"{label}: {turn['content']}")
            history_block = "\nConversation so far:\n" + "\n".join(lines) + "\n"
        prompt = qa_template.format(
            data=rendered_data, question=question, history_block=history_block
        )
        prompt_fingerprint = hashlib.sha256(prompt.encode()).hexdigest()
        model_name = provider.get_model_name()

    except Exception as exc:
        logger.error(
            "insights.qa.unexpected_error",
            household_id=str(household_id),
            error=str(exc),
        )
        try:
            await session.rollback()
        except Exception as rollback_exc:
            logger.warning(
                "insights.qa.rollback_failed",
                household_id=str(household_id),
                error=str(rollback_exc),
            )
        return AnswerResult(answer=None, provider_used=None, reason="no_provider")

    # Phase 2: LLM call — separate from setup so audit failures don't discard results
    start = time.monotonic()
    result: CompletionResult | None = None
    error_detail: str | None = None

    try:
        result = await provider.complete(prompt, _SYSTEM_PROMPT, 1024)
    except Exception as exc:
        error_detail = str(exc)
        logger.warning(
            "insights.qa.provider_error",
            household_id=str(household_id),
            error=str(exc),
        )

    duration_ms = int((time.monotonic() - start) * 1000)

    # Phase 3: Audit log — failure is logged but does not discard the LLM result
    try:
        await _record_audit_and_update_budget(
            session,
            household_id=household_id,
            config=config,
            model_name=model_name,
            prompt_template=qa_template,
            prompt_fingerprint=prompt_fingerprint,
            result=result,
            insight_category=InsightCategory.QA,
            duration_ms=duration_ms,
            error_detail=error_detail,
            provider_config_id=config.id,
        )
    except Exception as exc:
        logger.error(
            "insights.qa.audit_error",
            household_id=str(household_id),
            error=str(exc),
        )
        try:
            await session.rollback()
        except Exception as rollback_exc:
            logger.warning(
                "insights.qa.rollback_failed",
                household_id=str(household_id),
                error=str(rollback_exc),
            )

    if result is None:
        return AnswerResult(answer=None, provider_used=model_name, reason="no_provider")

    return AnswerResult(answer=result.text, provider_used=model_name, reason=None)


# ---------------------------------------------------------------------------
# Provider availability test
# ---------------------------------------------------------------------------


async def test_provider_config(
    session: AsyncSession,
    config_id: uuid.UUID,
    household_id: uuid.UUID,
    master_key: str,
) -> tuple[bool, str | None, str | None]:
    """Test whether a specific provider config is reachable.

    Returns (available, model_name, error_message).
    Never raises — connection failures are captured as available=False.
    """
    config = await get_provider_config(session, config_id, household_id)
    provider = _build_provider(config, master_key)
    try:
        available = await provider.is_available()
    except Exception:
        available = False

    if available:
        return True, provider.get_model_name(), None
    base = config.base_url or "no base URL configured"
    return False, None, f"Connection refused at {base}"


# ---------------------------------------------------------------------------
# Provider config CRUD
# ---------------------------------------------------------------------------


async def _disable_other_providers(
    session: AsyncSession,
    household_id: uuid.UUID,
    exclude_id: uuid.UUID,
) -> None:
    """Enforce single-active-provider constraint: disable all enabled configs except exclude_id."""
    await session.execute(
        sa.update(InsightProviderConfig)
        .where(
            InsightProviderConfig.household_id == household_id,
            InsightProviderConfig.id != exclude_id,
            InsightProviderConfig.enabled.is_(True),
            InsightProviderConfig.archived_at.is_(None),
        )
        .values(enabled=False)
    )


async def list_provider_configs(
    session: AsyncSession,
    household_id: uuid.UUID,
) -> list[InsightProviderConfig]:
    result = await session.execute(
        sa.select(InsightProviderConfig)
        .where(
            InsightProviderConfig.household_id == household_id,
            InsightProviderConfig.archived_at.is_(None),
        )
        .order_by(InsightProviderConfig.priority)
    )
    return list(result.scalars().all())


async def get_provider_config(
    session: AsyncSession,
    config_id: uuid.UUID,
    household_id: uuid.UUID,
) -> InsightProviderConfig:
    result = await session.execute(
        sa.select(InsightProviderConfig).where(
            InsightProviderConfig.id == config_id,
            InsightProviderConfig.household_id == household_id,
            InsightProviderConfig.archived_at.is_(None),
        )
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise NotFoundError("provider config not found")
    return config


async def create_provider_config(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    provider: str,
    priority: int,
    enabled: bool,
    base_url: str | None,
    model_name: str | None,
    credentials: dict[str, Any] | None,
    ai_data_sharing: str,
    master_key: str,
    actor_id: uuid.UUID,
) -> InsightProviderConfig:
    """Create a new provider config. Rejects full data_sharing for remote providers."""
    _validate_data_sharing(provider, ai_data_sharing)

    credentials_encrypted: str | None = None
    if credentials:
        credentials_encrypted = encrypt_dict(credentials, master_key)

    config = InsightProviderConfig(
        household_id=household_id,
        provider=provider,
        priority=priority,
        enabled=enabled,
        base_url=base_url,
        model_name=model_name,
        credentials_encrypted=credentials_encrypted,
        ai_data_sharing=ai_data_sharing,
    )
    session.add(config)
    await session.flush()

    if enabled:
        await _disable_other_providers(session, household_id, exclude_id=config.id)

    await _write_config_audit(
        session,
        actor_id=actor_id,
        household_id=household_id,
        entity_id=config.id,
        operation=str(AuditOperation.CREATE),
        delta=[{"op": "add", "path": "/provider", "value": provider}],
    )
    logger.info(
        "insights.provider_config.created",
        config_id=str(config.id),
        provider=provider,
        household_id=str(household_id),
    )
    return config


async def update_provider_config(
    session: AsyncSession,
    *,
    config_id: uuid.UUID,
    household_id: uuid.UUID,
    enabled: bool | None = None,
    priority: int | None = None,
    base_url: str | None = None,
    model_name: str | None = None,
    credentials: dict[str, Any] | None = None,
    ai_data_sharing: str | None = None,
    master_key: str,
    actor_id: uuid.UUID,
) -> InsightProviderConfig:
    config = await get_provider_config(session, config_id, household_id)

    target_sharing = ai_data_sharing or config.ai_data_sharing
    _validate_data_sharing(config.provider, target_sharing)

    delta: list[dict[str, Any]] = []

    if enabled is not None and enabled != config.enabled:
        delta.append({"op": "replace", "path": "/enabled", "value": enabled})
        config.enabled = enabled
        if enabled:
            await _disable_other_providers(session, household_id, exclude_id=config_id)
    if priority is not None and priority != config.priority:
        delta.append({"op": "replace", "path": "/priority", "value": priority})
        config.priority = priority
    if base_url is not None and base_url != config.base_url:
        delta.append({"op": "replace", "path": "/base_url", "value": base_url})
        config.base_url = base_url
    if model_name is not None and model_name != config.model_name:
        delta.append({"op": "replace", "path": "/model_name", "value": model_name})
        config.model_name = model_name
    if ai_data_sharing is not None and ai_data_sharing != config.ai_data_sharing:
        delta.append({"op": "replace", "path": "/ai_data_sharing", "value": ai_data_sharing})
        config.ai_data_sharing = ai_data_sharing
    if credentials is not None:
        config.credentials_encrypted = encrypt_dict(credentials, master_key)
        delta.append({"op": "replace", "path": "/credentials_encrypted", "value": "[redacted]"})

    if delta:
        await session.flush()
        await _write_config_audit(
            session,
            actor_id=actor_id,
            household_id=household_id,
            entity_id=config_id,
            operation=str(AuditOperation.UPDATE),
            delta=delta,
        )

    return config


async def archive_provider_config(
    session: AsyncSession,
    *,
    config_id: uuid.UUID,
    household_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    from app.platform.time import utcnow

    config = await get_provider_config(session, config_id, household_id)
    config.archived_at = utcnow()
    config.archived_by = actor_id
    await session.flush()

    await _write_config_audit(
        session,
        actor_id=actor_id,
        household_id=household_id,
        entity_id=config_id,
        operation=str(AuditOperation.ARCHIVE),
        delta=[{"op": "replace", "path": "/archived_at", "value": "now"}],
    )
    logger.info(
        "insights.provider_config.archived",
        config_id=str(config_id),
        household_id=str(household_id),
    )


# ---------------------------------------------------------------------------
# Budget CRUD
# ---------------------------------------------------------------------------


async def update_budget(
    session: AsyncSession,
    *,
    household_id: uuid.UUID,
    token_limit: int | None = None,
    cost_limit: Decimal | None = None,
    currency: str | None = None,
    overage_behavior: str | None = None,
    actor_id: uuid.UUID,
    provider_config_id: uuid.UUID | None = None,
) -> TokenBudget:
    budget = await get_or_create_budget(session, household_id, provider_config_id)
    delta: list[dict[str, Any]] = []

    if token_limit is not None and token_limit != budget.token_limit:
        delta.append({"op": "replace", "path": "/token_limit", "value": token_limit})
        budget.token_limit = token_limit
    if cost_limit is not None and cost_limit != budget.cost_limit:
        delta.append({"op": "replace", "path": "/cost_limit", "value": str(cost_limit)})
        budget.cost_limit = cost_limit
    if currency is not None and currency != budget.currency:
        delta.append({"op": "replace", "path": "/currency", "value": currency})
        budget.currency = currency
    if overage_behavior is not None and overage_behavior != budget.overage_behavior:
        delta.append({"op": "replace", "path": "/overage_behavior", "value": overage_behavior})
        budget.overage_behavior = overage_behavior

    if delta:
        await session.flush()
        await _write_config_audit(
            session,
            actor_id=actor_id,
            household_id=household_id,
            entity_id=budget.id,
            operation=str(AuditOperation.UPDATE),
            delta=delta,
        )

    return budget


# ---------------------------------------------------------------------------
# Audit log query
# ---------------------------------------------------------------------------


async def list_audit_log(
    session: AsyncSession,
    household_id: uuid.UUID,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[InsightAuditLog]:
    result = await session.execute(
        sa.select(InsightAuditLog)
        .where(InsightAuditLog.household_id == household_id)
        .order_by(InsightAuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _validate_data_sharing(provider: str, ai_data_sharing: str) -> None:
    """Reject full data sharing for remote providers. Hard gate — not user-configurable."""
    try:
        p = InsightProviderEnum(provider)
    except ValueError:
        return
    if p in REMOTE_PROVIDERS and ai_data_sharing == AiDataSharing.FULL:
        raise ValidationError(
            f"ai_data_sharing='full' is not permitted for remote provider '{provider}'. "
            "Full data sharing is available for local providers only."
        )


async def _write_config_audit(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    household_id: uuid.UUID,
    entity_id: uuid.UUID,
    operation: str,
    delta: list[dict[str, Any]],
) -> None:
    await audit_service.log(
        session,
        household_id=household_id,
        actor_type=ActorType.USER,
        actor_source="insights_config",
        entity_type="insights_provider_config",
        entity_id=entity_id,
        operation=AuditOperation(operation),
        delta=delta,
        actor_id=actor_id,
    )
