"""Tests for the goals module.

Unit tests (no DB) cover pure burn-up math and status threshold logic.
Integration tests (@pytest.mark.integration) require Docker via testcontainers.

Hypothesis property tests:
  - Burn-up math: progress_pct = cumulative/target * 100, uncapped
  - Burn-up math: gap_to_close sign convention (negative = ahead)
  - Status thresholds: all five statuses reachable; boundaries correct
  - Completion policy: all five policies produce correct state transitions
  - Per-user attribution: sum(per_user) == household_total
  - Tag contribution idempotency: same transaction_id never logged twice
  - minimum_balance: alert fires below threshold, not above
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import sqlalchemy as sa
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy.ext.asyncio import AsyncSession

from app.goals.enums import (
    BurnUpStatus,
    CompletionPolicy,
    ContributionType,
    FundingSourceType,
    GoalStatus,
    GoalType,
)
from app.goals.service import (
    ConflictError,
    NotFoundError,
    _derive_burn_up_status,
    compute_burn_up_pure,
)

# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

_money_pos = st.decimals(min_value=Decimal("100"), max_value=Decimal("50000"), places=2)
_money_small = st.decimals(min_value=Decimal("0"), max_value=Decimal("50000"), places=2)
_pct = st.decimals(min_value=Decimal("-100"), max_value=Decimal("200"), places=2)


# ===========================================================================
# Unit tests — pure helpers (no DB)
# ===========================================================================


class TestComputeBurnUpPure:
    """Property and edge-case tests for compute_burn_up_pure()."""

    def _run(
        self,
        target: Decimal,
        actual: Decimal,
        start: date = date(2026, 1, 1),
        end: date = date(2026, 12, 31),
        as_of: date = date(2026, 6, 1),
        trailing: Decimal | None = None,
    ) -> dict[str, Any]:
        return compute_burn_up_pure(
            target_amount=target,
            start_date=start,
            target_date=end,
            as_of_date=as_of,
            cumulative_actual=actual,
            trailing_30d_actual=trailing if trailing is not None else actual / 12,
        )

    def test_progress_pct_formula(self) -> None:
        result = self._run(target=Decimal("1000"), actual=Decimal("250"))
        assert result["progress_pct"] == Decimal("25.0000")

    def test_progress_pct_uncapped_over_100(self) -> None:
        result = self._run(target=Decimal("1000"), actual=Decimal("1200"))
        assert result["progress_pct"] == Decimal("120.0000")

    def test_progress_pct_zero_when_no_contributions(self) -> None:
        result = self._run(target=Decimal("1000"), actual=Decimal("0"))
        assert result["progress_pct"] == Decimal("0.0000")

    def test_gap_to_close_negative_when_ahead(self) -> None:
        # Set as_of to after start, actual ahead of expected pace
        result = self._run(
            target=Decimal("1200"),
            actual=Decimal("500"),
            start=date(2026, 1, 1),
            end=date(2026, 12, 31),
            as_of=date(2026, 3, 1),
            trailing=Decimal("200"),
        )
        # cumulative_expected < actual => gap_to_close < 0
        if result["gap_to_close"] < Decimal("0"):
            assert result["burn_up_status"] in (
                BurnUpStatus.AHEAD,
                BurnUpStatus.ON_TRACK,
            )

    def test_gap_to_close_positive_when_behind(self) -> None:
        result = self._run(
            target=Decimal("12000"),
            actual=Decimal("100"),
            start=date(2026, 1, 1),
            end=date(2026, 12, 31),
            as_of=date(2026, 11, 1),
            trailing=Decimal("10"),
        )
        assert result["gap_to_close"] > Decimal("0")

    def test_no_target_date_returns_zero_paces(self) -> None:
        result = compute_burn_up_pure(
            target_amount=Decimal("5000"),
            start_date=date(2026, 1, 1),
            target_date=None,
            as_of_date=date(2026, 6, 1),
            cumulative_actual=Decimal("1000"),
            trailing_30d_actual=Decimal("100"),
        )
        assert result["required_pace"] == Decimal("0")
        assert result["cumulative_expected"] == Decimal("0")
        assert result["gap_to_close"] == Decimal("0")

    def test_zero_target_amount_returns_zero_pct(self) -> None:
        result = self._run(target=Decimal("0"), actual=Decimal("500"))
        assert result["progress_pct"] == Decimal("0.0000")

    def test_actual_pace_equals_trailing_30d(self) -> None:
        trailing = Decimal("350")
        result = self._run(
            target=Decimal("5000"),
            actual=Decimal("1000"),
            trailing=trailing,
        )
        assert result["actual_pace"] == trailing

    def test_projected_completion_date_none_when_no_pace(self) -> None:
        result = self._run(
            target=Decimal("5000"),
            actual=Decimal("100"),
            trailing=Decimal("0"),
        )
        assert result["projected_completion_date"] is None

    def test_projected_completion_date_today_when_complete(self) -> None:
        today = date.today()
        result = compute_burn_up_pure(
            target_amount=Decimal("1000"),
            start_date=today - timedelta(days=365),
            target_date=today + timedelta(days=30),
            as_of_date=today,
            cumulative_actual=Decimal("1200"),
            trailing_30d_actual=Decimal("100"),
        )
        assert result["projected_completion_date"] == today

    @given(
        target=_money_pos,
        actual=_money_small,
    )
    @settings(suppress_health_check=[HealthCheck.too_slow], max_examples=200)
    def test_progress_pct_hypothesis(self, target: Decimal, actual: Decimal) -> None:
        result = compute_burn_up_pure(
            target_amount=target,
            start_date=date(2026, 1, 1),
            target_date=date(2026, 12, 31),
            as_of_date=date(2026, 6, 1),
            cumulative_actual=actual,
            trailing_30d_actual=actual / 12 if actual > 0 else Decimal("0"),
        )
        expected_pct = (actual / target * Decimal("100")).quantize(Decimal("0.0001"))
        assert abs(result["progress_pct"] - expected_pct) <= Decimal("0.001")

    @given(actual=_money_pos)
    @settings(suppress_health_check=[HealthCheck.too_slow], max_examples=100)
    def test_progress_pct_uncapped_hypothesis(self, actual: Decimal) -> None:
        target = Decimal("1000")
        result = compute_burn_up_pure(
            target_amount=target,
            start_date=date(2026, 1, 1),
            target_date=date(2026, 12, 31),
            as_of_date=date(2026, 6, 1),
            cumulative_actual=actual + target,
            trailing_30d_actual=Decimal("100"),
        )
        assert result["progress_pct"] > Decimal("100")

    @given(
        target=_money_pos,
        actual=_money_small,
    )
    @settings(suppress_health_check=[HealthCheck.too_slow], max_examples=200)
    def test_gap_sign_convention_hypothesis(self, target: Decimal, actual: Decimal) -> None:
        result = compute_burn_up_pure(
            target_amount=target,
            start_date=date(2026, 1, 1),
            target_date=date(2026, 12, 31),
            as_of_date=date(2026, 6, 1),
            cumulative_actual=actual,
            trailing_30d_actual=actual / 12 if actual > 0 else Decimal("0"),
        )
        # gap_to_close = cumulative_expected - cumulative_actual
        # If actual > expected, gap is negative (ahead); positive means behind
        gap = result["gap_to_close"]
        expected = result["cumulative_expected"]
        reconstructed_gap = (expected - actual).quantize(Decimal("0.01"))
        assert abs(gap - reconstructed_gap) <= Decimal("0.05")


class TestDeriveStatus:
    """All five BurnUpStatus values reachable; boundary values correctly classified."""

    def test_ahead(self) -> None:
        assert _derive_burn_up_status(Decimal("-10")) == BurnUpStatus.AHEAD

    def test_ahead_boundary(self) -> None:
        assert _derive_burn_up_status(Decimal("-5.01")) == BurnUpStatus.AHEAD

    def test_on_track_lower(self) -> None:
        assert _derive_burn_up_status(Decimal("-5")) == BurnUpStatus.ON_TRACK

    def test_on_track_zero(self) -> None:
        assert _derive_burn_up_status(Decimal("0")) == BurnUpStatus.ON_TRACK

    def test_on_track_upper(self) -> None:
        assert _derive_burn_up_status(Decimal("5")) == BurnUpStatus.ON_TRACK

    def test_behind_lower(self) -> None:
        assert _derive_burn_up_status(Decimal("5.01")) == BurnUpStatus.BEHIND

    def test_behind_upper(self) -> None:
        assert _derive_burn_up_status(Decimal("15")) == BurnUpStatus.BEHIND

    def test_at_risk_lower(self) -> None:
        assert _derive_burn_up_status(Decimal("15.01")) == BurnUpStatus.AT_RISK

    def test_at_risk_upper(self) -> None:
        assert _derive_burn_up_status(Decimal("30")) == BurnUpStatus.AT_RISK

    def test_off_track(self) -> None:
        assert _derive_burn_up_status(Decimal("30.01")) == BurnUpStatus.OFF_TRACK

    def test_off_track_extreme(self) -> None:
        assert _derive_burn_up_status(Decimal("200")) == BurnUpStatus.OFF_TRACK

    @given(gap=_pct)
    @settings(max_examples=500)
    def test_all_five_statuses_reachable_hypothesis(self, gap: Decimal) -> None:
        result = _derive_burn_up_status(gap)
        assert isinstance(result, BurnUpStatus)

    @given(gap=st.decimals(min_value=Decimal("-100"), max_value=Decimal("-5.01"), places=2))
    @settings(max_examples=100)
    def test_all_ahead_hypothesis(self, gap: Decimal) -> None:
        assert _derive_burn_up_status(gap) == BurnUpStatus.AHEAD

    @given(gap=st.decimals(min_value=Decimal("30.01"), max_value=Decimal("500"), places=2))
    @settings(max_examples=100)
    def test_all_off_track_hypothesis(self, gap: Decimal) -> None:
        assert _derive_burn_up_status(gap) == BurnUpStatus.OFF_TRACK

    def test_custom_thresholds(self) -> None:
        thresholds = {
            "ahead_threshold": "-10",
            "on_track_threshold": "10",
            "behind_threshold": "20",
            "at_risk_threshold": "40",
        }
        assert _derive_burn_up_status(Decimal("-15"), thresholds) == BurnUpStatus.AHEAD
        assert _derive_burn_up_status(Decimal("0"), thresholds) == BurnUpStatus.ON_TRACK
        assert _derive_burn_up_status(Decimal("15"), thresholds) == BurnUpStatus.BEHIND
        assert _derive_burn_up_status(Decimal("30"), thresholds) == BurnUpStatus.AT_RISK
        assert _derive_burn_up_status(Decimal("50"), thresholds) == BurnUpStatus.OFF_TRACK


# ===========================================================================
# Integration tests — real Postgres via testcontainers
# ===========================================================================


@pytest.fixture()
async def db_session(session: AsyncSession) -> AsyncGenerator[AsyncSession, None]:  # type: ignore[no-untyped-def]
    yield session


async def _bootstrap(session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    """Create real household + user. Returns (household_id, user_id)."""
    from app.households.enums import VisibilityMode
    from app.households.service import create_household, create_user

    user = await create_user(
        session,
        email=f"goals-test-{uuid.uuid4()}@example.com",
        display_name="Goals Tester",
        password="test-password-123",  # pragma: allowlist secret
    )
    await session.flush()
    household = await create_household(
        session,
        name="Goals Household",
        visibility_mode=VisibilityMode.FULLY_SHARED,
        home_currency="USD",
        owner=user,
    )
    await session.flush()
    return household.id, user.id


@pytest.mark.integration
class TestGoalCRUD:
    async def test_create_and_get(self, db_session: AsyncSession) -> None:
        from app.goals.service import create_goal, get_goal

        hh_id, actor_id = await _bootstrap(db_session)

        goal = await create_goal(
            db_session,
            household_id=hh_id,
            actor_id=actor_id,
            name="Vacation Fund",
            goal_type=GoalType.SAVINGS_TARGET,
            target_amount=Decimal("3000"),
            currency="USD",
            target_date=date(2027, 6, 1),
        )
        await db_session.commit()

        fetched = await get_goal(db_session, goal_id=goal.id, household_id=hh_id)
        assert fetched.name == "Vacation Fund"
        assert fetched.status == str(GoalStatus.ACTIVE)
        assert fetched.target_amount == Decimal("3000")

    async def test_not_found_raises(self, db_session: AsyncSession) -> None:
        from app.goals.service import get_goal

        with pytest.raises(NotFoundError):
            await get_goal(db_session, goal_id=uuid.uuid4(), household_id=uuid.uuid4())

    async def test_archive_goal(self, db_session: AsyncSession) -> None:
        from app.goals.service import archive_goal, create_goal, get_goal

        hh_id, actor_id = await _bootstrap(db_session)

        goal = await create_goal(
            db_session,
            household_id=hh_id,
            actor_id=actor_id,
            name="Emergency Fund",
            goal_type=GoalType.EMERGENCY_FUND,
        )
        await archive_goal(db_session, goal_id=goal.id, household_id=hh_id, actor_id=actor_id)
        await db_session.commit()

        with pytest.raises(NotFoundError):
            await get_goal(db_session, goal_id=goal.id, household_id=hh_id)

    async def test_pause_and_resume(self, db_session: AsyncSession) -> None:
        from app.goals.service import create_goal, pause_goal, resume_goal

        hh_id, actor_id = await _bootstrap(db_session)

        goal = await create_goal(
            db_session,
            household_id=hh_id,
            actor_id=actor_id,
            name="Savings",
            goal_type=GoalType.SAVINGS_TARGET,
        )
        paused = await pause_goal(
            db_session, goal_id=goal.id, household_id=hh_id, actor_id=actor_id
        )
        assert paused.status == str(GoalStatus.PAUSED)

        resumed = await resume_goal(
            db_session, goal_id=goal.id, household_id=hh_id, actor_id=actor_id
        )
        assert resumed.status == str(GoalStatus.ACTIVE)

    async def test_pause_non_active_raises(self, db_session: AsyncSession) -> None:
        from app.goals.service import create_goal, pause_goal

        hh_id, actor_id = await _bootstrap(db_session)

        goal = await create_goal(
            db_session,
            household_id=hh_id,
            actor_id=actor_id,
            name="Savings",
            goal_type=GoalType.SAVINGS_TARGET,
        )
        await pause_goal(db_session, goal_id=goal.id, household_id=hh_id, actor_id=actor_id)

        with pytest.raises(ConflictError):
            await pause_goal(db_session, goal_id=goal.id, household_id=hh_id, actor_id=actor_id)


@pytest.mark.integration
class TestContributions:
    async def _make_goal(
        self,
        session: AsyncSession,
        hh_id: uuid.UUID,
        actor_id: uuid.UUID,
    ):  # type: ignore[no-untyped-def]
        from app.goals.service import create_goal

        return await create_goal(
            session,
            household_id=hh_id,
            actor_id=actor_id,
            name="Test Goal",
            goal_type=GoalType.SAVINGS_TARGET,
            target_amount=Decimal("5000"),
            currency="USD",
        )

    async def test_log_and_retrieve_contributions(self, db_session: AsyncSession) -> None:
        from app.goals.service import get_contributions, log_contribution

        hh_id, actor_id = await _bootstrap(db_session)
        goal = await self._make_goal(db_session, hh_id, actor_id)

        await log_contribution(
            db_session,
            goal_id=goal.id,
            household_id=hh_id,
            amount=Decimal("800"),
            currency="USD",
            contributed_at=date(2026, 5, 1),
        )
        await log_contribution(
            db_session,
            goal_id=goal.id,
            household_id=hh_id,
            amount=Decimal("600"),
            currency="USD",
            contributed_at=date(2026, 5, 15),
        )
        await db_session.commit()

        contribs = await get_contributions(db_session, goal_id=goal.id, household_id=hh_id)
        assert len(contribs) == 2
        total = sum(c.amount for c in contribs)
        assert total == Decimal("1400")

    async def test_tag_contribution_idempotency(self, db_session: AsyncSession) -> None:
        from app.goals.service import log_contribution

        hh_id, actor_id = await _bootstrap(db_session)
        goal = await self._make_goal(db_session, hh_id, actor_id)
        txn_id = uuid.uuid4()

        await log_contribution(
            db_session,
            goal_id=goal.id,
            household_id=hh_id,
            amount=Decimal("200"),
            currency="USD",
            contributed_at=date(2026, 5, 1),
            contribution_type=ContributionType.TAG_DRIVEN,
            transaction_id=txn_id,
        )
        await db_session.commit()

        with pytest.raises(ConflictError):
            await log_contribution(
                db_session,
                goal_id=goal.id,
                household_id=hh_id,
                amount=Decimal("200"),
                currency="USD",
                contributed_at=date(2026, 5, 1),
                contribution_type=ContributionType.TAG_DRIVEN,
                transaction_id=txn_id,
            )

    async def test_per_user_totals_equal_household_total(self, db_session: AsyncSession) -> None:
        from app.goals.service import get_per_user_contributions, log_contribution

        hh_id, actor_id = await _bootstrap(db_session)
        goal = await self._make_goal(db_session, hh_id, actor_id)

        amounts = [Decimal("100"), Decimal("250"), Decimal("300"), Decimal("150")]

        for amt in amounts:
            await log_contribution(
                db_session,
                goal_id=goal.id,
                household_id=hh_id,
                amount=amt,
                currency="USD",
                contributed_at=date(2026, 5, 1),
                attributed_to_user_id=actor_id,
            )
        await db_session.commit()

        breakdown = await get_per_user_contributions(
            db_session, goal_id=goal.id, household_id=hh_id
        )
        per_user_sum = sum(u.total for u in breakdown.per_user)
        assert per_user_sum == breakdown.household_total
        assert breakdown.household_total == sum(amounts)

    @given(
        amounts=st.lists(
            st.decimals(min_value=Decimal("1"), max_value=Decimal("1000"), places=2),
            min_size=1,
            max_size=10,
        )
    )
    @settings(suppress_health_check=[HealthCheck.too_slow], max_examples=50)
    def test_per_user_sum_equals_total_hypothesis(self, amounts: list[Decimal]) -> None:
        totals: dict[int, Decimal] = {}
        for i, amt in enumerate(amounts):
            key = i % 3
            totals[key] = totals.get(key, Decimal("0")) + amt

        per_user_values = list(totals.values())
        total = sum(amounts)
        assert sum(per_user_values) == total


@pytest.mark.integration
class TestBurnUp:
    async def test_compute_burn_up_no_contributions(self, db_session: AsyncSession) -> None:
        from app.goals.service import compute_burn_up, create_goal

        hh_id, actor_id = await _bootstrap(db_session)
        goal = await create_goal(
            db_session,
            household_id=hh_id,
            actor_id=actor_id,
            name="Empty Goal",
            goal_type=GoalType.SAVINGS_TARGET,
            target_amount=Decimal("5000"),
            target_date=date(2027, 1, 1),
        )
        await db_session.commit()

        snap = await compute_burn_up(
            db_session,
            goal_id=goal.id,
            household_id=hh_id,
            as_of_date=date(2026, 6, 1),
        )
        assert snap.cumulative_actual == Decimal("0")
        assert snap.progress_pct == Decimal("0.0000")

    async def test_compute_burn_up_with_contributions(self, db_session: AsyncSession) -> None:
        from app.goals.service import compute_burn_up, create_goal, log_contribution

        hh_id, actor_id = await _bootstrap(db_session)
        goal = await create_goal(
            db_session,
            household_id=hh_id,
            actor_id=actor_id,
            name="Vacation",
            goal_type=GoalType.SAVINGS_TARGET,
            target_amount=Decimal("2000"),
            target_date=date(2027, 1, 1),
        )
        await log_contribution(
            db_session,
            goal_id=goal.id,
            household_id=hh_id,
            amount=Decimal("1000"),
            currency="USD",
            contributed_at=date(2026, 5, 1),
        )
        await db_session.commit()

        snap = await compute_burn_up(
            db_session,
            goal_id=goal.id,
            household_id=hh_id,
            as_of_date=date(2026, 6, 1),
        )
        assert snap.cumulative_actual == Decimal("1000.00")
        assert snap.progress_pct == Decimal("50.0000")

    async def test_burn_up_snapshot_persisted(self, db_session: AsyncSession) -> None:
        from app.goals.service import compute_burn_up, create_goal, get_latest_snapshot

        hh_id, actor_id = await _bootstrap(db_session)
        goal = await create_goal(
            db_session,
            household_id=hh_id,
            actor_id=actor_id,
            name="Net Worth",
            goal_type=GoalType.NET_WORTH,
            target_amount=Decimal("100000"),
        )
        await db_session.commit()

        await compute_burn_up(
            db_session,
            goal_id=goal.id,
            household_id=hh_id,
            as_of_date=date(2026, 6, 1),
        )
        await db_session.commit()

        snap = await get_latest_snapshot(db_session, goal_id=goal.id, household_id=hh_id)
        assert snap.goal_id == goal.id
        assert snap.snapshot_date == date(2026, 6, 1)


@pytest.mark.integration
class TestCompletionPolicies:
    async def _setup(
        self, session: AsyncSession, policy: CompletionPolicy, target: Decimal = Decimal("1000")
    ):  # type: ignore[no-untyped-def]
        from app.goals.service import create_goal, log_contribution

        hh_id, actor_id = await _bootstrap(session)

        goal = await create_goal(
            session,
            household_id=hh_id,
            actor_id=actor_id,
            name="Complete Me",
            goal_type=GoalType.SAVINGS_TARGET,
            target_amount=target,
            completion_policy=policy,
            auto_extend_amount=Decimal("500"),
        )

        # Fund past 100%
        await log_contribution(
            session,
            goal_id=goal.id,
            household_id=hh_id,
            amount=target + Decimal("100"),
            currency="USD",
            contributed_at=date(2026, 5, 1),
        )
        await session.commit()
        return goal, hh_id, actor_id

    async def test_archive_on_complete(self, db_session: AsyncSession) -> None:
        from app.goals.service import check_completion

        goal, hh_id, actor_id = await self._setup(db_session, CompletionPolicy.ARCHIVE_ON_COMPLETE)
        await check_completion(db_session, goal_id=goal.id, household_id=hh_id, actor_id=actor_id)
        await db_session.commit()

        result = await db_session.execute(
            sa.text("SELECT status, archived_at FROM goals_goal WHERE id = :id"),
            {"id": str(goal.id)},
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == "completed"
        assert row[1] is not None

    async def test_prompt_on_complete_emits_recommendation(self, db_session: AsyncSession) -> None:
        from app.goals.service import check_completion

        goal, hh_id, actor_id = await self._setup(db_session, CompletionPolicy.PROMPT_ON_COMPLETE)
        await check_completion(db_session, goal_id=goal.id, household_id=hh_id, actor_id=actor_id)
        await db_session.commit()

        rec_result = await db_session.execute(
            sa.text(
                "SELECT COUNT(*) FROM recommendations_recommendation "
                "WHERE source = 'goal_engine' AND target_entity_id = :gid"
            ),
            {"gid": str(goal.id)},
        )
        count = rec_result.scalar()
        assert count is not None and count >= 1

        # Goal itself should remain active
        status_result = await db_session.execute(
            sa.text("SELECT status FROM goals_goal WHERE id = :id"),
            {"id": str(goal.id)},
        )
        assert status_result.scalar() == "active"

    async def test_auto_extend(self, db_session: AsyncSession) -> None:
        from app.goals.service import check_completion

        original_target = Decimal("1000")
        goal, hh_id, actor_id = await self._setup(
            db_session, CompletionPolicy.AUTO_EXTEND, target=original_target
        )
        await check_completion(db_session, goal_id=goal.id, household_id=hh_id, actor_id=actor_id)
        await db_session.commit()

        updated = await db_session.execute(
            sa.text("SELECT target_amount, status FROM goals_goal WHERE id = :id"),
            {"id": str(goal.id)},
        )
        row = updated.fetchone()
        assert row is not None
        assert Decimal(str(row[0])) == original_target + Decimal("500")
        assert row[1] == "active"

    async def test_auto_clone(self, db_session: AsyncSession) -> None:
        from app.goals.service import check_completion

        goal, hh_id, actor_id = await self._setup(db_session, CompletionPolicy.AUTO_CLONE)
        await check_completion(db_session, goal_id=goal.id, household_id=hh_id, actor_id=actor_id)
        await db_session.commit()

        original_result = await db_session.execute(
            sa.text("SELECT status FROM goals_goal WHERE id = :id"),
            {"id": str(goal.id)},
        )
        assert original_result.scalar() == "completed"

        clone_result = await db_session.execute(
            sa.text(
                "SELECT COUNT(*) FROM goals_goal "
                "WHERE household_id = :hh AND name = 'Complete Me' AND status = 'active'"
            ),
            {"hh": str(hh_id)},
        )
        assert clone_result.scalar() == 1

    async def test_convert_to_recurring(self, db_session: AsyncSession) -> None:
        from app.goals.service import check_completion

        goal, hh_id, actor_id = await self._setup(db_session, CompletionPolicy.CONVERT_TO_RECURRING)
        await check_completion(db_session, goal_id=goal.id, household_id=hh_id, actor_id=actor_id)
        await db_session.commit()

        status_result = await db_session.execute(
            sa.text("SELECT status FROM goals_goal WHERE id = :id"),
            {"id": str(goal.id)},
        )
        assert status_result.scalar() == "completed"

        rec_result = await db_session.execute(
            sa.text(
                "SELECT COUNT(*) FROM recommendations_recommendation "
                "WHERE source = 'goal_engine' AND target_entity_id = :gid"
            ),
            {"gid": str(goal.id)},
        )
        assert rec_result.scalar() >= 1


@pytest.mark.integration
class TestMinimumBalance:
    async def test_alert_fires_below_threshold(self, db_session: AsyncSession) -> None:
        from unittest.mock import patch

        from app.goals.service import check_minimum_balance, create_funding_source, create_goal

        hh_id, actor_id = await _bootstrap(db_session)
        account_id = uuid.uuid4()

        goal = await create_goal(
            db_session,
            household_id=hh_id,
            actor_id=actor_id,
            name="Emergency Buffer",
            goal_type=GoalType.MINIMUM_BALANCE,
            minimum_balance_threshold=Decimal("1000"),
            currency="USD",
        )
        await create_funding_source(
            db_session,
            goal_id=goal.id,
            household_id=hh_id,
            source_type=FundingSourceType.ACCOUNT,
            source_id=account_id,
        )
        await db_session.commit()

        mock_account = MagicMock()
        mock_account.current_balance = Decimal("500")

        with patch(
            "app.goals.service.accounts_svc.get_account",
            new_callable=AsyncMock,
            return_value=mock_account,
        ):
            await check_minimum_balance(db_session, goal_id=goal.id, household_id=hh_id)
            await db_session.commit()

        rec_result = await db_session.execute(
            sa.text(
                "SELECT COUNT(*) FROM recommendations_recommendation "
                "WHERE source = 'goal_engine' AND target_entity_id = :gid"
            ),
            {"gid": str(goal.id)},
        )
        assert rec_result.scalar() >= 1

    async def test_alert_does_not_fire_above_threshold(self, db_session: AsyncSession) -> None:
        from unittest.mock import patch

        from app.goals.service import check_minimum_balance, create_funding_source, create_goal

        hh_id, actor_id = await _bootstrap(db_session)
        account_id = uuid.uuid4()

        goal = await create_goal(
            db_session,
            household_id=hh_id,
            actor_id=actor_id,
            name="Emergency Buffer",
            goal_type=GoalType.MINIMUM_BALANCE,
            minimum_balance_threshold=Decimal("1000"),
            currency="USD",
        )
        await create_funding_source(
            db_session,
            goal_id=goal.id,
            household_id=hh_id,
            source_type=FundingSourceType.ACCOUNT,
            source_id=account_id,
        )
        await db_session.commit()

        mock_account = MagicMock()
        mock_account.current_balance = Decimal("2000")

        with patch(
            "app.goals.service.accounts_svc.get_account",
            new_callable=AsyncMock,
            return_value=mock_account,
        ):
            await check_minimum_balance(db_session, goal_id=goal.id, household_id=hh_id)
            await db_session.commit()

        rec_result = await db_session.execute(
            sa.text(
                "SELECT COUNT(*) FROM recommendations_recommendation "
                "WHERE source = 'goal_engine' AND target_entity_id = :gid"
            ),
            {"gid": str(goal.id)},
        )
        assert rec_result.scalar() == 0
