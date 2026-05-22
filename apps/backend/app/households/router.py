"""FastAPI routes for households and auth.

Routes:
  Auth:
    POST   /api/v1/auth/register
    POST   /api/v1/auth/login
    POST   /api/v1/auth/refresh
    POST   /api/v1/auth/logout
    POST   /api/v1/auth/step-up
    GET    /api/v1/auth/me
    PATCH  /api/v1/auth/me
    POST   /api/v1/auth/totp/setup
    POST   /api/v1/auth/totp/confirm
    DELETE /api/v1/auth/totp/disable
    GET    /api/v1/auth/sessions
    DELETE /api/v1/auth/sessions/{token_id}
    POST   /api/v1/auth/change-password

  Households:
    GET    /api/v1/households
    POST   /api/v1/households
    GET    /api/v1/households/{household_id}
    PATCH  /api/v1/households/{household_id}
    DELETE /api/v1/households/{household_id}
    GET    /api/v1/households/{household_id}/members
    POST   /api/v1/households/{household_id}/members     (step-up required)
    DELETE /api/v1/households/{household_id}/members/{user_id} (step-up required)
    POST   /api/v1/households/{household_id}/invitations/
    GET    /api/v1/households/{household_id}/invitations/
    POST   /api/v1/households/{household_id}/invitations/{invitation_id}/resend
    POST   /api/v1/households/{household_id}/invitations/{invitation_id}/revoke

  Public (no auth):
    GET    /api/v1/invitations/{token}
    POST   /api/v1/invitations/{token}/accept
    POST   /api/v1/invitations/{token}/decline
    GET    /api/v1/settings/smtp-status

No business logic in this file — all logic is in service.py / invitations.py.
"""

import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings, smtp_configured
from app.database import get_db
from app.households import invitations as inv_service
from app.households import schemas, service
from app.households.deps import CurrentUser, StepUpUser
from app.households.enums import HouseholdRole, InvitationStatus
from app.households.schemas import (
    AcceptInviteResponse,
    AddMemberRequest,
    ChangePasswordRequest,
    CreateInvitationRequest,
    HouseholdCreate,
    HouseholdOut,
    HouseholdUpdate,
    HouseholdUpdateOut,
    InvitationOut,
    InviteMetadataOut,
    LoginRequest,
    MembershipOut,
    RegisterRequest,
    RegisterResponse,
    SessionOut,
    SmtpStatusResponse,
    StepUpRequest,
    TokenResponse,
    TotpSetupOut,
    UpdateProfileRequest,
    UserOut,
)
from app.security import cookies as cookie_service
from app.security.ratelimit import get_limiter

router = APIRouter(tags=["households", "auth"])
limiter = get_limiter()

_DbSession = Annotated[AsyncSession, Depends(get_db)]


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------


@router.post("/auth/register", status_code=status.HTTP_201_CREATED, response_model=RegisterResponse)
async def register(
    body: RegisterRequest,
    response: Response,
    session: _DbSession,
) -> RegisterResponse | JSONResponse:
    """Register a new user with local credentials.

    Returns a RegisterResponse with has_household and redirect routing hints.
    Returns RFC 9457 Problem Details (403) if registration is blocked.
    """
    try:
        user = await service.register_user(
            session,
            email=body.email,
            display_name=body.display_name,
            password=body.password,
            invite_token=None,
        )
    except service.RegistrationClosedError:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "type": "registration_closed",
                "title": "Registration is closed",
                "detail": ("New accounts are not accepted. Contact your administrator."),
                "status": 403,
            },
        )
    except service.RegistrationLimitReachedError:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "type": "registration_limit_reached",
                "title": "Registration limit reached",
                "detail": (
                    "The maximum number of accounts has been reached. Contact your administrator."
                ),
                "status": 403,
            },
        )
    except service.ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    settings = get_settings()
    access_token, refresh_token = await service.issue_tokens(
        session,
        user=user,
        household_id=None,
        jwt_secret=settings.jwt_secret,
    )
    cookie_service.set_auth_cookies(
        response,
        access_token=access_token,
        refresh_token=refresh_token,
        secure=not settings.debug,
    )
    memberships = await service.list_households(session, actor=user)
    has_household = len(memberships) > 0
    redirect = "/onboarding" if has_household else "/waiting"
    return RegisterResponse(
        user_id=user.id,
        is_app_admin=user.is_app_admin,
        has_household=has_household,
        redirect=redirect,
    )


@router.post("/auth/login", response_model=TokenResponse)
@limiter.limit("10/minute")  # type: ignore[misc]
async def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    session: _DbSession,
) -> TokenResponse:
    """Authenticate with local credentials and receive session cookies."""
    try:
        user = await service.authenticate_local(
            session,
            email=body.email,
            password=body.password,
            totp_code=body.totp_code,
        )
    except service.TotpRequiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="totp_required",
        ) from None
    except service.AuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid credentials",
        ) from None

    # Resolve default household (first membership, if any)
    memberships = await service.list_households(session, actor=user)
    household_id = memberships[0].id if memberships else None

    settings = get_settings()
    access_token, refresh_token = await service.issue_tokens(
        session,
        user=user,
        household_id=household_id,
        jwt_secret=settings.jwt_secret,
    )
    cookie_service.set_auth_cookies(
        response,
        access_token=access_token,
        refresh_token=refresh_token,
        secure=not settings.debug,
    )
    return TokenResponse(user_id=user.id, is_app_admin=user.is_app_admin)


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    session: _DbSession,
) -> TokenResponse:
    """Rotate the refresh token (sliding-window idle timeout)."""
    raw_token = cookie_service.get_refresh_token(request)
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="refresh token missing",
        )

    settings = get_settings()
    try:
        new_access, new_raw = await service.refresh_tokens(
            session,
            raw_refresh_token=raw_token,
            jwt_secret=settings.jwt_secret,
        )
    except service.AuthenticationError as exc:
        cookie_service.clear_auth_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    # Load the user from the new access token claims for the response
    from app.security import jwt as jwt_service

    claims = jwt_service.validate_access_token(new_access, settings.jwt_secret)
    user_id = uuid.UUID(str(claims["sub"]))
    user = await service.get_user_by_id(session, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found")

    cookie_service.set_auth_cookies(
        response,
        access_token=new_access,
        refresh_token=new_raw,
        secure=not settings.debug,
    )
    return TokenResponse(user_id=user.id, is_app_admin=user.is_app_admin)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    current_user: CurrentUser,
    session: _DbSession,
) -> None:
    """Revoke all refresh tokens for the current user and clear cookies."""
    await service.revoke_all_tokens(session, user_id=current_user.id)
    cookie_service.clear_auth_cookies(response)


@router.post("/auth/step-up", response_model=TokenResponse)
@limiter.limit("5/minute")  # type: ignore[misc]
async def step_up(
    request: Request,
    body: StepUpRequest,
    response: Response,
    current_user: CurrentUser,
    session: _DbSession,
) -> TokenResponse:
    """Grant step-up elevation for App Admin actions (5-minute window)."""
    settings = get_settings()
    try:
        step_up_token = await service.step_up_auth(
            session,
            user=current_user,
            password=body.password,
            totp_code=body.totp_code,
            jwt_secret=settings.jwt_secret,
        )
    except service.AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    cookie_service.set_step_up_cookie(
        response,
        step_up_token=step_up_token,
        secure=not settings.debug,
    )
    return TokenResponse(user_id=current_user.id, is_app_admin=current_user.is_app_admin)


@router.get("/auth/me", response_model=UserOut)
async def me(current_user: CurrentUser) -> UserOut:
    """Return the authenticated user's profile."""
    return UserOut.model_validate(current_user)


@router.patch("/auth/me", response_model=UserOut)
async def update_me(
    body: UpdateProfileRequest,
    current_user: CurrentUser,
    session: _DbSession,
) -> UserOut:
    """Update the authenticated user's display_name."""
    user = await service.update_user_profile(
        session,
        user=current_user,
        display_name=body.display_name,
    )
    return UserOut.model_validate(user)


@router.post("/auth/totp/setup", response_model=TotpSetupOut)
async def totp_setup(
    current_user: CurrentUser,
    session: _DbSession,
) -> TotpSetupOut:
    """Begin TOTP enrollment — returns a provisioning URI and raw secret for QR-code display."""
    uri, secret = await service.setup_totp(session, user=current_user)
    return TotpSetupOut(provisioning_uri=uri, secret=secret)


@router.post("/auth/totp/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def totp_confirm(
    body: schemas.StepUpRequest,
    current_user: CurrentUser,
    session: _DbSession,
) -> None:
    """Confirm TOTP enrollment with the first generated code."""
    if not body.totp_code:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="totp_code is required",
        )
    try:
        await service.confirm_totp(session, user=current_user, code=body.totp_code)
    except service.AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/auth/totp/disable", status_code=status.HTTP_204_NO_CONTENT)
async def totp_disable(
    current_user: CurrentUser,
    session: _DbSession,
) -> None:
    """Disable TOTP for the current user."""
    await service.disable_totp(session, user=current_user)


@router.get("/auth/sessions", response_model=list[SessionOut])
async def list_sessions(
    current_user: CurrentUser,
    session: _DbSession,
) -> list[SessionOut]:
    """Return all active refresh tokens (sessions) for the current user."""
    tokens = await service.list_user_sessions(session, user_id=current_user.id)
    return [SessionOut.model_validate(t) for t in tokens]


@router.delete("/auth/sessions/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(
    token_id: uuid.UUID,
    current_user: CurrentUser,
    session: _DbSession,
) -> None:
    """Revoke a specific refresh token (session) for the current user."""
    try:
        await service.revoke_user_session(
            session,
            user_id=current_user.id,
            token_id=token_id,
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/auth/change-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")  # type: ignore[misc]
async def change_password(
    request: Request,
    body: ChangePasswordRequest,
    current_user: CurrentUser,
    session: _DbSession,
) -> None:
    """Change the current user's password. Revokes all active sessions."""
    try:
        await service.change_password(
            session,
            user=current_user,
            current_password=body.current_password,
            new_password=body.new_password,
        )
    except service.AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Household routes
# ---------------------------------------------------------------------------


@router.get("/households", response_model=list[HouseholdOut])
async def list_households(
    current_user: CurrentUser,
    session: _DbSession,
) -> list[HouseholdOut]:
    """List all households the current user is a member of."""
    households = await service.list_households(session, actor=current_user)
    return [HouseholdOut.model_validate(h) for h in households]


@router.post("/households", response_model=HouseholdOut, status_code=status.HTTP_201_CREATED)
async def create_household(
    body: HouseholdCreate,
    current_user: CurrentUser,
    session: _DbSession,
) -> HouseholdOut:
    """Create a new household. The creator becomes the owner."""
    household = await service.create_household(
        session,
        name=body.name,
        visibility_mode=body.visibility_mode,
        home_currency=body.home_currency,
        owner=current_user,
    )
    return HouseholdOut.model_validate(household)


@router.get("/households/{household_id}", response_model=HouseholdOut)
async def get_household(
    household_id: uuid.UUID,
    current_user: CurrentUser,
    session: _DbSession,
) -> HouseholdOut:
    """Return household details (actor must be a member)."""
    try:
        household = await service.get_household(
            session, household_id=household_id, actor=current_user
        )
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return HouseholdOut.model_validate(household)


@router.patch("/households/{household_id}", response_model=HouseholdUpdateOut)
async def update_household(
    household_id: uuid.UUID,
    body: HouseholdUpdate,
    current_user: CurrentUser,
    session: _DbSession,
) -> HouseholdUpdateOut:
    """Update household settings (actor must be owner).

    When home_currency changes, enqueues recompute_fx_conversions_job and
    returns recompute_started=true. Clients should show a recalculating banner
    until the fx_recompute_complete SSE event is received.
    """
    try:
        household, recompute_started = await service.update_household(
            session,
            household_id=household_id,
            actor=current_user,
            name=body.name,
            visibility_mode=body.visibility_mode,
            home_currency=body.home_currency,
        )
    except service.PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    out = HouseholdUpdateOut.model_validate(household)
    out.recompute_started = recompute_started
    return out


@router.delete("/households/{household_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_household(
    household_id: uuid.UUID,
    current_user: CurrentUser,
    session: _DbSession,
) -> None:
    """Soft-delete (archive) a household (actor must be owner)."""
    try:
        await service.archive_household(session, household_id=household_id, actor=current_user)
    except service.PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/households/{household_id}/members", response_model=list[MembershipOut])
async def list_members(
    household_id: uuid.UUID,
    current_user: CurrentUser,
    session: _DbSession,
) -> list[MembershipOut]:
    """List all active members of the household."""
    try:
        memberships = await service.list_members(
            session, household_id=household_id, actor=current_user
        )
    except service.PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    # Eagerly load user objects for the response
    results: list[MembershipOut] = []
    for m in memberships:
        user = await service.get_user_by_id(session, m.user_id)
        if user is not None:
            results.append(
                MembershipOut(
                    id=m.id,
                    household_id=m.household_id,
                    user_id=m.user_id,
                    role=m.role,
                    created_at=m.created_at,
                    user=UserOut.model_validate(user),
                )
            )
    return results


@router.post(
    "/households/{household_id}/members",
    response_model=MembershipOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    household_id: uuid.UUID,
    body: AddMemberRequest,
    _step_up_user: StepUpUser,
    current_user: CurrentUser,
    session: _DbSession,
) -> MembershipOut:
    """Add a user to the household (requires step-up auth + App Admin)."""
    try:
        membership = await service.add_member(
            session,
            household_id=household_id,
            email=body.email,
            role=body.role,
            actor=current_user,
        )
    except service.PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except (service.NotFoundError, service.ConflictError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    user = await service.get_user_by_id(session, membership.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    return MembershipOut(
        id=membership.id,
        household_id=membership.household_id,
        user_id=membership.user_id,
        role=membership.role,
        created_at=membership.created_at,
        user=UserOut.model_validate(user),
    )


@router.delete(
    "/households/{household_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member(
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    _step_up_user: StepUpUser,
    current_user: CurrentUser,
    session: _DbSession,
) -> None:
    """Remove a member from the household (requires step-up auth + App Admin)."""
    try:
        await service.remove_member(
            session,
            household_id=household_id,
            user_id=user_id,
            actor=current_user,
        )
    except service.PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Invitation routes (owner or app_admin only)
# ---------------------------------------------------------------------------


async def _require_owner_or_admin(
    session: AsyncSession,
    household_id: uuid.UUID,
    actor: service.User,
) -> None:
    """Raise HTTPException 403 unless actor is owner or app_admin."""
    if actor.is_app_admin:
        return
    from app.households.models import HouseholdMembership

    stmt = sa.select(HouseholdMembership).where(
        HouseholdMembership.household_id == household_id,
        HouseholdMembership.user_id == actor.id,
        HouseholdMembership.archived_at.is_(None),
    )
    result = await session.execute(stmt)
    membership = result.scalar_one_or_none()
    if membership is None or membership.role != str(HouseholdRole.OWNER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="must be household owner or app admin",
        )


@router.post(
    "/households/{household_id}/invitations/",
    response_model=InvitationOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_invitation(
    household_id: uuid.UUID,
    body: CreateInvitationRequest,
    current_user: CurrentUser,
    session: _DbSession,
) -> InvitationOut:
    """Create a household invitation (owner or app_admin)."""
    await _require_owner_or_admin(session, household_id, current_user)
    try:
        invite = await inv_service.create_invitation(
            session,
            household_id=household_id,
            invited_by_id=current_user.id,
            invited_email=body.email,
            role=HouseholdRole(body.role),
        )
    except inv_service.AlreadyMemberError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member",
        ) from exc
    except inv_service.PendingInviteExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    await session.refresh(invite, ["household", "invited_by"])
    return InvitationOut.from_invite(invite, inv_service.get_invite_url(invite.token))


@router.get(
    "/households/{household_id}/invitations/",
    response_model=list[InvitationOut],
)
async def list_invitations(
    household_id: uuid.UUID,
    current_user: CurrentUser,
    session: _DbSession,
    status_filter: str | None = None,
) -> list[InvitationOut]:
    """List invitations for this household (owner or app_admin)."""
    await _require_owner_or_admin(session, household_id, current_user)
    inv_status: InvitationStatus | None = None
    if status_filter and status_filter != "all":
        try:
            inv_status = InvitationStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"invalid status filter: {status_filter!r}",
            ) from None
    invites = await inv_service.list_invitations(
        session, household_id=household_id, status=inv_status
    )
    results: list[InvitationOut] = []
    for invite in invites:
        await session.refresh(invite, ["household", "invited_by"])
        results.append(InvitationOut.from_invite(invite, inv_service.get_invite_url(invite.token)))
    return results


@router.post(
    "/households/{household_id}/invitations/{invitation_id}/resend",
    response_model=InvitationOut,
)
async def resend_invitation(
    household_id: uuid.UUID,
    invitation_id: uuid.UUID,
    current_user: CurrentUser,
    session: _DbSession,
) -> InvitationOut:
    """Reset invite expiry and reattempt email delivery (owner or app_admin)."""
    from app.households.models import HouseholdMembership

    membership = await session.execute(
        sa.select(HouseholdMembership).where(
            HouseholdMembership.household_id == household_id,
            HouseholdMembership.user_id == current_user.id,
            HouseholdMembership.archived_at.is_(None),
        )
    )
    m = membership.scalar_one_or_none()
    is_owner = m is not None and m.role == str(HouseholdRole.OWNER)
    try:
        invite = await inv_service.resend_invite(
            session,
            invitation_id=invitation_id,
            resent_by_id=current_user.id,
            actor_is_owner=is_owner,
            actor_is_app_admin=current_user.is_app_admin,
        )
    except inv_service.PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except inv_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except inv_service.InviteExpiredError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await session.refresh(invite, ["household", "invited_by"])
    return InvitationOut.from_invite(invite, inv_service.get_invite_url(invite.token))


@router.post(
    "/households/{household_id}/invitations/{invitation_id}/revoke",
    response_model=InvitationOut,
)
async def revoke_invitation(
    household_id: uuid.UUID,
    invitation_id: uuid.UUID,
    current_user: CurrentUser,
    session: _DbSession,
) -> InvitationOut:
    """Revoke a pending invitation (owner or app_admin)."""
    from app.households.models import HouseholdMembership

    membership = await session.execute(
        sa.select(HouseholdMembership).where(
            HouseholdMembership.household_id == household_id,
            HouseholdMembership.user_id == current_user.id,
            HouseholdMembership.archived_at.is_(None),
        )
    )
    m = membership.scalar_one_or_none()
    is_owner = m is not None and m.role == str(HouseholdRole.OWNER)
    try:
        invite = await inv_service.revoke_invite(
            session,
            invitation_id=invitation_id,
            revoked_by_id=current_user.id,
            actor_is_owner=is_owner,
            actor_is_app_admin=current_user.is_app_admin,
        )
    except inv_service.PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except inv_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.refresh(invite, ["household", "invited_by"])
    return InvitationOut.from_invite(invite, inv_service.get_invite_url(invite.token))


# ---------------------------------------------------------------------------
# Public invitation endpoints (no auth required for GET metadata + accept/decline)
# ---------------------------------------------------------------------------


@router.get("/invitations/{token}", response_model=InviteMetadataOut)
async def get_invitation_metadata(
    token: str,
    session: _DbSession,
) -> InviteMetadataOut:
    """Return public invitation metadata. Token is NOT included in response."""
    try:
        invite = await inv_service.get_invite_by_token(session, token)
    except inv_service.InviteNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.refresh(invite, ["household", "invited_by"])
    return InviteMetadataOut.from_invite(invite)


@router.post("/invitations/{token}/accept", response_model=AcceptInviteResponse)
async def accept_invitation(
    token: str,
    current_user: CurrentUser,
    session: _DbSession,
) -> AcceptInviteResponse:
    """Accept an invitation. Requires authentication; validates email match."""
    try:
        membership = await inv_service.accept_invite(session, token=token, user_id=current_user.id)
    except inv_service.InviteNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except inv_service.InviteExpiredError as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc)) from exc
    except inv_service.AlreadyAcceptedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except inv_service.InviteRevokedError as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc)) from exc
    except inv_service.EmailMismatchError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except inv_service.AlreadyMemberError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return AcceptInviteResponse(
        household_id=membership.household_id,
        membership_id=membership.id,
    )


@router.post("/invitations/{token}/decline", status_code=status.HTTP_204_NO_CONTENT)
async def decline_invitation(
    token: str,
    current_user: CurrentUser,
    session: _DbSession,
) -> None:
    """Decline an invitation. No email match required."""
    try:
        await inv_service.decline_invite(session, token=token, user_id=current_user.id)
    except inv_service.InviteNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (inv_service.InviteExpiredError, inv_service.InviteRevokedError) as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc)) from exc
    except inv_service.AlreadyAcceptedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Public settings
# ---------------------------------------------------------------------------


@router.get("/settings/smtp-status", response_model=SmtpStatusResponse)
async def get_smtp_status(session: _DbSession) -> SmtpStatusResponse:
    """Return SMTP configuration status (no auth required, non-sensitive).

    Checks DB-stored config first, then falls back to env-var SMTP settings.
    """
    result = await session.execute(sa.text("SELECT 1 FROM admin_smtp_config LIMIT 1"))
    db_configured = result.scalar_one_or_none() is not None
    return SmtpStatusResponse(smtp_configured=db_configured or smtp_configured())


@router.get("/settings/registration", include_in_schema=True)
async def get_registration_settings(session: _DbSession) -> dict[str, object]:
    """Return public registration configuration.

    No authentication required — used by RegisterPage and WaitingPage.
    Reads DB-backed admin overrides so admin panel changes take effect immediately.
    """
    settings = get_settings()
    allow_reg, reg_limit = await service.get_effective_registration_settings(session, settings)
    return {
        "allow_registration": allow_reg,
        "registration_limit": reg_limit,
        "unassigned_account_ttl_days": settings.unassigned_account_ttl_days,
    }


# ---------------------------------------------------------------------------
# Household SSE event stream
# ---------------------------------------------------------------------------


async def _sse_stream(user_id: object) -> AsyncGenerator[str, None]:
    """Yield SSE events for this user. Keepalive comment every 30s."""
    import asyncio
    import uuid as _uuid

    uid = user_id if isinstance(user_id, _uuid.UUID) else _uuid.UUID(str(user_id))
    from app.households.sse import get_sse_manager

    mgr = get_sse_manager()
    async with mgr.connect(uid) as queue:
        while True:
            try:
                chunk = await asyncio.wait_for(queue.get(), timeout=30.0)
                if chunk is None:
                    break
                yield chunk
            except TimeoutError:
                yield ": keepalive\n\n"


@router.get("/households/events")
async def household_events(current_user: CurrentUser) -> StreamingResponse:
    """Server-Sent Events stream for household-level notifications.

    Emits events: household_assigned, read_only_changed.
    Keepalive comment every 30s to prevent proxy timeouts.
    """
    return StreamingResponse(
        _sse_stream(current_user.id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
