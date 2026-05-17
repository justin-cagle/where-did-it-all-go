"""FastAPI routes for the classification module.

Routes:
  /households/{hid}/categories/
    GET    /                        list categories (system + household-scoped)
    POST   /                        create category
    GET    /{category_id}           get category
    PATCH  /{category_id}           update category
    DELETE /{category_id}           archive category

  /households/{hid}/tags/
    GET    /                        list tags
    POST   /                        create tag
    GET    /{tag_id}                get tag
    PATCH  /{tag_id}                update tag
    DELETE /{tag_id}                archive tag

  /households/{hid}/rules/
    GET    /                        list rules (priority order)
    POST   /                        create rule
    GET    /{rule_id}               get rule
    PATCH  /{rule_id}               update rule
    DELETE /{rule_id}               archive rule
    POST   /reorder                 bulk priority reorder
    POST   /{rule_id}/test          dry-run rule (no writes)

  /households/{hid}/income-sources/
    GET    /                        list income sources
    POST   /                        create income source
    GET    /{source_id}             get income source
    PATCH  /{source_id}             update income source
    DELETE /{source_id}             archive income source

  /households/{hid}/classification-settings
    GET    /                        get settings
    PATCH  /                        update strictness

  /households/{hid}/transactions/{transaction_id}/reclassify
    POST   /                        re-run pipeline on one transaction

  /households/{hid}/reclassify-all
    POST   /                        enqueue bulk reclassification job
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.classification import service
from app.classification.deps import HouseholdMember
from app.classification.schemas import (
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    ClassificationResultOut,
    HouseholdSettingsOut,
    HouseholdSettingsUpdate,
    IncomeSourceCreate,
    IncomeSourceOut,
    IncomeSourceUpdate,
    ReclassifyAllOut,
    RuleCreate,
    RuleOut,
    RulePriorityReorderRequest,
    RuleTestResult,
    RuleUpdate,
    TagCreate,
    TagOut,
    TagUpdate,
    TransactionSummary,
)
from app.config import get_settings
from app.database import get_db
from app.households.deps import CurrentUser

router = APIRouter()

# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

_cat_prefix = "/households/{household_id}/categories"


@router.get(_cat_prefix, response_model=list[CategoryOut], tags=["classification"])
async def list_categories(
    household_id: HouseholdMember,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[CategoryOut]:
    cats = await service.list_categories(session, household_id=household_id)
    return [CategoryOut.model_validate(c) for c in cats]


@router.post(
    _cat_prefix,
    response_model=CategoryOut,
    status_code=status.HTTP_201_CREATED,
    tags=["classification"],
)
async def create_category(
    household_id: HouseholdMember,
    body: CategoryCreate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CategoryOut:
    try:
        cat = await service.create_category(
            session,
            household_id=household_id,
            actor_id=current_user.id,
            name=body.name,
            parent_id=body.parent_id,
            color=body.color,
            sort_order=body.sort_order,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except service.ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return CategoryOut.model_validate(cat)


@router.get(_cat_prefix + "/{category_id}", response_model=CategoryOut, tags=["classification"])
async def get_category(
    household_id: HouseholdMember,
    category_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CategoryOut:
    try:
        cat = await service.get_category(
            session, category_id=category_id, household_id=household_id
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return CategoryOut.model_validate(cat)


@router.patch(_cat_prefix + "/{category_id}", response_model=CategoryOut, tags=["classification"])
async def update_category(
    household_id: HouseholdMember,
    category_id: uuid.UUID,
    body: CategoryUpdate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CategoryOut:
    try:
        cat = await service.update_category(
            session,
            category_id=category_id,
            household_id=household_id,
            actor_id=current_user.id,
            name=body.name,
            parent_id=body.parent_id,
            color=body.color,
            sort_order=body.sort_order,
            budget_role=body.budget_role,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (service.ValidationError, service.PermissionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return CategoryOut.model_validate(cat)


@router.delete(
    _cat_prefix + "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["classification"],
)
async def archive_category(
    household_id: HouseholdMember,
    category_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    try:
        await service.archive_category(
            session,
            category_id=category_id,
            household_id=household_id,
            actor_id=current_user.id,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except service.PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

_tag_prefix = "/households/{household_id}/tags"


@router.get(_tag_prefix, response_model=list[TagOut], tags=["classification"])
async def list_tags(
    household_id: HouseholdMember,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[TagOut]:
    tags = await service.list_tags(session, household_id=household_id)
    return [TagOut.model_validate(t) for t in tags]


@router.post(
    _tag_prefix,
    response_model=TagOut,
    status_code=status.HTTP_201_CREATED,
    tags=["classification"],
)
async def create_tag(
    household_id: HouseholdMember,
    body: TagCreate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TagOut:
    tag = await service.create_tag(
        session,
        household_id=household_id,
        actor_id=current_user.id,
        name=body.name,
        color=body.color,
    )
    return TagOut.model_validate(tag)


@router.get(_tag_prefix + "/{tag_id}", response_model=TagOut, tags=["classification"])
async def get_tag(
    household_id: HouseholdMember,
    tag_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TagOut:
    try:
        tag = await service.get_tag(session, tag_id=tag_id, household_id=household_id)
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return TagOut.model_validate(tag)


@router.patch(_tag_prefix + "/{tag_id}", response_model=TagOut, tags=["classification"])
async def update_tag(
    household_id: HouseholdMember,
    tag_id: uuid.UUID,
    body: TagUpdate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TagOut:
    try:
        tag = await service.update_tag(
            session,
            tag_id=tag_id,
            household_id=household_id,
            actor_id=current_user.id,
            name=body.name,
            color=body.color,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return TagOut.model_validate(tag)


@router.delete(
    _tag_prefix + "/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["classification"],
)
async def archive_tag(
    household_id: HouseholdMember,
    tag_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    try:
        await service.archive_tag(
            session,
            tag_id=tag_id,
            household_id=household_id,
            actor_id=current_user.id,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

_rule_prefix = "/households/{household_id}/rules"


@router.get(_rule_prefix, response_model=list[RuleOut], tags=["classification"])
async def list_rules(
    household_id: HouseholdMember,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[RuleOut]:
    rules = await service.list_rules(session, household_id=household_id)
    return [RuleOut.model_validate(r) for r in rules]


@router.post(
    _rule_prefix,
    response_model=RuleOut,
    status_code=status.HTTP_201_CREATED,
    tags=["classification"],
)
async def create_rule(
    household_id: HouseholdMember,
    body: RuleCreate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RuleOut:
    rule = await service.create_rule(
        session,
        household_id=household_id,
        actor_id=current_user.id,
        name=body.name,
        priority=body.priority,
        conditions=[c.model_dump() for c in body.conditions],
        actions=[a.model_dump() for a in body.actions],
        mode=str(body.mode),
        enabled=body.enabled,
    )
    return RuleOut.model_validate(rule)


@router.get(_rule_prefix + "/{rule_id}", response_model=RuleOut, tags=["classification"])
async def get_rule(
    household_id: HouseholdMember,
    rule_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RuleOut:
    try:
        rule = await service.get_rule(session, rule_id=rule_id, household_id=household_id)
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return RuleOut.model_validate(rule)


@router.patch(_rule_prefix + "/{rule_id}", response_model=RuleOut, tags=["classification"])
async def update_rule(
    household_id: HouseholdMember,
    rule_id: uuid.UUID,
    body: RuleUpdate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RuleOut:
    try:
        rule = await service.update_rule(
            session,
            rule_id=rule_id,
            household_id=household_id,
            actor_id=current_user.id,
            name=body.name,
            priority=body.priority,
            conditions=[c.model_dump() for c in body.conditions]
            if body.conditions is not None
            else None,
            actions=[a.model_dump() for a in body.actions] if body.actions is not None else None,
            mode=str(body.mode) if body.mode is not None else None,
            enabled=body.enabled,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return RuleOut.model_validate(rule)


@router.delete(
    _rule_prefix + "/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["classification"],
)
async def archive_rule(
    household_id: HouseholdMember,
    rule_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    try:
        await service.archive_rule(
            session,
            rule_id=rule_id,
            household_id=household_id,
            actor_id=current_user.id,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(_rule_prefix + "/reorder", response_model=list[RuleOut], tags=["classification"])
async def reorder_rules(
    household_id: HouseholdMember,
    body: RulePriorityReorderRequest,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[RuleOut]:
    try:
        rules = await service.reorder_rules(
            session,
            household_id=household_id,
            actor_id=current_user.id,
            items=[{"rule_id": str(i.rule_id), "priority": i.priority} for i in body.items],
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [RuleOut.model_validate(r) for r in rules]


@router.post(
    _rule_prefix + "/{rule_id}/test", response_model=RuleTestResult, tags=["classification"]
)
async def test_rule(
    household_id: HouseholdMember,
    rule_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RuleTestResult:
    try:
        matching_ids, sample_count, matching_txs = await service.test_rule(
            session, rule_id=rule_id, household_id=household_id
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return RuleTestResult(
        matching_transaction_ids=matching_ids,
        match_count=len(matching_ids),
        sample_count=sample_count,
        sample_transactions=[
            TransactionSummary(
                id=tx.id,
                posted_date=tx.posted_date,
                description=tx.description,
                merchant_name=tx.merchant_name,
                amount=tx.amount,
                currency=tx.currency,
                direction=tx.direction,
            )
            for tx in matching_txs
        ],
    )


# ---------------------------------------------------------------------------
# Income Sources
# ---------------------------------------------------------------------------

_src_prefix = "/households/{household_id}/income-sources"


@router.get(_src_prefix, response_model=list[IncomeSourceOut], tags=["classification"])
async def list_income_sources(
    household_id: HouseholdMember,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[IncomeSourceOut]:
    sources = await service.list_income_sources(session, household_id=household_id)
    return [IncomeSourceOut.model_validate(s) for s in sources]


@router.post(
    _src_prefix,
    response_model=IncomeSourceOut,
    status_code=status.HTTP_201_CREATED,
    tags=["classification"],
)
async def create_income_source(
    household_id: HouseholdMember,
    body: IncomeSourceCreate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> IncomeSourceOut:
    src = await service.create_income_source(
        session,
        household_id=household_id,
        actor_id=current_user.id,
        attributed_to_user_id=body.attributed_to_user_id,
        employer_name=body.employer_name,
        sub_type=str(body.sub_type),
        expected_amount_min=body.expected_amount_min,
        expected_amount_max=body.expected_amount_max,
        currency=body.currency,
        expected_cadence=body.expected_cadence,
        account_id=body.account_id,
        variability_model=str(body.variability_model),
        deposit_split_pattern=[e.model_dump(mode="json") for e in body.deposit_split_pattern],
    )
    return IncomeSourceOut.model_validate(src)


@router.get(_src_prefix + "/{source_id}", response_model=IncomeSourceOut, tags=["classification"])
async def get_income_source(
    household_id: HouseholdMember,
    source_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> IncomeSourceOut:
    try:
        src = await service.get_income_source(
            session, source_id=source_id, household_id=household_id
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return IncomeSourceOut.model_validate(src)


@router.patch(_src_prefix + "/{source_id}", response_model=IncomeSourceOut, tags=["classification"])
async def update_income_source(
    household_id: HouseholdMember,
    source_id: uuid.UUID,
    body: IncomeSourceUpdate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> IncomeSourceOut:
    try:
        src = await service.update_income_source(
            session,
            source_id=source_id,
            household_id=household_id,
            actor_id=current_user.id,
            employer_name=body.employer_name,
            sub_type=str(body.sub_type) if body.sub_type is not None else None,
            expected_amount_min=body.expected_amount_min,
            expected_amount_max=body.expected_amount_max,
            currency=body.currency,
            expected_cadence=body.expected_cadence,
            account_id=body.account_id,
            variability_model=str(body.variability_model)
            if body.variability_model is not None
            else None,
            deposit_split_pattern=(
                [e.model_dump(mode="json") for e in body.deposit_split_pattern]
                if body.deposit_split_pattern is not None
                else None
            ),
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return IncomeSourceOut.model_validate(src)


@router.delete(
    _src_prefix + "/{source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["classification"],
)
async def archive_income_source(
    household_id: HouseholdMember,
    source_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    try:
        await service.archive_income_source(
            session,
            source_id=source_id,
            household_id=household_id,
            actor_id=current_user.id,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Household classification settings
# ---------------------------------------------------------------------------

_settings_prefix = "/households/{household_id}/classification-settings"


@router.get(_settings_prefix, response_model=HouseholdSettingsOut, tags=["classification"])
async def get_classification_settings(
    household_id: HouseholdMember,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> HouseholdSettingsOut:
    settings = await service.get_household_settings(session, household_id=household_id)
    return HouseholdSettingsOut.model_validate(settings)


@router.patch(_settings_prefix, response_model=HouseholdSettingsOut, tags=["classification"])
async def update_classification_settings(
    household_id: HouseholdMember,
    body: HouseholdSettingsUpdate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> HouseholdSettingsOut:
    settings = await service.update_household_settings(
        session,
        household_id=household_id,
        actor_id=current_user.id,
        strictness=str(body.strictness),
    )
    return HouseholdSettingsOut.model_validate(settings)


# ---------------------------------------------------------------------------
# Reclassification
# ---------------------------------------------------------------------------


@router.post(
    "/households/{household_id}/transactions/{transaction_id}/reclassify",
    response_model=ClassificationResultOut,
    tags=["classification"],
)
async def reclassify_transaction(
    household_id: HouseholdMember,
    transaction_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ClassificationResultOut:
    try:
        result = await service.reclassify_transaction(
            session,
            transaction_id=transaction_id,
            household_id=household_id,
            actor_id=current_user.id,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ClassificationResultOut(
        allocation_updates=len(result.allocation_updates),
        suggestions=len(result.suggestions),
        hitl_items=len(result.hitl_items),
    )


@router.post(
    "/households/{household_id}/reclassify-all",
    response_model=ReclassifyAllOut,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["classification"],
)
async def reclassify_all(
    household_id: HouseholdMember,
) -> ReclassifyAllOut:
    """Enqueue a bulk reclassification job. Returns immediately with a job ID."""
    app_settings = get_settings()
    job_id = await service.enqueue_reclassify_all(
        household_id=household_id,
        redis_url=str(app_settings.redis_url),
    )
    return ReclassifyAllOut(job_id=job_id)
