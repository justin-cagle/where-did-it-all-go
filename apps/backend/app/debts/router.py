"""FastAPI routes for the debts module.

Routes under /api/v1/households/{household_id}/debt-plans/

  GET    /                                list plans (all current versions)
  POST   /                                create plan
  GET    /{id}                            get current plan version
  PATCH  /{id}                            edit (creates new version)
  DELETE /{id}                            archive
  GET    /{id}/history                    list all versions
  GET    /{id}/schedule                   full amortization table grouped by account
  GET    /{id}/summary                    totals + payoff date + savings
  POST   /{id}/compute                    manually trigger schedule recompute
  GET    /{id}/comparison                 side-by-side current vs ?compare=method
  POST   /accounts/{account_id}/payment  record actual payment; trigger deviation check
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.debts import service
from app.debts.deps import HouseholdMember
from app.debts.schemas import (
    DebtPaymentRecord,
    DebtPlanComparisonItem,
    DebtPlanComparisonOut,
    DebtPlanCreate,
    DebtPlanOut,
    DebtPlanScheduleByAccount,
    DebtPlanScheduleRow,
    DebtPlanSummaryOut,
    DebtPlanUpdate,
)
from app.households.deps import CurrentUser

router = APIRouter()

_base = "/households/{household_id}/debt-plans"


# ---------------------------------------------------------------------------
# Plan CRUD
# ---------------------------------------------------------------------------


@router.get(_base, response_model=list[DebtPlanOut])
async def list_plans(
    household_id: HouseholdMember,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[DebtPlanOut]:
    plans = await service.list_plans(session, household_id=household_id)
    return [DebtPlanOut.model_validate(p) for p in plans]


@router.post(_base, response_model=DebtPlanOut, status_code=status.HTTP_201_CREATED)
async def create_plan(
    household_id: HouseholdMember,
    body: DebtPlanCreate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DebtPlanOut:
    plan = await service.create_plan(
        session,
        household_id=household_id,
        actor_id=current_user.id,
        name=body.name,
        method=body.method,
        monthly_extra_payment=body.monthly_extra_payment,
        currency=body.currency,
        snowball_flow=body.snowball_flow,
        account_ids=body.account_ids,
        effective_from=body.effective_from,
    )
    await session.commit()
    return DebtPlanOut.model_validate(plan)


@router.get(_base + "/{plan_id}", response_model=DebtPlanOut)
async def get_plan(
    household_id: HouseholdMember,
    plan_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DebtPlanOut:
    try:
        plan = await service.get_plan(session, plan_group_id=plan_id, household_id=household_id)
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return DebtPlanOut.model_validate(plan)


@router.patch(_base + "/{plan_id}", response_model=DebtPlanOut)
async def update_plan(
    household_id: HouseholdMember,
    plan_id: uuid.UUID,
    body: DebtPlanUpdate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DebtPlanOut:
    try:
        plan = await service.update_plan(
            session,
            plan_group_id=plan_id,
            household_id=household_id,
            actor_id=current_user.id,
            effective_from=body.effective_from,
            name=body.name,
            method=body.method,
            monthly_extra_payment=body.monthly_extra_payment,
            currency=body.currency,
            snowball_flow=body.snowball_flow,
            account_ids=body.account_ids,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()
    return DebtPlanOut.model_validate(plan)


@router.delete(_base + "/{plan_id}", response_model=DebtPlanOut)
async def archive_plan(
    household_id: HouseholdMember,
    plan_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DebtPlanOut:
    try:
        plan = await service.archive_plan(
            session,
            plan_group_id=plan_id,
            household_id=household_id,
            actor_id=current_user.id,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()
    return DebtPlanOut.model_validate(plan)


@router.get(_base + "/{plan_id}/history", response_model=list[DebtPlanOut])
async def list_plan_history(
    household_id: HouseholdMember,
    plan_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[DebtPlanOut]:
    try:
        plans = await service.list_plan_history(
            session, plan_group_id=plan_id, household_id=household_id
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [DebtPlanOut.model_validate(p) for p in plans]


# ---------------------------------------------------------------------------
# Schedule & summary
# ---------------------------------------------------------------------------


@router.get(_base + "/{plan_id}/schedule", response_model=list[DebtPlanScheduleByAccount])
async def get_schedule(
    household_id: HouseholdMember,
    plan_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[DebtPlanScheduleByAccount]:
    try:
        grouped = await service.get_schedule(
            session, plan_group_id=plan_id, household_id=household_id
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [
        DebtPlanScheduleByAccount(
            account_id=g.account_id,
            rows=[DebtPlanScheduleRow.model_validate(r) for r in g.rows],
        )
        for g in grouped
    ]


@router.get(_base + "/{plan_id}/summary", response_model=DebtPlanSummaryOut)
async def get_summary(
    household_id: HouseholdMember,
    plan_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DebtPlanSummaryOut:
    try:
        summary = await service.get_summary(
            session, plan_group_id=plan_id, household_id=household_id
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return DebtPlanSummaryOut.model_validate(summary)


@router.post(_base + "/{plan_id}/compute", response_model=DebtPlanSummaryOut)
async def compute_schedule(
    household_id: HouseholdMember,
    plan_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DebtPlanSummaryOut:
    try:
        summary = await service.compute_schedule(
            session, plan_group_id=plan_id, household_id=household_id
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()
    return DebtPlanSummaryOut.model_validate(summary)


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


@router.get(_base + "/{plan_id}/comparison", response_model=DebtPlanComparisonOut)
async def compare_plans(
    household_id: HouseholdMember,
    plan_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    compare: Annotated[str, Query(description="avalanche | snowball | minimums")] = "minimums",
) -> DebtPlanComparisonOut:
    try:
        current, compared = await service.compute_comparison(
            session,
            plan_group_id=plan_id,
            household_id=household_id,
            compare=compare,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except service.ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    def _to_item(c: service.ComparisonSummary) -> DebtPlanComparisonItem:
        return DebtPlanComparisonItem(
            label=c.label,
            total_interest=c.total_interest,
            total_paid=c.total_paid,
            months_to_payoff=c.months_to_payoff,
            payoff_date=c.payoff_date,
            interest_savings_vs_minimums=c.interest_savings_vs_minimums,
        )

    return DebtPlanComparisonOut(current=_to_item(current), compared=_to_item(compared))


# ---------------------------------------------------------------------------
# Payment recording
# ---------------------------------------------------------------------------


@router.post(_base + "/accounts/{account_id}/payment", status_code=status.HTTP_204_NO_CONTENT)
async def record_payment(
    household_id: HouseholdMember,
    account_id: uuid.UUID,
    body: DebtPaymentRecord,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await service.check_payment_deviation(
        session,
        household_id=household_id,
        account_id=account_id,
        actual_payment=body.amount,
        payment_date=body.payment_date,
    )
    await session.commit()
