"""FastAPI routes for the insights module.

All routes scoped under /api/v1/households/{household_id}/insights/.
Household membership enforced by HouseholdMember dependency.

Routes:
  GET    /providers                   list InsightProviderConfigs
  POST   /providers                   add provider config
  PATCH  /providers/{config_id}       update config (enable/disable, model, credentials)
  DELETE /providers/{config_id}       soft delete
  GET    /budget                      current period TokenBudget
  PATCH  /budget                      update limits + overage_behavior
  GET    /audit                       paginated InsightAuditLog
  POST   /ask                         synchronous Q&A
  POST   /generate                    manually trigger insight generation job
"""

import uuid
from typing import Annotated

import arq
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.households.deps import CurrentUser
from app.insights import service
from app.insights.deps import HouseholdMember
from app.insights.schemas import (
    AskRequest,
    AskResponse,
    AuditLogOut,
    GenerateResponse,
    ProviderConfigCreate,
    ProviderConfigOut,
    ProviderConfigUpdate,
    TokenBudgetOut,
    TokenBudgetUpdate,
)
from app.security.ratelimit import get_household_id, get_limiter
from app.worker.settings import get_redis_settings

router = APIRouter(tags=["insights"])
limiter = get_limiter()

_DbSession = Annotated[AsyncSession, Depends(get_db)]


async def _get_arq_pool() -> arq.ArqRedis:
    redis_settings: RedisSettings = get_redis_settings()
    return await arq.create_pool(redis_settings)


# ---------------------------------------------------------------------------
# Provider configs
# ---------------------------------------------------------------------------


@router.get(
    "/households/{household_id}/insights/providers",
    response_model=list[ProviderConfigOut],
)
async def list_providers(
    household_id: HouseholdMember,
    session: _DbSession,
    current_user: CurrentUser,
) -> list[ProviderConfigOut]:
    configs = await service.list_provider_configs(session, household_id)
    return [ProviderConfigOut.model_validate(c) for c in configs]


@router.post(
    "/households/{household_id}/insights/providers",
    response_model=ProviderConfigOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_provider(
    household_id: HouseholdMember,
    body: ProviderConfigCreate,
    session: _DbSession,
    current_user: CurrentUser,
) -> ProviderConfigOut:
    settings = get_settings()
    try:
        config = await service.create_provider_config(
            session,
            household_id=household_id,
            provider=body.provider,
            priority=body.priority,
            enabled=body.enabled,
            base_url=body.base_url,
            model_name=body.model_name,
            credentials=body.credentials,
            ai_data_sharing=body.ai_data_sharing,
            master_key=settings.master_key,
            actor_id=current_user.id,
        )
        await session.commit()
    except service.ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return ProviderConfigOut.model_validate(config)


@router.patch(
    "/households/{household_id}/insights/providers/{config_id}",
    response_model=ProviderConfigOut,
)
async def update_provider(
    household_id: HouseholdMember,
    config_id: uuid.UUID,
    body: ProviderConfigUpdate,
    session: _DbSession,
    current_user: CurrentUser,
) -> ProviderConfigOut:
    settings = get_settings()
    try:
        config = await service.update_provider_config(
            session,
            config_id=config_id,
            household_id=household_id,
            enabled=body.enabled,
            priority=body.priority,
            base_url=body.base_url,
            model_name=body.model_name,
            credentials=body.credentials,
            ai_data_sharing=body.ai_data_sharing,
            master_key=settings.master_key,
            actor_id=current_user.id,
        )
        await session.commit()
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except service.ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return ProviderConfigOut.model_validate(config)


@router.delete(
    "/households/{household_id}/insights/providers/{config_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_provider(
    household_id: HouseholdMember,
    config_id: uuid.UUID,
    session: _DbSession,
    current_user: CurrentUser,
) -> None:
    try:
        await service.archive_provider_config(
            session,
            config_id=config_id,
            household_id=household_id,
            actor_id=current_user.id,
        )
        await session.commit()
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------


@router.get(
    "/households/{household_id}/insights/budget",
    response_model=TokenBudgetOut,
)
async def get_budget(
    household_id: HouseholdMember,
    session: _DbSession,
    current_user: CurrentUser,
) -> TokenBudgetOut:
    budget = await service.get_or_create_budget(session, household_id)
    await session.commit()
    return TokenBudgetOut.model_validate(budget)


@router.patch(
    "/households/{household_id}/insights/budget",
    response_model=TokenBudgetOut,
)
async def update_budget(
    household_id: HouseholdMember,
    body: TokenBudgetUpdate,
    session: _DbSession,
    current_user: CurrentUser,
) -> TokenBudgetOut:
    budget = await service.update_budget(
        session,
        household_id=household_id,
        token_limit=body.token_limit,
        cost_limit=body.cost_limit,
        currency=body.currency,
        overage_behavior=body.overage_behavior,
        actor_id=current_user.id,
    )
    await session.commit()
    return TokenBudgetOut.model_validate(budget)


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


@router.get(
    "/households/{household_id}/insights/audit",
    response_model=list[AuditLogOut],
)
async def list_audit(
    household_id: HouseholdMember,
    session: _DbSession,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AuditLogOut]:
    logs = await service.list_audit_log(session, household_id, limit=limit, offset=offset)
    return [AuditLogOut.model_validate(entry) for entry in logs]


# ---------------------------------------------------------------------------
# Q&A
# ---------------------------------------------------------------------------


@router.post(
    "/households/{household_id}/insights/ask",
    response_model=AskResponse,
)
@limiter.limit("10/minute", key_func=get_household_id)  # type: ignore[misc]
async def ask(
    request: Request,
    household_id: HouseholdMember,
    body: AskRequest,
    session: _DbSession,
    current_user: CurrentUser,
) -> AskResponse:
    settings = get_settings()
    result = await service.answer_question(
        session,
        household_id=household_id,
        question=body.question,
        master_key=settings.master_key,
    )
    await session.commit()
    return AskResponse(
        answer=result["answer"],
        provider_used=result["provider_used"],
        reason=result["reason"],
    )


# ---------------------------------------------------------------------------
# Manual trigger
# ---------------------------------------------------------------------------


@router.post(
    "/households/{household_id}/insights/generate",
    response_model=GenerateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_generate(
    household_id: HouseholdMember,
    session: _DbSession,
    current_user: CurrentUser,
) -> GenerateResponse:
    """Enqueue the insight generation job. Returns job_id for polling."""
    pool = await _get_arq_pool()
    try:
        job = await pool.enqueue_job(
            "generate_insights_job",
            household_id=str(household_id),
        )
    finally:
        await pool.aclose()

    job_id = job.job_id if job else "unknown"
    return GenerateResponse(job_id=job_id)
