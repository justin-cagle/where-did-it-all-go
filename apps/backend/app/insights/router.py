"""FastAPI routes for the insights module.

All routes scoped under /api/v1/households/{household_id}/insights/.
Household membership enforced by HouseholdMember dependency.

Routes:
  GET    /providers                           list InsightProviderConfigs
  POST   /providers                           add provider config
  PATCH  /providers/{config_id}               update config (enable/disable, model, credentials)
  DELETE /providers/{config_id}               soft delete
  POST   /providers/{config_id}/test          test provider availability
  GET    /providers/ollama/models             list locally installed Ollama models
  POST   /providers/ollama/pull              pull a new Ollama model (SSE)
  DELETE /providers/ollama/models/{name}      delete an installed Ollama model
  GET    /budget                              current period TokenBudget
  PATCH  /budget                              update limits + overage_behavior
  GET    /audit                               paginated InsightAuditLog
  POST   /ask                                 synchronous Q&A
  POST   /generate                            manually trigger insight generation job
"""

import json
import urllib.parse
import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

import arq
import httpx
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
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
    OllamaModelOut,
    OllamaModelsResponse,
    OllamaPullRequest,
    ProviderConfigCreate,
    ProviderConfigOut,
    ProviderConfigUpdate,
    ProviderTestResponse,
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


# ---------------------------------------------------------------------------
# Ollama model management  (must be registered before /{config_id} routes)
# ---------------------------------------------------------------------------


async def _get_ollama_config(
    session: AsyncSession,
    household_id: uuid.UUID,
) -> tuple[str, str] | None:
    """Return (base_url, model_name) for the first active Ollama config, or None."""
    import sqlalchemy as sa

    from app.insights.models import InsightProviderConfig

    result = await session.execute(
        sa.select(InsightProviderConfig).where(
            InsightProviderConfig.household_id == household_id,
            InsightProviderConfig.provider == "local_ollama",
            InsightProviderConfig.archived_at.is_(None),
        )
    )
    config = result.scalars().first()
    if config is None or not config.base_url:
        return None
    return config.base_url, config.model_name or ""


@router.get(
    "/households/{household_id}/insights/providers/ollama/models",
    response_model=OllamaModelsResponse,
)
async def list_ollama_models(
    household_id: HouseholdMember,
    session: _DbSession,
    current_user: CurrentUser,
) -> OllamaModelsResponse:
    """List models installed on the configured Ollama instance.

    Returns empty list (not 400) if Ollama is unreachable.
    Returns 400 if no Ollama provider is configured.
    """
    config_info = await _get_ollama_config(session, household_id)
    if config_info is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="no Ollama provider configured for this household",
        )
    base_url, _ = config_info

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{base_url.rstrip('/')}/api/tags")
            if resp.status_code != 200:
                return OllamaModelsResponse(models=[])
            data = resp.json()
    except Exception:
        return OllamaModelsResponse(models=[])

    models: list[OllamaModelOut] = []
    for m in data.get("models", []):
        name = str(m.get("name", ""))
        size = int(m.get("size", 0))
        modified = str(m.get("modified_at", ""))
        if name:
            models.append(OllamaModelOut(name=name, size_bytes=size, modified_at=modified))
    return OllamaModelsResponse(models=models)


async def _ollama_pull_stream(
    base_url: str,
    model_name: str,
) -> AsyncGenerator[str, None]:
    """Yield SSE-formatted pull progress events from Ollama."""
    try:
        async with httpx.AsyncClient(timeout=None) as client:  # noqa: S113
            async with client.stream(
                "POST",
                f"{base_url.rstrip('/')}/api/pull",
                json={"name": model_name, "stream": True},
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:  # noqa: S112
                        continue
                    status_val = obj.get("status", "")
                    completed = obj.get("completed")
                    total = obj.get("total")
                    payload: dict[str, object] = {"status": status_val}
                    if completed is not None:
                        payload["completed"] = completed
                    if total is not None:
                        payload["total"] = total
                    yield f"data: {json.dumps(payload)}\n\n"
    except Exception as exc:
        yield f"data: {json.dumps({'status': 'error', 'error': str(exc)})}\n\n"


@router.post(
    "/households/{household_id}/insights/providers/ollama/pull",
    response_class=StreamingResponse,
)
async def pull_ollama_model(
    household_id: HouseholdMember,
    body: OllamaPullRequest,
    session: _DbSession,
    current_user: CurrentUser,
) -> StreamingResponse:
    """Pull a model from Ollama registry. Streams SSE progress events."""
    config_info = await _get_ollama_config(session, household_id)
    if config_info is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="no Ollama provider configured for this household",
        )
    base_url, _ = config_info

    return StreamingResponse(
        _ollama_pull_stream(base_url, body.model_name),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete(
    "/households/{household_id}/insights/providers/ollama/models/{model_name:path}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_ollama_model(
    household_id: HouseholdMember,
    model_name: str,
    session: _DbSession,
    current_user: CurrentUser,
) -> None:
    """Delete a locally installed Ollama model. model_name may contain colons."""
    config_info = await _get_ollama_config(session, household_id)
    if config_info is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="no Ollama provider configured for this household",
        )
    base_url, _ = config_info
    decoded_name = urllib.parse.unquote(model_name)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.request(
                "DELETE",
                f"{base_url.rstrip('/')}/api/delete",
                json={"name": decoded_name},
            )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ollama unreachable: {exc}",
        ) from exc

    if resp.status_code == 404:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="model not found")
    if resp.status_code not in (200, 204):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ollama returned {resp.status_code}",
        )


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


@router.post(
    "/households/{household_id}/insights/providers/{config_id}/test",
    response_model=ProviderTestResponse,
)
async def test_provider(
    household_id: HouseholdMember,
    config_id: uuid.UUID,
    session: _DbSession,
    current_user: CurrentUser,
) -> ProviderTestResponse:
    """Check whether a specific provider config is reachable.

    Always returns 200. Never raises on connection failure.
    """
    settings = get_settings()
    try:
        available, model_name, error = await service.test_provider_config(
            session,
            config_id=config_id,
            household_id=household_id,
            master_key=settings.master_key,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ProviderTestResponse(available=available, model_name=model_name, error=error)


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
    settings = get_settings()
    _, config = await service.get_active_provider(session, household_id, settings.master_key)
    provider_config_id = config.id if config is not None else None
    budget = await service.get_or_create_budget(session, household_id, provider_config_id)
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
    settings = get_settings()
    _, config = await service.get_active_provider(session, household_id, settings.master_key)
    provider_config_id = config.id if config is not None else None
    budget = await service.update_budget(
        session,
        household_id=household_id,
        token_limit=body.token_limit,
        cost_limit=body.cost_limit,
        currency=body.currency,
        overage_behavior=body.overage_behavior,
        actor_id=current_user.id,
        provider_config_id=provider_config_id,
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
        history=[{"role": t.role, "content": t.content} for t in body.history],
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
