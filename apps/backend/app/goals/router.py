"""FastAPI routes for the goals module.

Routes under /api/v1/households/{household_id}/goals/

  GET    /                              list goals (optionally filtered by status)
  POST   /                              create goal
  GET    /{id}                          get goal
  PATCH  /{id}                          update goal
  DELETE /{id}                          archive goal
  POST   /{id}/pause                    pause active goal
  POST   /{id}/resume                   resume paused goal
  POST   /{id}/complete                 manual completion trigger
  GET    /{id}/status                   current GoalSnapshot (latest burn-up)
  GET    /{id}/history                  GoalSnapshot history over time
  GET    /{id}/contributions            list contributions + per-user breakdown
  POST   /{id}/contributions            log manual contribution
  GET    /{id}/funding-sources/         list funding sources
  POST   /{id}/funding-sources/         add funding source
  DELETE /{id}/funding-sources/{sid}    remove funding source
  GET    /status                        all active goals status summary
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.goals import service
from app.goals.deps import HouseholdMember
from app.goals.enums import GoalStatus
from app.goals.schemas import (
    ContributionBreakdown,
    ContributionCreate,
    ContributionOut,
    FundingSourceCreate,
    FundingSourceOut,
    GoalCreate,
    GoalOut,
    GoalSnapshotOut,
    GoalUpdate,
    UserContributionTotal,
)
from app.households.deps import CurrentUser

router = APIRouter()

_base = "/households/{household_id}/goals"


# ---------------------------------------------------------------------------
# All-goals status summary (must register before /{goal_id} routes)
# ---------------------------------------------------------------------------


@router.get(_base + "/status", response_model=list[GoalSnapshotOut])
async def all_goals_status(
    household_id: HouseholdMember,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[GoalSnapshotOut]:
    snaps = await service.get_all_status(session, household_id=household_id)
    await session.commit()
    return [GoalSnapshotOut.model_validate(s) for s in snaps]


# ---------------------------------------------------------------------------
# Goal CRUD
# ---------------------------------------------------------------------------


@router.get(_base, response_model=list[GoalOut])
async def list_goals(
    household_id: HouseholdMember,
    session: Annotated[AsyncSession, Depends(get_db)],
    goal_status: Annotated[GoalStatus | None, Query(alias="status")] = None,
) -> list[GoalOut]:
    goals = await service.list_goals(session, household_id=household_id, status=goal_status)
    return [GoalOut.model_validate(g) for g in goals]


@router.post(_base, response_model=GoalOut, status_code=status.HTTP_201_CREATED)
async def create_goal(
    household_id: HouseholdMember,
    body: GoalCreate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> GoalOut:
    goal = await service.create_goal(
        session,
        household_id=household_id,
        actor_id=current_user.id,
        name=body.name,
        goal_type=body.goal_type,
        description=body.description,
        target_amount=body.target_amount,
        currency=body.currency,
        target_date=body.target_date,
        funding_strategy=body.funding_strategy,
        completion_policy=body.completion_policy,
        auto_extend_amount=body.auto_extend_amount,
        owner_id=body.owner_id,
        linked_debt_plan_id=body.linked_debt_plan_id,
        linked_category_id=body.linked_category_id,
        minimum_balance_threshold=body.minimum_balance_threshold,
        metadata=body.metadata_,
    )
    await session.commit()
    return GoalOut.model_validate(goal)


@router.get(_base + "/{goal_id}", response_model=GoalOut)
async def get_goal(
    household_id: HouseholdMember,
    goal_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> GoalOut:
    try:
        goal = await service.get_goal(session, goal_id=goal_id, household_id=household_id)
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return GoalOut.model_validate(goal)


@router.patch(_base + "/{goal_id}", response_model=GoalOut)
async def update_goal(
    household_id: HouseholdMember,
    goal_id: uuid.UUID,
    body: GoalUpdate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> GoalOut:
    try:
        goal = await service.update_goal(
            session,
            goal_id=goal_id,
            household_id=household_id,
            actor_id=current_user.id,
            name=body.name,
            description=body.description,
            target_amount=body.target_amount,
            currency=body.currency,
            target_date=body.target_date,
            funding_strategy=body.funding_strategy,
            completion_policy=body.completion_policy,
            auto_extend_amount=body.auto_extend_amount,
            owner_id=body.owner_id,
            linked_debt_plan_id=body.linked_debt_plan_id,
            linked_category_id=body.linked_category_id,
            minimum_balance_threshold=body.minimum_balance_threshold,
            metadata_=body.metadata_,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()
    return GoalOut.model_validate(goal)


@router.delete(_base + "/{goal_id}", response_model=GoalOut)
async def archive_goal(
    household_id: HouseholdMember,
    goal_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> GoalOut:
    try:
        goal = await service.archive_goal(
            session,
            goal_id=goal_id,
            household_id=household_id,
            actor_id=current_user.id,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()
    return GoalOut.model_validate(goal)


# ---------------------------------------------------------------------------
# State transitions
# ---------------------------------------------------------------------------


@router.post(_base + "/{goal_id}/pause", response_model=GoalOut)
async def pause_goal(
    household_id: HouseholdMember,
    goal_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> GoalOut:
    try:
        goal = await service.pause_goal(
            session,
            goal_id=goal_id,
            household_id=household_id,
            actor_id=current_user.id,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except service.ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await session.commit()
    return GoalOut.model_validate(goal)


@router.post(_base + "/{goal_id}/resume", response_model=GoalOut)
async def resume_goal(
    household_id: HouseholdMember,
    goal_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> GoalOut:
    try:
        goal = await service.resume_goal(
            session,
            goal_id=goal_id,
            household_id=household_id,
            actor_id=current_user.id,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except service.ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await session.commit()
    return GoalOut.model_validate(goal)


@router.post(_base + "/{goal_id}/complete", status_code=status.HTTP_204_NO_CONTENT)
async def manual_complete(
    household_id: HouseholdMember,
    goal_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    try:
        await service.manual_complete(
            session,
            goal_id=goal_id,
            household_id=household_id,
            actor_id=current_user.id,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()


# ---------------------------------------------------------------------------
# Burn-up status
# ---------------------------------------------------------------------------


@router.get(_base + "/{goal_id}/status", response_model=GoalSnapshotOut)
async def get_goal_status(
    household_id: HouseholdMember,
    goal_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> GoalSnapshotOut:
    try:
        snap = await service.compute_burn_up(session, goal_id=goal_id, household_id=household_id)
        await session.commit()
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return GoalSnapshotOut.model_validate(snap)


@router.get(_base + "/{goal_id}/history", response_model=list[GoalSnapshotOut])
async def list_goal_history(
    household_id: HouseholdMember,
    goal_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[GoalSnapshotOut]:
    try:
        snaps = await service.list_snapshots(session, goal_id=goal_id, household_id=household_id)
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [GoalSnapshotOut.model_validate(s) for s in snaps]


# ---------------------------------------------------------------------------
# Contributions
# ---------------------------------------------------------------------------


@router.get(_base + "/{goal_id}/contributions", response_model=ContributionBreakdown)
async def list_contributions(
    household_id: HouseholdMember,
    goal_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ContributionBreakdown:
    try:
        breakdown = await service.get_per_user_contributions(
            session, goal_id=goal_id, household_id=household_id
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ContributionBreakdown(
        contributions=[ContributionOut.model_validate(c) for c in breakdown.contributions],
        per_user=[
            UserContributionTotal(
                attributed_to_user_id=u.attributed_to_user_id,
                total=u.total,
                currency=u.currency,
            )
            for u in breakdown.per_user
        ],
        household_total=breakdown.household_total,
        currency=breakdown.currency,
    )


@router.post(
    _base + "/{goal_id}/contributions",
    response_model=ContributionOut,
    status_code=status.HTTP_201_CREATED,
)
async def log_contribution(
    household_id: HouseholdMember,
    goal_id: uuid.UUID,
    body: ContributionCreate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ContributionOut:
    try:
        contrib = await service.log_contribution(
            session,
            goal_id=goal_id,
            household_id=household_id,
            amount=body.amount,
            currency=body.currency,
            contributed_at=body.contributed_at,
            contribution_type=body.contribution_type,
            transaction_id=body.transaction_id,
            attributed_to_user_id=body.attributed_to_user_id,
            note=body.note,
            actor_id=current_user.id,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except service.ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await session.commit()
    return ContributionOut.model_validate(contrib)


# ---------------------------------------------------------------------------
# Funding sources
# ---------------------------------------------------------------------------


@router.get(_base + "/{goal_id}/funding-sources/", response_model=list[FundingSourceOut])
async def list_funding_sources(
    household_id: HouseholdMember,
    goal_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[FundingSourceOut]:
    try:
        sources = await service.list_funding_sources(
            session, goal_id=goal_id, household_id=household_id
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [FundingSourceOut.model_validate(s) for s in sources]


@router.post(
    _base + "/{goal_id}/funding-sources/",
    response_model=FundingSourceOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_funding_source(
    household_id: HouseholdMember,
    goal_id: uuid.UUID,
    body: FundingSourceCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> FundingSourceOut:
    try:
        fs = await service.create_funding_source(
            session,
            goal_id=goal_id,
            household_id=household_id,
            source_type=body.source_type,
            source_id=body.source_id,
            attributed_to_user_id=body.attributed_to_user_id,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()
    return FundingSourceOut.model_validate(fs)


@router.delete(
    _base + "/{goal_id}/funding-sources/{source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_funding_source(
    household_id: HouseholdMember,
    goal_id: uuid.UUID,
    source_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    try:
        await service.delete_funding_source(
            session,
            source_id=source_id,
            goal_id=goal_id,
            household_id=household_id,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()
