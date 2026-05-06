"""FastAPI routes for the recurrences module.

Routes under /api/v1/households/{household_id}/recurrences/

  GET    /                              list recurrences
  POST   /                              create declared recurrence
  GET    /{recurrence_id}               get recurrence
  PATCH  /{recurrence_id}               update recurrence
  DELETE /{recurrence_id}               archive recurrence
  POST   /{recurrence_id}/pause         pause missed-detection alerts
  POST   /{recurrence_id}/resume        resume missed-detection alerts
  POST   /{recurrence_id}/exceptions    add single-instance exception
  GET    /{recurrence_id}/matches       match history

  GET    /candidates                    list pending candidates
  POST   /candidates/{id}/confirm       confirm candidate (HITL)
  POST   /candidates/{id}/dismiss       dismiss candidate

  GET    /expected                      expected events in date window
"""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.households.deps import CurrentUser
from app.recurrences import service
from app.recurrences.deps import HouseholdMember
from app.recurrences.enums import Cadence, RecurrenceKind
from app.recurrences.schemas import (
    CandidateOut,
    ExceptionCreate,
    ExceptionOut,
    ExpectedEventOut,
    MatchOut,
    RecurrenceCreate,
    RecurrenceOut,
    RecurrenceUpdate,
)

router = APIRouter()

_base = "/households/{household_id}/recurrences"


# ---------------------------------------------------------------------------
# Recurrence CRUD
# ---------------------------------------------------------------------------


@router.get(_base, response_model=list[RecurrenceOut], tags=["recurrences"])
async def list_recurrences(
    household_id: HouseholdMember,
    session: Annotated[AsyncSession, Depends(get_db)],
    account_id: uuid.UUID | None = None,
) -> list[RecurrenceOut]:
    recs = await service.list_recurrences(session, household_id=household_id, account_id=account_id)
    return [RecurrenceOut.model_validate(r) for r in recs]


@router.post(
    _base,
    response_model=RecurrenceOut,
    status_code=status.HTTP_201_CREATED,
    tags=["recurrences"],
)
async def create_recurrence(
    household_id: HouseholdMember,
    body: RecurrenceCreate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RecurrenceOut:
    try:
        rec = await service.create_recurrence(
            session,
            household_id=household_id,
            actor_id=current_user.id,
            account_id=body.account_id,
            kind=RecurrenceKind.DECLARED,
            cadence=body.cadence,
            expected_amount=body.expected_amount,
            currency=body.currency,
            tolerance=body.tolerance,
            expected_day_of_period=body.expected_day_of_period,
            expected_amount_strategy=body.expected_amount_strategy,
            linked_category_id=body.linked_category_id,
            linked_account_id=body.linked_account_id,
            start_date=body.start_date,
            end_date=body.end_date,
            merchant_name=body.merchant_name,
            recurrence_metadata=body.recurrence_metadata,
        )
    except service.ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return RecurrenceOut.model_validate(rec)


@router.get(_base + "/{recurrence_id}", response_model=RecurrenceOut, tags=["recurrences"])
async def get_recurrence(
    household_id: HouseholdMember,
    recurrence_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RecurrenceOut:
    try:
        rec = await service.get_recurrence(
            session, recurrence_id=recurrence_id, household_id=household_id
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return RecurrenceOut.model_validate(rec)


@router.patch(_base + "/{recurrence_id}", response_model=RecurrenceOut, tags=["recurrences"])
async def update_recurrence(
    household_id: HouseholdMember,
    recurrence_id: uuid.UUID,
    body: RecurrenceUpdate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RecurrenceOut:
    try:
        rec = await service.update_recurrence(
            session,
            recurrence_id=recurrence_id,
            household_id=household_id,
            actor_id=current_user.id,
            cadence=body.cadence,
            expected_amount=body.expected_amount,
            currency=body.currency,
            tolerance=body.tolerance,
            expected_day_of_period=body.expected_day_of_period,
            expected_amount_strategy=body.expected_amount_strategy,
            linked_category_id=body.linked_category_id,
            linked_account_id=body.linked_account_id,
            end_date=body.end_date,
            merchant_name=body.merchant_name,
            recurrence_metadata=body.recurrence_metadata,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return RecurrenceOut.model_validate(rec)


@router.delete(
    _base + "/{recurrence_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["recurrences"],
)
async def archive_recurrence(
    household_id: HouseholdMember,
    recurrence_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    try:
        await service.archive_recurrence(
            session,
            recurrence_id=recurrence_id,
            household_id=household_id,
            actor_id=current_user.id,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    _base + "/{recurrence_id}/pause",
    response_model=RecurrenceOut,
    tags=["recurrences"],
)
async def pause_recurrence(
    household_id: HouseholdMember,
    recurrence_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RecurrenceOut:
    try:
        rec = await service.pause_recurrence(
            session,
            recurrence_id=recurrence_id,
            household_id=household_id,
            actor_id=current_user.id,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except service.ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return RecurrenceOut.model_validate(rec)


@router.post(
    _base + "/{recurrence_id}/resume",
    response_model=RecurrenceOut,
    tags=["recurrences"],
)
async def resume_recurrence(
    household_id: HouseholdMember,
    recurrence_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RecurrenceOut:
    try:
        rec = await service.resume_recurrence(
            session,
            recurrence_id=recurrence_id,
            household_id=household_id,
            actor_id=current_user.id,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except service.ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return RecurrenceOut.model_validate(rec)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


@router.post(
    _base + "/{recurrence_id}/exceptions",
    response_model=ExceptionOut,
    status_code=status.HTTP_201_CREATED,
    tags=["recurrences"],
)
async def add_exception(
    household_id: HouseholdMember,
    recurrence_id: uuid.UUID,
    body: ExceptionCreate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ExceptionOut:
    try:
        exc = await service.apply_exception(
            session,
            recurrence_id=recurrence_id,
            household_id=household_id,
            actor_id=current_user.id,
            exception_type=body.exception_type,
            affected_period=body.affected_period,
            override_amount=body.override_amount,
            override_date=body.override_date,
            note=body.note,
        )
    except service.NotFoundError as exc_err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc_err)) from exc_err
    except service.ValidationError as exc_err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc_err)
        ) from exc_err
    return ExceptionOut.model_validate(exc)


# ---------------------------------------------------------------------------
# Matches
# ---------------------------------------------------------------------------


@router.get(
    _base + "/{recurrence_id}/matches",
    response_model=list[MatchOut],
    tags=["recurrences"],
)
async def list_matches(
    household_id: HouseholdMember,
    recurrence_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[MatchOut]:
    try:
        matches = await service.list_matches(
            session, recurrence_id=recurrence_id, household_id=household_id
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [MatchOut.model_validate(m) for m in matches]


# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------

_cand_base = "/households/{household_id}/recurrences"


@router.get(
    _cand_base + "/candidates",
    response_model=list[CandidateOut],
    tags=["recurrences"],
)
async def list_candidates(
    household_id: HouseholdMember,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[CandidateOut]:
    candidates = await service.list_candidates(session, household_id=household_id)
    return [CandidateOut.model_validate(c) for c in candidates]


@router.post(
    _cand_base + "/candidates/{candidate_id}/confirm",
    response_model=RecurrenceOut,
    status_code=status.HTTP_201_CREATED,
    tags=["recurrences"],
)
async def confirm_candidate(
    household_id: HouseholdMember,
    candidate_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RecurrenceOut:
    try:
        rec = await service.confirm_candidate(
            session,
            candidate_id=candidate_id,
            household_id=household_id,
            actor_id=current_user.id,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except service.ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return RecurrenceOut.model_validate(rec)


@router.post(
    _cand_base + "/candidates/{candidate_id}/dismiss",
    response_model=CandidateOut,
    tags=["recurrences"],
)
async def dismiss_candidate(
    household_id: HouseholdMember,
    candidate_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CandidateOut:
    try:
        candidate = await service.dismiss_candidate(
            session,
            candidate_id=candidate_id,
            household_id=household_id,
            actor_id=current_user.id,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except service.ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return CandidateOut.model_validate(candidate)


# ---------------------------------------------------------------------------
# Expected events
# ---------------------------------------------------------------------------


@router.get(
    "/households/{household_id}/recurrences/expected",
    response_model=list[ExpectedEventOut],
    tags=["recurrences"],
)
async def get_expected_events(
    household_id: HouseholdMember,
    session: Annotated[AsyncSession, Depends(get_db)],
    from_date: Annotated[date, Query(alias="from")],
    to_date: Annotated[date, Query(alias="to")],
) -> list[ExpectedEventOut]:
    events = await service.get_expected_events(
        session,
        household_id=household_id,
        from_date=from_date,
        to_date=to_date,
    )
    return [
        ExpectedEventOut(
            recurrence_id=e.recurrence_id,
            account_id=e.account_id,
            expected_date=e.expected_date,
            expected_amount=e.expected_amount,
            currency=e.currency,
            cadence=Cadence(e.cadence),
            merchant_name=e.merchant_name,
            exception_type=e.exception_type,  # type: ignore[arg-type]
            override_amount=e.override_amount,
            override_date=e.override_date,
        )
        for e in events
    ]
