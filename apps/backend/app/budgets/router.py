"""FastAPI routes for the budgets module.

Routes under /api/v1/households/{household_id}/budgets/

  GET    /                         list budgets (all current versions)
  POST   /                         create budget
  GET    /{id}                     get current budget version
  PATCH  /{id}                     edit (creates new version)
  DELETE /{id}                     archive
  GET    /{id}/history             list all versions
  GET    /{id}/status?as_of=DATE   full status snapshot
  GET    /{id}/lines               list budget lines
  POST   /{id}/lines               add line
  PATCH  /{id}/lines/{line_id}     update line
  DELETE /{id}/lines/{line_id}     archive line
  GET    /{id}/periods             list BudgetPeriodActuals
  POST   /{id}/compute             manually trigger actuals recompute
  POST   /{id}/income              set manual per-period income override
"""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.budgets import service
from app.budgets.deps import HouseholdMember
from app.budgets.schemas import (
    BudgetCreate,
    BudgetLineCreate,
    BudgetLineOut,
    BudgetLineStatusOut,
    BudgetLineUpdate,
    BudgetOut,
    BudgetPeriodActualOut,
    BudgetStatusOut,
    BudgetUpdate,
    PeriodIncomeOut,
    PeriodIncomeSet,
)
from app.database import get_db
from app.households.deps import CurrentUser

router = APIRouter()

_base = "/households/{household_id}/budgets"


def _snapshot_to_out(snapshot: service.BudgetStatusSnapshot) -> BudgetStatusOut:
    return BudgetStatusOut(
        budget=BudgetOut.model_validate(snapshot.budget),
        period_start=snapshot.period_start,
        period_end=snapshot.period_end,
        expected_income=snapshot.expected_income,
        lines=[
            BudgetLineStatusOut(
                line=BudgetLineOut.model_validate(r.line),
                period_actual=(
                    BudgetPeriodActualOut.model_validate(r.period_actual)
                    if r.period_actual is not None
                    else None
                ),
                planned=r.planned,
                actual=r.actual,
                carried_in=r.carried_in,
                remaining=r.remaining,
                status=r.status,
            )
            for r in snapshot.lines
        ],
    )


# ---------------------------------------------------------------------------
# Budget CRUD
# ---------------------------------------------------------------------------


@router.get(_base, response_model=list[BudgetOut], tags=["budgets"])
async def list_budgets(
    household_id: HouseholdMember,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[BudgetOut]:
    budgets = await service.list_budgets(session, household_id=household_id)
    return [BudgetOut.model_validate(b) for b in budgets]


@router.post(_base, response_model=BudgetOut, status_code=status.HTTP_201_CREATED, tags=["budgets"])
async def create_budget(
    household_id: HouseholdMember,
    body: BudgetCreate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> BudgetOut:
    budget = await service.create_budget(
        session,
        household_id=household_id,
        actor_id=current_user.id,
        name=body.name,
        period=body.period,
        start_date=body.start_date,
        method=body.method,
        end_date=body.end_date,
        owner_id=body.owner_id,
        expected_income_strategy=body.expected_income_strategy,
        expected_income=body.expected_income,
        currency=body.currency,
        income_rolling_periods=body.income_rolling_periods,
        scope_accounts=body.scope_accounts,
        scope_categories=body.scope_categories,
        scope_tags=body.scope_tags,
        pay_period_income_source_id=body.pay_period_income_source_id,
    )
    await session.commit()
    return BudgetOut.model_validate(budget)


@router.get(_base + "/{budget_id}", response_model=BudgetOut, tags=["budgets"])
async def get_budget(
    household_id: HouseholdMember,
    budget_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> BudgetOut:
    try:
        budget = await service.get_budget(
            session, budget_group_id=budget_id, household_id=household_id
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return BudgetOut.model_validate(budget)


@router.patch(_base + "/{budget_id}", response_model=BudgetOut, tags=["budgets"])
async def update_budget(
    household_id: HouseholdMember,
    budget_id: uuid.UUID,
    body: BudgetUpdate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> BudgetOut:
    try:
        updates: dict[str, object] = {}
        if body.name is not None:
            updates["name"] = body.name
        if body.end_date is not None:
            updates["end_date"] = body.end_date
        if body.method is not None:
            updates["method"] = str(body.method)
        if body.expected_income_strategy is not None:
            updates["expected_income_strategy"] = str(body.expected_income_strategy)
        if body.expected_income is not None:
            updates["expected_income"] = body.expected_income
        if body.currency is not None:
            updates["currency"] = body.currency
        if body.income_rolling_periods is not None:
            updates["income_rolling_periods"] = body.income_rolling_periods
        if body.scope_accounts is not None:
            updates["scope_accounts"] = [str(a) for a in body.scope_accounts]
        if body.scope_categories is not None:
            updates["scope_categories"] = [str(c) for c in body.scope_categories]
        if body.scope_tags is not None:
            updates["scope_tags"] = [str(t) for t in body.scope_tags]
        if body.pay_period_income_source_id is not None:
            updates["pay_period_income_source_id"] = body.pay_period_income_source_id

        budget = await service.update_budget(
            session,
            budget_group_id=budget_id,
            household_id=household_id,
            actor_id=current_user.id,
            effective_from=body.effective_from,
            **updates,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()
    return BudgetOut.model_validate(budget)


@router.delete(_base + "/{budget_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["budgets"])
async def archive_budget(
    household_id: HouseholdMember,
    budget_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    try:
        await service.archive_budget(
            session,
            budget_group_id=budget_id,
            household_id=household_id,
            actor_id=current_user.id,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()


@router.get(_base + "/{budget_id}/history", response_model=list[BudgetOut], tags=["budgets"])
async def list_budget_history(
    household_id: HouseholdMember,
    budget_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[BudgetOut]:
    history = await service.list_budget_history(
        session, budget_group_id=budget_id, household_id=household_id
    )
    return [BudgetOut.model_validate(b) for b in history]


# ---------------------------------------------------------------------------
# Status snapshot
# ---------------------------------------------------------------------------


@router.get(_base + "/{budget_id}/status", response_model=BudgetStatusOut, tags=["budgets"])
async def get_budget_status(
    household_id: HouseholdMember,
    budget_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    as_of: Annotated[date | None, Query(alias="as_of")] = None,
) -> BudgetStatusOut:
    try:
        snapshot = await service.get_status(
            session,
            budget_group_id=budget_id,
            household_id=household_id,
            as_of_date=as_of or date.today(),
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()

    return _snapshot_to_out(snapshot)


# ---------------------------------------------------------------------------
# Budget lines
# ---------------------------------------------------------------------------


@router.get(_base + "/{budget_id}/lines", response_model=list[BudgetLineOut], tags=["budgets"])
async def list_budget_lines(
    household_id: HouseholdMember,
    budget_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[BudgetLineOut]:
    lines = await service.list_budget_lines(
        session, budget_group_id=budget_id, household_id=household_id
    )
    return [BudgetLineOut.model_validate(ln) for ln in lines]


@router.post(
    _base + "/{budget_id}/lines",
    response_model=BudgetLineOut,
    status_code=status.HTTP_201_CREATED,
    tags=["budgets"],
)
async def create_budget_line(
    household_id: HouseholdMember,
    budget_id: uuid.UUID,
    body: BudgetLineCreate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> BudgetLineOut:
    try:
        line = await service.create_budget_line(
            session,
            budget_group_id=budget_id,
            household_id=household_id,
            actor_id=current_user.id,
            category_id=body.category_id,
            planned_amount=body.planned_amount,
            currency=body.currency,
            tag_id=body.tag_id,
            rollover_policy=body.rollover_policy,
            rollover_cap=body.rollover_cap,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()
    return BudgetLineOut.model_validate(line)


@router.patch(
    _base + "/{budget_id}/lines/{line_id}",
    response_model=BudgetLineOut,
    tags=["budgets"],
)
async def update_budget_line(
    household_id: HouseholdMember,
    budget_id: uuid.UUID,
    line_id: uuid.UUID,
    body: BudgetLineUpdate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> BudgetLineOut:
    try:
        line = await service.update_budget_line(
            session,
            line_id=line_id,
            budget_group_id=budget_id,
            household_id=household_id,
            actor_id=current_user.id,
            planned_amount=body.planned_amount,
            currency=body.currency,
            rollover_policy=body.rollover_policy,
            rollover_cap=body.rollover_cap,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()
    return BudgetLineOut.model_validate(line)


@router.delete(
    _base + "/{budget_id}/lines/{line_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["budgets"],
)
async def archive_budget_line(
    household_id: HouseholdMember,
    budget_id: uuid.UUID,
    line_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    try:
        await service.archive_budget_line(
            session,
            line_id=line_id,
            budget_group_id=budget_id,
            household_id=household_id,
            actor_id=current_user.id,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()


# ---------------------------------------------------------------------------
# Period actuals
# ---------------------------------------------------------------------------


@router.get(
    _base + "/{budget_id}/periods",
    response_model=list[BudgetPeriodActualOut],
    tags=["budgets"],
)
async def list_periods(
    household_id: HouseholdMember,
    budget_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[BudgetPeriodActualOut]:
    periods = await service.list_periods(
        session, budget_group_id=budget_id, household_id=household_id
    )
    return [BudgetPeriodActualOut.model_validate(p) for p in periods]


@router.post(
    _base + "/{budget_id}/compute",
    response_model=BudgetStatusOut,
    tags=["budgets"],
)
async def compute_actuals(
    household_id: HouseholdMember,
    budget_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    as_of: Annotated[date | None, Query(alias="as_of")] = None,
) -> BudgetStatusOut:
    """Manually trigger actuals recompute for the current period."""
    try:
        snapshot = await service.get_status(
            session,
            budget_group_id=budget_id,
            household_id=household_id,
            as_of_date=as_of or date.today(),
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()
    return _snapshot_to_out(snapshot)


# ---------------------------------------------------------------------------
# Per-period income override
# ---------------------------------------------------------------------------


@router.post(
    _base + "/{budget_id}/income",
    response_model=PeriodIncomeOut,
    tags=["budgets"],
)
async def set_period_income(
    household_id: HouseholdMember,
    budget_id: uuid.UUID,
    body: PeriodIncomeSet,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PeriodIncomeOut:
    try:
        # Verify budget exists
        await service.get_budget(session, budget_group_id=budget_id, household_id=household_id)
        override = await service.set_period_income(
            session,
            budget_group_id=budget_id,
            household_id=household_id,
            period_start=body.period_start,
            expected_income=body.expected_income,
            currency=body.currency,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()
    return PeriodIncomeOut.model_validate(override)
