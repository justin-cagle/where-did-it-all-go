"""FastAPI routes for the transactions module.

Routes:
  Per-account (/households/{hid}/accounts/{aid}/transactions/):
    GET    /                                     list transactions
    POST   /                                     create transaction
    GET    /{transaction_id}                     get detail (includes splits)
    PATCH  /{transaction_id}/state               transition state
    DELETE /{transaction_id}                     archive
    POST   /{transaction_id}/splits              set splits
    POST   /{transaction_id}/transfer-pair       link transfer peer
    POST   /{transaction_id}/refund-pair         link refund peer
    GET    /{transaction_id}/refund-candidates   surface refund candidates

  Cross-account (/households/{hid}/transactions/):
    GET    /                                     list all household transactions
    GET    /dedup-candidates                     pending dedup log rows (registered before /{tid})
    POST   /dedup-candidates/{log_id}/resolve    resolve a dedup candidate
    GET    /{transaction_id}                     get detail (includes splits)
    PATCH  /{transaction_id}/state               transition state
    DELETE /{transaction_id}                     archive
    POST   /{transaction_id}/splits              set splits
    POST   /{transaction_id}/transfer-pair       link transfer peer
    POST   /{transaction_id}/refund-pair         link refund peer

  PaymentGroups (/households/{hid}/payment-groups/):
    GET    /                                     list payment groups
    POST   /                                     create payment group
    GET    /{group_id}                           get payment group
    DELETE /{group_id}                           archive payment group
"""

import uuid
from collections.abc import Sequence
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.households.deps import CurrentUser
from app.transactions import service
from app.transactions.deps import AccountInHousehold, HouseholdMember
from app.transactions.enums import (
    DedupResolution,
    TransactionDirection,
    TransactionState,
    TransactionType,
)
from app.transactions.schemas import (
    DeduplicationLogOut,
    DedupResolveRequest,
    PaymentGroupCreate,
    PaymentGroupOut,
    RefundCandidateOut,
    RefundPairRequest,
    SplitAllocationOut,
    SplitsSetRequest,
    TransactionCreate,
    TransactionDetailOut,
    TransactionOut,
    TransactionStateUpdate,
    TransferPairRequest,
)

router = APIRouter(tags=["transactions"])

_DbSession = Annotated[AsyncSession, Depends(get_db)]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _tx_out(tx: object) -> TransactionOut:
    return TransactionOut.model_validate(tx)


def _tx_detail(tx: object, splits: Sequence[object]) -> TransactionDetailOut:
    return TransactionDetailOut(
        **TransactionOut.model_validate(tx).model_dump(),
        splits=[SplitAllocationOut.model_validate(s) for s in splits],
    )


# ===========================================================================
# Per-account routes
# ===========================================================================


@router.get(
    "/households/{household_id}/accounts/{account_id}/transactions/",
    response_model=list[TransactionOut],
)
async def list_transactions_for_account(
    household_id: HouseholdMember,
    account_id: AccountInHousehold,
    session: _DbSession,
    state: TransactionState | None = None,
    direction: TransactionDirection | None = None,
    transaction_type: TransactionType | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[TransactionOut]:
    """List transactions for a specific account."""
    txs = await service.list_transactions(
        session,
        household_id=household_id,
        account_id=account_id,
        state=state,
        direction=direction,
        transaction_type=transaction_type,
        date_from=date_from,
        date_to=date_to,
    )
    return [_tx_out(t) for t in txs]


@router.post(
    "/households/{household_id}/accounts/{account_id}/transactions/",
    response_model=TransactionDetailOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_transaction(
    household_id: HouseholdMember,
    account_id: AccountInHousehold,
    body: TransactionCreate,
    current_user: CurrentUser,
    session: _DbSession,
) -> TransactionDetailOut:
    """Create a transaction via manual entry."""
    try:
        tx = await service.create_transaction(
            session,
            household_id=household_id,
            account_id=account_id,
            actor_id=current_user.id,
            amount=body.amount,
            currency=body.currency,
            direction=body.direction,
            transaction_type=body.transaction_type,
            state=body.state,
            posted_date=body.posted_date,
            pending_date=body.pending_date,
            occurred_at=body.occurred_at,
            description=body.description,
            merchant_name=body.merchant_name,
            external_id=body.external_id,
            manually_categorized=body.manually_categorized,
        )
    except service.ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    splits = await service.get_splits(session, transaction_id=tx.id, household_id=household_id)
    return _tx_detail(tx, splits)


@router.get(
    "/households/{household_id}/accounts/{account_id}/transactions/{transaction_id}",
    response_model=TransactionDetailOut,
)
async def get_transaction_for_account(
    household_id: HouseholdMember,
    account_id: AccountInHousehold,
    transaction_id: uuid.UUID,
    session: _DbSession,
) -> TransactionDetailOut:
    """Return transaction detail with splits."""
    try:
        tx = await service.get_transaction(
            session,
            transaction_id=transaction_id,
            household_id=household_id,
            account_id=account_id,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    splits = await service.get_splits(session, transaction_id=tx.id, household_id=household_id)
    return _tx_detail(tx, splits)


@router.patch(
    "/households/{household_id}/accounts/{account_id}/transactions/{transaction_id}/state",
    response_model=TransactionOut,
)
async def transition_state_for_account(
    household_id: HouseholdMember,
    account_id: AccountInHousehold,
    transaction_id: uuid.UUID,
    body: TransactionStateUpdate,
    current_user: CurrentUser,
    session: _DbSession,
) -> TransactionOut:
    """Advance the transaction state machine."""
    try:
        tx = await service.transition_state(
            session,
            transaction_id=transaction_id,
            household_id=household_id,
            actor_id=current_user.id,
            new_state=body.state,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except service.InvalidTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return _tx_out(tx)


@router.delete(
    "/households/{household_id}/accounts/{account_id}/transactions/{transaction_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def archive_transaction_for_account(
    household_id: HouseholdMember,
    account_id: AccountInHousehold,
    transaction_id: uuid.UUID,
    current_user: CurrentUser,
    session: _DbSession,
) -> None:
    """Soft-delete (archive) a transaction."""
    try:
        await service.archive_transaction(
            session,
            transaction_id=transaction_id,
            household_id=household_id,
            actor_id=current_user.id,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/households/{household_id}/accounts/{account_id}/transactions/{transaction_id}/splits",
    response_model=list[SplitAllocationOut],
)
async def set_splits_for_account(
    household_id: HouseholdMember,
    account_id: AccountInHousehold,
    transaction_id: uuid.UUID,
    body: SplitsSetRequest,
    current_user: CurrentUser,
    session: _DbSession,
) -> list[SplitAllocationOut]:
    """Replace all splits on a transaction."""
    try:
        splits = await service.set_splits(
            session,
            transaction_id=transaction_id,
            household_id=household_id,
            actor_id=current_user.id,
            splits=[s.model_dump() for s in body.splits],
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except service.ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return [SplitAllocationOut.model_validate(s) for s in splits]


@router.post(
    "/households/{household_id}/accounts/{account_id}/transactions/{transaction_id}/transfer-pair",
    response_model=list[TransactionOut],
)
async def pair_transfer_for_account(
    household_id: HouseholdMember,
    account_id: AccountInHousehold,
    transaction_id: uuid.UUID,
    body: TransferPairRequest,
    current_user: CurrentUser,
    session: _DbSession,
) -> list[TransactionOut]:
    """Link two transactions as an internal or external transfer."""
    try:
        tx, peer = await service.pair_transfer(
            session,
            transaction_id=transaction_id,
            peer_id=body.peer_id,
            household_id=household_id,
            actor_id=current_user.id,
            transfer_type=body.transfer_type,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (service.ValidationError, service.ConflictError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return [_tx_out(tx), _tx_out(peer)]


@router.get(
    "/households/{household_id}/accounts/{account_id}/transactions/{transaction_id}/refund-candidates",
    response_model=list[RefundCandidateOut],
)
async def get_refund_candidates(
    household_id: HouseholdMember,
    account_id: AccountInHousehold,
    transaction_id: uuid.UUID,
    session: _DbSession,
    window_days: int = 30,
) -> list[RefundCandidateOut]:
    """Return credit transactions that could be refunds of this debit."""
    try:
        candidates = await service.find_refund_candidates(
            session,
            transaction_id=transaction_id,
            household_id=household_id,
            window_days=window_days,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except service.ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return [
        RefundCandidateOut(
            transaction=_tx_out(c.transaction),
            days_apart=c.days_apart,
        )
        for c in candidates
    ]


@router.post(
    "/households/{household_id}/accounts/{account_id}/transactions/{transaction_id}/refund-pair",
    response_model=list[TransactionOut],
)
async def pair_refund_for_account(
    household_id: HouseholdMember,
    account_id: AccountInHousehold,
    transaction_id: uuid.UUID,
    body: RefundPairRequest,
    current_user: CurrentUser,
    session: _DbSession,
) -> list[TransactionOut]:
    """Confirm a refund pairing (HITL write)."""
    try:
        debit, credit = await service.pair_refund(
            session,
            transaction_id=transaction_id,
            peer_id=body.peer_id,
            household_id=household_id,
            actor_id=current_user.id,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (service.ValidationError, service.ConflictError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return [_tx_out(debit), _tx_out(credit)]


# ===========================================================================
# Cross-account routes — /households/{hid}/transactions/
# NOTE: static paths (dedup-candidates) registered BEFORE {transaction_id}
# ===========================================================================


@router.get(
    "/households/{household_id}/transactions/",
    response_model=list[TransactionOut],
)
async def list_transactions_cross_account(
    household_id: HouseholdMember,
    session: _DbSession,
    state: TransactionState | None = None,
    direction: TransactionDirection | None = None,
    transaction_type: TransactionType | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    import_job_id: uuid.UUID | None = None,
) -> list[TransactionOut]:
    """List all transactions in the household (cross-account)."""
    txs = await service.list_transactions(
        session,
        household_id=household_id,
        state=state,
        direction=direction,
        transaction_type=transaction_type,
        date_from=date_from,
        date_to=date_to,
        import_job_id=import_job_id,
    )
    return [_tx_out(t) for t in txs]


@router.get(
    "/households/{household_id}/transactions/dedup-candidates",
    response_model=list[DeduplicationLogOut],
)
async def list_dedup_candidates(
    household_id: HouseholdMember,
    session: _DbSession,
) -> list[DeduplicationLogOut]:
    """Return pending dedup candidate pairs for HITL review."""
    logs = await service.list_dedup_candidates(session, household_id=household_id)
    return [DeduplicationLogOut.model_validate(lg) for lg in logs]


@router.post(
    "/households/{household_id}/transactions/dedup-candidates/{log_id}/resolve",
    response_model=DeduplicationLogOut,
)
async def resolve_dedup_candidate(
    household_id: HouseholdMember,
    log_id: uuid.UUID,
    body: DedupResolveRequest,
    current_user: CurrentUser,
    session: _DbSession,
) -> DeduplicationLogOut:
    """Accept a merge or reject a dedup candidate pair."""
    try:
        log = await service.resolve_dedup(
            session,
            log_id=log_id,
            household_id=household_id,
            actor_id=current_user.id,
            resolution=DedupResolution(body.resolution),
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except service.ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return DeduplicationLogOut.model_validate(log)


@router.get(
    "/households/{household_id}/transactions/{transaction_id}",
    response_model=TransactionDetailOut,
)
async def get_transaction_cross_account(
    household_id: HouseholdMember,
    transaction_id: uuid.UUID,
    session: _DbSession,
) -> TransactionDetailOut:
    """Return transaction detail with splits (cross-account)."""
    try:
        tx = await service.get_transaction(
            session, transaction_id=transaction_id, household_id=household_id
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    splits = await service.get_splits(session, transaction_id=tx.id, household_id=household_id)
    return _tx_detail(tx, splits)


@router.patch(
    "/households/{household_id}/transactions/{transaction_id}/state",
    response_model=TransactionOut,
)
async def transition_state_cross_account(
    household_id: HouseholdMember,
    transaction_id: uuid.UUID,
    body: TransactionStateUpdate,
    current_user: CurrentUser,
    session: _DbSession,
) -> TransactionOut:
    """Advance the transaction state machine (cross-account)."""
    try:
        tx = await service.transition_state(
            session,
            transaction_id=transaction_id,
            household_id=household_id,
            actor_id=current_user.id,
            new_state=body.state,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except service.InvalidTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return _tx_out(tx)


@router.delete(
    "/households/{household_id}/transactions/{transaction_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def archive_transaction_cross_account(
    household_id: HouseholdMember,
    transaction_id: uuid.UUID,
    current_user: CurrentUser,
    session: _DbSession,
) -> None:
    """Soft-delete a transaction (cross-account)."""
    try:
        await service.archive_transaction(
            session,
            transaction_id=transaction_id,
            household_id=household_id,
            actor_id=current_user.id,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/households/{household_id}/transactions/{transaction_id}/splits",
    response_model=list[SplitAllocationOut],
)
async def set_splits_cross_account(
    household_id: HouseholdMember,
    transaction_id: uuid.UUID,
    body: SplitsSetRequest,
    current_user: CurrentUser,
    session: _DbSession,
) -> list[SplitAllocationOut]:
    """Replace all splits on a transaction (cross-account)."""
    try:
        splits = await service.set_splits(
            session,
            transaction_id=transaction_id,
            household_id=household_id,
            actor_id=current_user.id,
            splits=[s.model_dump() for s in body.splits],
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except service.ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return [SplitAllocationOut.model_validate(s) for s in splits]


@router.post(
    "/households/{household_id}/transactions/{transaction_id}/transfer-pair",
    response_model=list[TransactionOut],
)
async def pair_transfer_cross_account(
    household_id: HouseholdMember,
    transaction_id: uuid.UUID,
    body: TransferPairRequest,
    current_user: CurrentUser,
    session: _DbSession,
) -> list[TransactionOut]:
    """Link two transactions as an internal or external transfer (cross-account)."""
    try:
        tx, peer = await service.pair_transfer(
            session,
            transaction_id=transaction_id,
            peer_id=body.peer_id,
            household_id=household_id,
            actor_id=current_user.id,
            transfer_type=body.transfer_type,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (service.ValidationError, service.ConflictError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return [_tx_out(tx), _tx_out(peer)]


@router.post(
    "/households/{household_id}/transactions/{transaction_id}/refund-pair",
    response_model=list[TransactionOut],
)
async def pair_refund_cross_account(
    household_id: HouseholdMember,
    transaction_id: uuid.UUID,
    body: RefundPairRequest,
    current_user: CurrentUser,
    session: _DbSession,
) -> list[TransactionOut]:
    """Confirm a refund pairing (cross-account)."""
    try:
        debit, credit = await service.pair_refund(
            session,
            transaction_id=transaction_id,
            peer_id=body.peer_id,
            household_id=household_id,
            actor_id=current_user.id,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (service.ValidationError, service.ConflictError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return [_tx_out(debit), _tx_out(credit)]


# ===========================================================================
# PaymentGroup routes
# ===========================================================================


@router.get(
    "/households/{household_id}/payment-groups/",
    response_model=list[PaymentGroupOut],
)
async def list_payment_groups(
    household_id: HouseholdMember,
    session: _DbSession,
) -> list[PaymentGroupOut]:
    """List all payment groups in the household."""
    groups = await service.list_payment_groups(session, household_id=household_id)
    return [PaymentGroupOut.model_validate(g) for g in groups]


@router.post(
    "/households/{household_id}/payment-groups/",
    response_model=PaymentGroupOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_payment_group(
    household_id: HouseholdMember,
    body: PaymentGroupCreate,
    current_user: CurrentUser,
    session: _DbSession,
) -> PaymentGroupOut:
    """Create a payment group from confirmed candidate transactions."""
    try:
        group = await service.create_payment_group(
            session,
            household_id=household_id,
            actor_id=current_user.id,
            group_type=body.group_type,
            member_transaction_ids=body.member_transaction_ids,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except service.ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return PaymentGroupOut.model_validate(group)


@router.get(
    "/households/{household_id}/payment-groups/{group_id}",
    response_model=PaymentGroupOut,
)
async def get_payment_group(
    household_id: HouseholdMember,
    group_id: uuid.UUID,
    session: _DbSession,
) -> PaymentGroupOut:
    """Return payment group details."""
    try:
        group = await service.get_payment_group(
            session, group_id=group_id, household_id=household_id
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return PaymentGroupOut.model_validate(group)


@router.delete(
    "/households/{household_id}/payment-groups/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def archive_payment_group(
    household_id: HouseholdMember,
    group_id: uuid.UUID,
    current_user: CurrentUser,
    session: _DbSession,
) -> None:
    """Soft-delete (archive) a payment group."""
    try:
        await service.archive_payment_group(
            session,
            group_id=group_id,
            household_id=household_id,
            actor_id=current_user.id,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
