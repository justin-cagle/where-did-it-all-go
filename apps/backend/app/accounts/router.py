"""FastAPI routes for the accounts module.

All routes are scoped under /api/v1/households/{household_id}/accounts/.
Membership in the household is enforced by the HouseholdMember dependency.

Routes:
  Accounts:
    GET    /                               list accounts
    POST   /                               create account
    GET    /{account_id}                   get account
    PATCH  /{account_id}                   update account
    DELETE /{account_id}                   archive account

  AccountGroups (register /candidates before /{group_id} to avoid routing collision):
    GET    /groups/                        list groups
    POST   /groups/                        create group
    GET    /groups/candidates              detection heuristic for HITL
    GET    /groups/{group_id}              get group
    PATCH  /groups/{group_id}              update group
    DELETE /groups/{group_id}              archive group
    POST   /groups/{group_id}/members/{account_id}   add to group
    DELETE /groups/{group_id}/members/{account_id}   remove from group

  DebtAccount:
    GET    /{account_id}/debt              get annotation
    POST   /{account_id}/debt              create annotation
    PATCH  /{account_id}/debt              update annotation
    GET    /{account_id}/debt/balances     list APR history
    POST   /{account_id}/debt/balances     add APR tranche
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts import service
from app.accounts.deps import HouseholdMember
from app.accounts.enums import AccountType
from app.accounts.schemas import (
    AccountCreate,
    AccountGroupCreate,
    AccountGroupOut,
    AccountGroupUpdate,
    AccountOut,
    AccountUpdate,
    DebtAnnotationCreate,
    DebtAnnotationOut,
    DebtAnnotationUpdate,
    DebtBalanceCreate,
    DebtBalanceOut,
    GroupCandidateOut,
)
from app.database import get_db
from app.households.deps import CurrentUser

router = APIRouter(tags=["accounts"])

_DbSession = Annotated[AsyncSession, Depends(get_db)]


# ---------------------------------------------------------------------------
# Account routes
# ---------------------------------------------------------------------------


@router.get(
    "/households/{household_id}/accounts/",
    response_model=list[AccountOut],
)
async def list_accounts(
    household_id: HouseholdMember,
    session: _DbSession,
    account_type: AccountType | None = None,
    is_manual: bool | None = None,
) -> list[AccountOut]:
    """List accounts in the household, optionally filtered by type or manual flag."""
    accounts = await service.list_accounts(
        session,
        household_id=household_id,
        account_type=account_type,
        is_manual=is_manual,
    )
    return [AccountOut.model_validate(a) for a in accounts]


@router.post(
    "/households/{household_id}/accounts/",
    response_model=AccountOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_account(
    household_id: HouseholdMember,
    body: AccountCreate,
    current_user: CurrentUser,
    session: _DbSession,
) -> AccountOut:
    """Create a new account."""
    account = await service.create_account(
        session,
        household_id=household_id,
        actor_id=current_user.id,
        name=body.name,
        institution=body.institution,
        account_type=body.account_type,
        currency=body.currency,
        current_balance=body.current_balance,
    )
    return AccountOut.model_validate(account)


@router.get(
    "/households/{household_id}/accounts/{account_id}",
    response_model=AccountOut,
)
async def get_account(
    household_id: HouseholdMember,
    account_id: uuid.UUID,
    session: _DbSession,
) -> AccountOut:
    """Return account details."""
    try:
        account = await service.get_account(
            session, account_id=account_id, household_id=household_id
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return AccountOut.model_validate(account)


@router.patch(
    "/households/{household_id}/accounts/{account_id}",
    response_model=AccountOut,
)
async def update_account(
    household_id: HouseholdMember,
    account_id: uuid.UUID,
    body: AccountUpdate,
    current_user: CurrentUser,
    session: _DbSession,
) -> AccountOut:
    """Update account name or balance."""
    try:
        account = await service.update_account(
            session,
            account_id=account_id,
            household_id=household_id,
            actor_id=current_user.id,
            name=body.name,
            current_balance=body.current_balance,
            allow_negative_balance=body.allow_negative_balance,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except service.ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return AccountOut.model_validate(account)


@router.delete(
    "/households/{household_id}/accounts/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def archive_account(
    household_id: HouseholdMember,
    account_id: uuid.UUID,
    current_user: CurrentUser,
    session: _DbSession,
) -> None:
    """Soft-delete (archive) an account."""
    try:
        await service.archive_account(
            session,
            account_id=account_id,
            household_id=household_id,
            actor_id=current_user.id,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# AccountGroup routes — /candidates registered before /{group_id}
# ---------------------------------------------------------------------------


@router.get(
    "/households/{household_id}/accounts/groups/",
    response_model=list[AccountGroupOut],
)
async def list_account_groups(
    household_id: HouseholdMember,
    session: _DbSession,
) -> list[AccountGroupOut]:
    """List all account groups in the household."""
    groups = await service.list_account_groups(session, household_id=household_id)
    return [AccountGroupOut.model_validate(g) for g in groups]


@router.post(
    "/households/{household_id}/accounts/groups/",
    response_model=AccountGroupOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_account_group(
    household_id: HouseholdMember,
    body: AccountGroupCreate,
    current_user: CurrentUser,
    session: _DbSession,
) -> AccountGroupOut:
    """Create an account group, optionally linking initial member accounts."""
    try:
        group = await service.create_account_group(
            session,
            household_id=household_id,
            actor_id=current_user.id,
            name=body.name,
            primary_holder_id=body.primary_holder_id,
            authorized_user_ids=body.authorized_user_ids,
            member_account_ids=body.member_account_ids,
        )
    except (service.NotFoundError, service.ConflictError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return AccountGroupOut.model_validate(group)


@router.get(
    "/households/{household_id}/accounts/groups/candidates",
    response_model=list[GroupCandidateOut],
)
async def find_group_candidates(
    household_id: HouseholdMember,
    session: _DbSession,
) -> list[GroupCandidateOut]:
    """Return candidate account pairs for HITL grouping review.

    Detection heuristic: same institution + same balance + same currency +
    name similarity ≥ 60%. Does NOT auto-merge; confirmation is a separate write.
    """
    candidates = await service.find_group_candidates(session, household_id=household_id)
    return [
        GroupCandidateOut(
            account_a_id=c.account_a.id,
            account_b_id=c.account_b.id,
            reason=c.reason,
            similarity_score=c.similarity_score,
        )
        for c in candidates
    ]


@router.get(
    "/households/{household_id}/accounts/groups/{group_id}",
    response_model=AccountGroupOut,
)
async def get_account_group(
    household_id: HouseholdMember,
    group_id: uuid.UUID,
    session: _DbSession,
) -> AccountGroupOut:
    """Return account group details."""
    try:
        group = await service.get_account_group(
            session, group_id=group_id, household_id=household_id
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return AccountGroupOut.model_validate(group)


@router.patch(
    "/households/{household_id}/accounts/groups/{group_id}",
    response_model=AccountGroupOut,
)
async def update_account_group(
    household_id: HouseholdMember,
    group_id: uuid.UUID,
    body: AccountGroupUpdate,
    current_user: CurrentUser,
    session: _DbSession,
) -> AccountGroupOut:
    """Update account group name or membership metadata."""
    try:
        group = await service.update_account_group(
            session,
            group_id=group_id,
            household_id=household_id,
            actor_id=current_user.id,
            name=body.name,
            primary_holder_id=body.primary_holder_id,
            authorized_user_ids=body.authorized_user_ids,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return AccountGroupOut.model_validate(group)


@router.delete(
    "/households/{household_id}/accounts/groups/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def archive_account_group(
    household_id: HouseholdMember,
    group_id: uuid.UUID,
    current_user: CurrentUser,
    session: _DbSession,
) -> None:
    """Soft-delete (archive) an account group."""
    try:
        await service.archive_account_group(
            session,
            group_id=group_id,
            household_id=household_id,
            actor_id=current_user.id,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/households/{household_id}/accounts/groups/{group_id}/members/{account_id}",
    response_model=AccountOut,
    status_code=status.HTTP_200_OK,
)
async def add_account_to_group(
    household_id: HouseholdMember,
    group_id: uuid.UUID,
    account_id: uuid.UUID,
    current_user: CurrentUser,
    session: _DbSession,
) -> AccountOut:
    """Link an account to a group (HITL confirmation of a detected candidate)."""
    try:
        account = await service.add_account_to_group(
            session,
            group_id=group_id,
            account_id=account_id,
            household_id=household_id,
            actor_id=current_user.id,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except service.ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return AccountOut.model_validate(account)


@router.delete(
    "/households/{household_id}/accounts/groups/{group_id}/members/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_account_from_group(
    household_id: HouseholdMember,
    group_id: uuid.UUID,
    account_id: uuid.UUID,
    current_user: CurrentUser,
    session: _DbSession,
) -> None:
    """Remove an account from a group."""
    try:
        await service.remove_account_from_group(
            session,
            group_id=group_id,
            account_id=account_id,
            household_id=household_id,
            actor_id=current_user.id,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# DebtAccount routes
# ---------------------------------------------------------------------------


@router.get(
    "/households/{household_id}/accounts/{account_id}/debt",
    response_model=DebtAnnotationOut,
)
async def get_debt_annotation(
    household_id: HouseholdMember,
    account_id: uuid.UUID,
    session: _DbSession,
) -> DebtAnnotationOut:
    """Return the debt annotation for an account."""
    try:
        da = await service.get_debt_annotation(
            session, account_id=account_id, household_id=household_id
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return DebtAnnotationOut.model_validate(da)


@router.post(
    "/households/{household_id}/accounts/{account_id}/debt",
    response_model=DebtAnnotationOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_debt_annotation(
    household_id: HouseholdMember,
    account_id: uuid.UUID,
    body: DebtAnnotationCreate,
    current_user: CurrentUser,
    session: _DbSession,
) -> DebtAnnotationOut:
    """Annotate a debt account with payment strategy and initial APR tranche."""
    try:
        da, _ = await service.create_debt_annotation(
            session,
            account_id=account_id,
            household_id=household_id,
            actor_id=current_user.id,
            minimum_payment_strategy=body.minimum_payment_strategy,
            statement_day=body.statement_day,
            due_day=body.due_day,
            payoff_target_date=body.payoff_target_date,
            initial_balance=body.initial_balance,
            initial_apr=body.initial_apr,
            currency=body.currency,
            term=body.term,
            promotional_period_end=body.promotional_period_end,
            effective_from=body.effective_from,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except service.ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except service.ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return DebtAnnotationOut.model_validate(da)


@router.patch(
    "/households/{household_id}/accounts/{account_id}/debt",
    response_model=DebtAnnotationOut,
)
async def update_debt_annotation(
    household_id: HouseholdMember,
    account_id: uuid.UUID,
    body: DebtAnnotationUpdate,
    current_user: CurrentUser,
    session: _DbSession,
) -> DebtAnnotationOut:
    """Update debt account payment strategy and scheduling fields."""
    try:
        da = await service.update_debt_annotation(
            session,
            account_id=account_id,
            household_id=household_id,
            actor_id=current_user.id,
            minimum_payment_strategy=body.minimum_payment_strategy,
            statement_day=body.statement_day,
            due_day=body.due_day,
            payoff_target_date=body.payoff_target_date,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return DebtAnnotationOut.model_validate(da)


@router.get(
    "/households/{household_id}/accounts/{account_id}/debt/balances",
    response_model=list[DebtBalanceOut],
)
async def list_debt_balances(
    household_id: HouseholdMember,
    account_id: uuid.UUID,
    session: _DbSession,
) -> list[DebtBalanceOut]:
    """Return full APR history for a debt account, ordered by effective_from."""
    try:
        balances = await service.list_debt_balances(
            session, account_id=account_id, household_id=household_id
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [DebtBalanceOut.model_validate(b) for b in balances]


@router.post(
    "/households/{household_id}/accounts/{account_id}/debt/balances",
    response_model=DebtBalanceOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_debt_balance(
    household_id: HouseholdMember,
    account_id: uuid.UUID,
    body: DebtBalanceCreate,
    current_user: CurrentUser,
    session: _DbSession,
) -> DebtBalanceOut:
    """Add a new APR tranche, closing the current one in the effective-dated chain."""
    try:
        balance = await service.add_debt_balance(
            session,
            account_id=account_id,
            household_id=household_id,
            actor_id=current_user.id,
            principal_balance=body.principal_balance,
            currency=body.currency,
            apr=body.apr,
            term=body.term,
            promotional_period_end=body.promotional_period_end,
            effective_from=body.effective_from,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except service.ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return DebtBalanceOut.model_validate(balance)
