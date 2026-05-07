"""FastAPI routes for the projections module.

Routes under /api/v1/households/{household_id}/projections/

  GET    /                              run or return cached base projection
  GET    /events                        list ProjectedEvents
  GET    /balance-curve                 per-account balance curve
  GET    /cashflow                      cashflow summary by period
  GET    /net-worth                     net worth curve
  GET    /breaches                      list ProjectionBreachEvents
  GET    /calendar-events               events formatted for calendar
  POST   /scenarios                     create scenario (saved or transient)
  GET    /scenarios                     list saved scenarios
  GET    /scenarios/{id}                get scenario + run results
  DELETE /scenarios/{id}                soft-delete scenario
  POST   /scenarios/{id}/run            (re)compute scenario
"""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.households.deps import CurrentUser
from app.projections import service
from app.projections.deps import HouseholdMember
from app.projections.schemas import (
    BalancePoint,
    CashflowPeriod,
    NetWorthPoint,
    ProjectedEventOut,
    ProjectionBreachEventOut,
    ProjectionResponse,
    ProjectionRunOut,
    RunProjectionRequest,
    ScenarioCreate,
    ScenarioOut,
    ScenarioUpdate,
)

router = APIRouter()

_base = "/households/{household_id}/projections"


# ---------------------------------------------------------------------------
# Base projection
# ---------------------------------------------------------------------------


@router.get(_base, response_model=ProjectionResponse)
async def get_projection(
    household_id: HouseholdMember,
    session: Annotated[AsyncSession, Depends(get_db)],
    horizon_months: Annotated[int, Query(ge=1, le=60)] = 12,
    as_of: Annotated[date | None, Query()] = None,
    force: Annotated[bool, Query()] = False,
) -> ProjectionResponse:
    """Run or return cached base projection."""
    as_of_date = as_of or date.today()
    try:
        result = await service.run_projection(
            session,
            household_id=household_id,
            as_of_date=as_of_date,
            horizon_months=horizon_months,
            scenario_id=None,
            force=force,
        )
    except service.ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    await session.commit()
    return ProjectionResponse(
        run=ProjectionRunOut.model_validate(result.run),
        events_count=len(result.events),
        breaches_count=len(result.breaches),
    )


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


@router.get(_base + "/events", response_model=list[ProjectedEventOut])
async def list_events(
    household_id: HouseholdMember,
    session: Annotated[AsyncSession, Depends(get_db)],
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
    account_id: Annotated[uuid.UUID | None, Query()] = None,
    event_type: Annotated[str | None, Query()] = None,
    scenario_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[ProjectedEventOut]:
    """List projected events with optional filters."""
    import sqlalchemy as sa

    from app.projections.models import ProjectedEvent

    run = await service.latest_run(session, household_id=household_id, scenario_id=scenario_id)
    if run is None:
        return []

    stmt = sa.select(ProjectedEvent).where(ProjectedEvent.run_id == run.id)
    if from_date:
        stmt = stmt.where(ProjectedEvent.event_date >= from_date)
    if to_date:
        stmt = stmt.where(ProjectedEvent.event_date <= to_date)
    if account_id:
        stmt = stmt.where(ProjectedEvent.account_id == account_id)
    if event_type:
        stmt = stmt.where(ProjectedEvent.event_type == event_type)
    stmt = stmt.order_by(ProjectedEvent.event_date)
    result = await session.execute(stmt)
    events = list(result.scalars().all())
    return [ProjectedEventOut.model_validate(e) for e in events]


# ---------------------------------------------------------------------------
# Balance curve
# ---------------------------------------------------------------------------


@router.get(_base + "/balance-curve", response_model=list[BalancePoint])
async def get_balance_curve(
    household_id: HouseholdMember,
    session: Annotated[AsyncSession, Depends(get_db)],
    accounts: Annotated[str | None, Query(description="Comma-separated UUIDs")] = None,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
    scenario_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[BalancePoint]:
    account_ids: list[uuid.UUID] = []
    if accounts:
        for s in accounts.split(","):
            s = s.strip()
            if s:
                try:
                    account_ids.append(uuid.UUID(s))
                except ValueError:
                    pass

    if not account_ids:
        import app.accounts.service as acct_svc

        accts = await acct_svc.list_accounts(session, household_id=household_id)
        account_ids = [a.id for a in accts]

    today = date.today()
    points = await service.get_balance_curve(
        session,
        household_id=household_id,
        account_ids=account_ids,
        from_date=from_date or today,
        to_date=to_date or today.replace(year=today.year + 1),
        scenario_id=scenario_id,
    )
    return [
        BalancePoint(
            event_date=p.event_date,
            account_id=p.account_id,
            balance=p.balance,
            currency=p.currency,
        )
        for p in points
    ]


# ---------------------------------------------------------------------------
# Cashflow summary
# ---------------------------------------------------------------------------


@router.get(_base + "/cashflow", response_model=list[CashflowPeriod])
async def get_cashflow(
    household_id: HouseholdMember,
    session: Annotated[AsyncSession, Depends(get_db)],
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
    period: Annotated[str, Query()] = "monthly",
    scenario_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[CashflowPeriod]:
    if period not in ("monthly", "weekly"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="period must be 'monthly' or 'weekly'",
        )
    today = date.today()
    cf = await service.get_cashflow_summary(
        session,
        household_id=household_id,
        from_date=from_date or today,
        to_date=to_date or today.replace(year=today.year + 1),
        period=period,
        scenario_id=scenario_id,
    )
    return [
        CashflowPeriod(
            period_start=p.period_start,
            period_end=p.period_end,
            total_income=p.total_income,
            total_expenses=p.total_expenses,
            net_cashflow=p.net_cashflow,
            currency=p.currency,
        )
        for p in cf
    ]


# ---------------------------------------------------------------------------
# Net worth curve
# ---------------------------------------------------------------------------


@router.get(_base + "/net-worth", response_model=list[NetWorthPoint])
async def get_net_worth(
    household_id: HouseholdMember,
    session: Annotated[AsyncSession, Depends(get_db)],
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
    scenario_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[NetWorthPoint]:
    today = date.today()
    points = await service.get_net_worth_curve(
        session,
        household_id=household_id,
        from_date=from_date or today,
        to_date=to_date or today.replace(year=today.year + 1),
        scenario_id=scenario_id,
    )
    return [
        NetWorthPoint(
            event_date=p.event_date,
            net_worth=p.net_worth,
            currency=p.currency,
        )
        for p in points
    ]


# ---------------------------------------------------------------------------
# Breach events
# ---------------------------------------------------------------------------


@router.get(_base + "/breaches", response_model=list[ProjectionBreachEventOut])
async def list_breaches(
    household_id: HouseholdMember,
    session: Annotated[AsyncSession, Depends(get_db)],
    scenario_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[ProjectionBreachEventOut]:
    run = await service.latest_run(session, household_id=household_id, scenario_id=scenario_id)
    if run is None:
        return []
    breaches = await service.load_run_breaches(session, run.id)
    return [ProjectionBreachEventOut.model_validate(b) for b in breaches]


# ---------------------------------------------------------------------------
# Calendar events
# ---------------------------------------------------------------------------


@router.get(_base + "/calendar-events", response_model=list[ProjectedEventOut])
async def get_calendar_events(
    household_id: HouseholdMember,
    session: Annotated[AsyncSession, Depends(get_db)],
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
    scenario_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[ProjectedEventOut]:
    today = date.today()
    events = await service.get_calendar_events(
        session,
        household_id=household_id,
        from_date=from_date or today,
        to_date=to_date or today.replace(year=today.year + 1),
        scenario_id=scenario_id,
    )
    return [ProjectedEventOut.model_validate(e) for e in events]


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


@router.post(
    _base + "/scenarios",
    response_model=ScenarioOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_scenario(
    household_id: HouseholdMember,
    body: ScenarioCreate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ScenarioOut:
    scenario = await service.create_scenario(
        session,
        household_id=household_id,
        actor_id=current_user.id,
        name=body.name,
        overrides=[o.model_dump(mode="json") for o in body.overrides],
        saved=body.saved,
    )
    await session.commit()
    return ScenarioOut.model_validate(scenario)


@router.get(_base + "/scenarios", response_model=list[ScenarioOut])
async def list_scenarios(
    household_id: HouseholdMember,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[ScenarioOut]:
    scenarios = await service.list_scenarios(session, household_id=household_id)
    return [ScenarioOut.model_validate(s) for s in scenarios]


@router.get(_base + "/scenarios/{scenario_id}", response_model=ScenarioOut)
async def get_scenario(
    household_id: HouseholdMember,
    scenario_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ScenarioOut:
    try:
        scenario = await service.get_scenario(
            session, scenario_id=scenario_id, household_id=household_id
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ScenarioOut.model_validate(scenario)


@router.patch(_base + "/scenarios/{scenario_id}", response_model=ScenarioOut)
async def update_scenario(
    household_id: HouseholdMember,
    scenario_id: uuid.UUID,
    body: ScenarioUpdate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ScenarioOut:
    try:
        scenario = await service.update_scenario(
            session,
            scenario_id=scenario_id,
            household_id=household_id,
            actor_id=current_user.id,
            name=body.name,
            saved=body.saved,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()
    return ScenarioOut.model_validate(scenario)


@router.delete(_base + "/scenarios/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_scenario(
    household_id: HouseholdMember,
    scenario_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    try:
        await service.archive_scenario(
            session,
            scenario_id=scenario_id,
            household_id=household_id,
            actor_id=current_user.id,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()


@router.post(_base + "/scenarios/{scenario_id}/run", response_model=ProjectionResponse)
async def run_scenario(
    household_id: HouseholdMember,
    scenario_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    body: RunProjectionRequest | None = None,
) -> ProjectionResponse:
    req = body or RunProjectionRequest()
    as_of_date = req.as_of or date.today()
    try:
        result = await service.run_scenario(
            session,
            scenario_id=scenario_id,
            household_id=household_id,
            as_of_date=as_of_date,
            horizon_months=req.horizon_months,
            force=req.force,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except service.ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    await session.commit()
    return ProjectionResponse(
        run=ProjectionRunOut.model_validate(result.run),
        events_count=len(result.events),
        breaches_count=len(result.breaches),
    )
