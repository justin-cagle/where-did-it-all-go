"""FastAPI routes for the recommendations module.

Routes under /api/v1/households/{household_id}/recommendations/

  GET    /                              list recommendations (filterable)
  GET    /auto-apply                    list auto-apply rules
  POST   /auto-apply/{source}           toggle auto-apply for a source
  GET    /{id}                          detail
  POST   /{id}/accept                   accept a pending recommendation
  POST   /{id}/reject                   reject a pending recommendation

Note: /auto-apply routes MUST be registered before /{id} to avoid path conflict.
"""

import uuid
from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.households.deps import CurrentUser
from app.recommendations import service
from app.recommendations.deps import HouseholdMember
from app.recommendations.enums import RecommendationSource, RecommendationStatus
from app.recommendations.models import AutoApplyRule
from app.recommendations.schemas import AutoApplyRuleOut, AutoApplyToggle, RecommendationOut

router = APIRouter()

_base = "/households/{household_id}/recommendations"


@router.get(_base, response_model=list[RecommendationOut], tags=["recommendations"])
async def list_recommendations(
    household_id: HouseholdMember,
    session: Annotated[AsyncSession, Depends(get_db)],
    source: Annotated[RecommendationSource | None, Query()] = None,
    target_subsystem: Annotated[str | None, Query()] = None,
    status_filter: Annotated[
        RecommendationStatus | None, Query(alias="status")
    ] = RecommendationStatus.PENDING,
) -> list[RecommendationOut]:
    recs = await service.list_pending(
        session,
        household_id=household_id,
        source=source,
        target_subsystem=target_subsystem,
        status=status_filter,
    )
    return [RecommendationOut.model_validate(r) for r in recs]


@router.get(
    _base + "/auto-apply",
    response_model=list[AutoApplyRuleOut],
    tags=["recommendations"],
)
async def list_auto_apply_rules(
    household_id: HouseholdMember,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[AutoApplyRuleOut]:
    result = await session.execute(
        sa.select(AutoApplyRule).where(AutoApplyRule.household_id == household_id)
    )
    rules = list(result.scalars().all())
    return [AutoApplyRuleOut.model_validate(r) for r in rules]


@router.post(
    _base + "/auto-apply/{source}",
    response_model=AutoApplyRuleOut,
    tags=["recommendations"],
)
async def toggle_auto_apply(
    household_id: HouseholdMember,
    source: RecommendationSource,
    body: AutoApplyToggle,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AutoApplyRuleOut:
    rule = await service.set_auto_apply(
        session,
        household_id=household_id,
        source=source,
        enabled=body.enabled,
    )
    return AutoApplyRuleOut.model_validate(rule)


@router.get(
    _base + "/{recommendation_id}",
    response_model=RecommendationOut,
    tags=["recommendations"],
)
async def get_recommendation(
    household_id: HouseholdMember,
    recommendation_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RecommendationOut:
    try:
        rec = await service.get(
            session, recommendation_id=recommendation_id, household_id=household_id
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return RecommendationOut.model_validate(rec)


@router.post(
    _base + "/{recommendation_id}/accept",
    response_model=RecommendationOut,
    tags=["recommendations"],
)
async def accept_recommendation(
    household_id: HouseholdMember,
    recommendation_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RecommendationOut:
    try:
        rec = await service.accept(
            session,
            recommendation_id=recommendation_id,
            household_id=household_id,
            user_id=current_user.id,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except service.ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return RecommendationOut.model_validate(rec)


@router.post(
    _base + "/{recommendation_id}/reject",
    response_model=RecommendationOut,
    tags=["recommendations"],
)
async def reject_recommendation(
    household_id: HouseholdMember,
    recommendation_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RecommendationOut:
    try:
        rec = await service.reject(
            session,
            recommendation_id=recommendation_id,
            household_id=household_id,
            user_id=current_user.id,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except service.ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return RecommendationOut.model_validate(rec)
