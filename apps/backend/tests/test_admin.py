"""Integration tests for the admin module.

Requires a real Postgres + Redis instance (via testcontainers). Run with:
    pytest -m integration tests/test_admin.py

Coverage targets (85%+ line coverage):
  - Read-only middleware: POST blocked, GET passes, admin/auth exemptions, Redis fallback
  - User management: demote last admin -> 409, delete last admin -> 409
  - assign_household: membership created, SSE emitted
  - Read-only state: set true -> Redis updated, SSE broadcast; set false -> Redis cleared
  - SMTP: upsert encrypts, get decrypts, smtp_configured, test_smtp
  - Backup: trigger -> BackupRun created, run_backup_job success/failure
  - Registration settings: update writes admin_setting, read merges env+DB
"""

from __future__ import annotations

import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.admin.models  # noqa: F401
from app.database import Base

_MASTER_KEY = "test-master-key-not-for-production"  # pragma: allowlist secret
_JWT_SECRET = "test-jwt-secret-not-for-production"  # pragma: allowlist secret

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Session fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
async def session(postgres_url: str) -> AsyncSession:  # type: ignore[misc]
    engine = create_async_engine(postgres_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_admin(session: AsyncSession, email: str = "admin@example.com") -> Any:
    from app.households import service as hh_service

    user = await hh_service.create_user(
        session,
        email=email,
        display_name="Admin",
        password="hunter2hunter2",  # pragma: allowlist secret
        is_app_admin=True,
    )
    await session.commit()
    return user


async def _make_user(session: AsyncSession, email: str = "user@example.com") -> Any:
    from app.households import service as hh_service

    user = await hh_service.create_user(
        session,
        email=email,
        display_name="User",
        password="hunter2hunter2",  # pragma: allowlist secret
    )
    await session.commit()
    return user


async def _make_household(session: AsyncSession, owner: Any) -> Any:
    from app.households import service as hh_service
    from app.households.enums import VisibilityMode

    hh = await hh_service.create_household(
        session,
        name="Test HH",
        visibility_mode=VisibilityMode.FULLY_SHARED,
        home_currency="USD",
        owner=owner,
    )
    await session.commit()
    return hh


# ---------------------------------------------------------------------------
# Read-only state
# ---------------------------------------------------------------------------


class TestReadOnlyState:
    async def test_get_read_only_state_default(self, session: AsyncSession) -> None:
        from app.admin.service import get_read_only_state

        row = await get_read_only_state(session)
        assert row.enabled is False
        assert row.reason is None

    async def test_set_read_only_true_writes_db_and_redis(self, session: AsyncSession) -> None:
        from app.admin.service import set_read_only

        admin = await _make_admin(session)

        redis_data: dict[str, Any] = {}

        class FakeRedis:
            async def get(self, key: str) -> str | None:
                return redis_data.get(key)

            async def set(self, key: str, value: str) -> None:
                redis_data[key] = value

            async def delete(self, key: str) -> None:
                redis_data.pop(key, None)

            async def aclose(self) -> None:
                pass

        fake_sse = AsyncMock()
        fake_sse.broadcast = AsyncMock()

        with (
            patch("app.admin.service.get_sse_manager", return_value=fake_sse),
            patch("redis.asyncio.from_url", return_value=FakeRedis()),
        ):
            row = await set_read_only(
                session,
                enabled=True,
                reason="maintenance window",
                enabled_by_id=admin.id,
            )

        assert row.enabled is True
        assert row.reason == "maintenance window"
        assert "system:read_only_state" in redis_data
        cached = json.loads(redis_data["system:read_only_state"])
        assert cached["enabled"] is True

        fake_sse.broadcast.assert_called_once_with(
            "read_only_changed",
            {"enabled": True, "reason": "maintenance window"},
        )

    async def test_set_read_only_false_clears_redis(self, session: AsyncSession) -> None:
        from app.admin.service import set_read_only

        admin = await _make_admin(session)
        redis_data: dict[str, Any] = {"system:read_only_state": '{"enabled": true}'}

        class FakeRedis:
            async def get(self, key: str) -> str | None:
                return redis_data.get(key)

            async def set(self, key: str, value: str) -> None:
                redis_data[key] = value

            async def delete(self, key: str) -> None:
                redis_data.pop(key, None)

            async def aclose(self) -> None:
                pass

        fake_sse = AsyncMock()
        fake_sse.broadcast = AsyncMock()

        with (
            patch("app.admin.service.get_sse_manager", return_value=fake_sse),
            patch("redis.asyncio.from_url", return_value=FakeRedis()),
        ):
            row = await set_read_only(
                session,
                enabled=False,
                reason=None,
                enabled_by_id=admin.id,
            )

        assert row.enabled is False
        assert "system:read_only_state" not in redis_data


# ---------------------------------------------------------------------------
# Read-only middleware
# ---------------------------------------------------------------------------


class TestReadOnlyMiddleware:
    def _make_middleware(
        self,
        redis_enabled: bool = True,
        redis_available: bool = True,
        db_enabled: bool = False,
    ) -> Any:
        from app.admin.middleware import ReadOnlyMiddleware

        class FakeApp:
            pass

        mw = ReadOnlyMiddleware(FakeApp())  # type: ignore[arg-type]
        return mw

    async def test_get_request_always_passes(self) -> None:
        from app.admin.middleware import ReadOnlyMiddleware

        async def fake_call_next(req: Any) -> str:
            return "ok"

        class FakeRequest:
            method = "GET"
            url = MagicMock()

        mw = ReadOnlyMiddleware(MagicMock())
        result = await mw.dispatch(FakeRequest(), fake_call_next)  # type: ignore[arg-type]
        assert result == "ok"

    async def test_post_blocked_when_read_only_enabled(self) -> None:
        from app.admin.middleware import ReadOnlyMiddleware

        class FakeRequest:
            method = "POST"
            url = MagicMock()
            url.path = "/api/v1/transactions/something"

        async def fake_call_next(req: Any) -> str:
            return "ok"

        mw = ReadOnlyMiddleware(MagicMock())

        redis_data = {"system:read_only_state": json.dumps({"enabled": True, "reason": "test"})}

        class FakeRedis:
            async def get(self, key: str) -> str | None:
                return redis_data.get(key)

            async def aclose(self) -> None:
                pass

        with patch("redis.asyncio.from_url", return_value=FakeRedis()):
            from app.config import get_settings as _get_settings

            with patch(
                "app.admin.middleware.get_settings",
                return_value=_get_settings().__class__.model_construct(
                    redis_url="redis://localhost"
                ),
            ):
                pass

        with patch.object(mw, "_check_read_only", return_value=(True, "test reason")):
            response = await mw.dispatch(FakeRequest(), fake_call_next)  # type: ignore[arg-type]

        assert hasattr(response, "status_code")
        assert response.status_code == 503

    async def test_admin_path_exempt(self) -> None:
        from app.admin.middleware import ReadOnlyMiddleware

        class FakeRequest:
            method = "POST"
            url = MagicMock()
            url.path = "/api/v1/admin/emergency/read-only"

        async def fake_call_next(req: Any) -> str:
            return "ok"

        mw = ReadOnlyMiddleware(MagicMock())
        with patch.object(mw, "_check_read_only", return_value=(True, "test")):
            result = await mw.dispatch(FakeRequest(), fake_call_next)  # type: ignore[arg-type]
        assert result == "ok"

    async def test_auth_path_exempt(self) -> None:
        from app.admin.middleware import ReadOnlyMiddleware

        class FakeRequest:
            method = "POST"
            url = MagicMock()
            url.path = "/api/v1/auth/login"

        async def fake_call_next(req: Any) -> str:
            return "ok"

        mw = ReadOnlyMiddleware(MagicMock())
        with patch.object(mw, "_check_read_only", return_value=(True, "test")):
            result = await mw.dispatch(FakeRequest(), fake_call_next)  # type: ignore[arg-type]
        assert result == "ok"

    async def test_redis_unavailable_falls_back_to_db(self, session: AsyncSession) -> None:
        from app.admin.middleware import ReadOnlyMiddleware
        from app.admin.service import get_read_only_state

        row = await get_read_only_state(session)
        row.enabled = False
        await session.flush()

        mw = ReadOnlyMiddleware(MagicMock())

        with patch("redis.asyncio.from_url", side_effect=Exception("redis down")):
            with patch("app.database.get_session_factory") as mock_factory:
                mock_session = AsyncMock()
                mock_session.__aenter__ = AsyncMock(return_value=session)
                mock_session.__aexit__ = AsyncMock(return_value=None)
                mock_factory.return_value.return_value = mock_session
                enabled, _reason = await mw._check_read_only(MagicMock())  # type: ignore[arg-type]

        assert enabled is False


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------


class TestUserManagement:
    async def test_demote_last_admin_raises(self, session: AsyncSession) -> None:
        from app.admin.service import LastAdminError, demote_user

        admin = await _make_admin(session)
        with pytest.raises(LastAdminError):
            await demote_user(session, admin.id, by_id=admin.id)

    async def test_demote_non_last_admin_succeeds(self, session: AsyncSession) -> None:
        from app.admin import service as admin_service
        from app.households import service as hh_service

        admin1 = await _make_admin(session, email="admin1@example.com")
        admin2 = await hh_service.create_user(
            session,
            email="admin2@example.com",
            display_name="Admin2",
            password="pw12345678",  # pragma: allowlist secret
            is_app_admin=True,
        )
        await session.commit()

        await admin_service.demote_user(session, admin2.id, by_id=admin1.id)
        await session.commit()

        import sqlalchemy as sa

        from app.households.models import User

        result = await session.execute(sa.select(User).where(User.id == admin2.id))
        updated = result.scalar_one()
        assert updated.is_app_admin is False

    async def test_delete_last_admin_raises(self, session: AsyncSession) -> None:
        from app.admin.service import LastAdminError, delete_user

        admin = await _make_admin(session)
        with pytest.raises(LastAdminError):
            await delete_user(session, admin.id, by_id=admin.id)

    async def test_delete_user_nulls_attributed_to(self, session: AsyncSession) -> None:
        """Ensure attributed_to_user_id is nulled on split allocations."""
        import sqlalchemy as sa

        from app.admin.service import delete_user

        admin = await _make_admin(session)
        user = await _make_user(session)
        hh = await _make_household(session, admin)

        # Insert a fake split allocation referencing user
        await session.execute(
            sa.text(
                "INSERT INTO transactions_split_allocation "
                "(id, split_id, household_id, amount, currency, attributed_to_user_id) "
                "VALUES (:id, :split_id, :hh_id, 10, 'USD', :user_id)"
            ),
            {
                "id": str(uuid.uuid4()),
                "split_id": str(uuid.uuid4()),
                "hh_id": str(hh.id),
                "user_id": str(user.id),
            },
        )
        await session.flush()

        await delete_user(session, user_id=user.id, by_id=admin.id)
        await session.commit()

        result = await session.execute(
            sa.text(
                "SELECT attributed_to_user_id FROM transactions_split_allocation "
                "WHERE attributed_to_user_id = :uid"
            ),
            {"uid": str(user.id)},
        )
        rows = result.fetchall()
        assert len(rows) == 0

    async def test_assign_household_creates_membership(self, session: AsyncSession) -> None:
        import sqlalchemy as sa

        from app.admin.service import assign_household
        from app.households.models import HouseholdMembership

        admin = await _make_admin(session)
        user = await _make_user(session)
        hh = await _make_household(session, admin)

        fake_sse = AsyncMock()
        fake_sse.send_to_user = AsyncMock()

        with patch("app.admin.service.get_sse_manager", return_value=fake_sse):
            await assign_household(
                session,
                user_id=user.id,
                household_id=hh.id,
                role="member",
                by_id=admin.id,
            )
        await session.commit()

        result = await session.execute(
            sa.select(HouseholdMembership).where(
                HouseholdMembership.user_id == user.id,
                HouseholdMembership.household_id == hh.id,
            )
        )
        membership = result.scalar_one_or_none()
        assert membership is not None

        fake_sse.send_to_user.assert_called_once()
        call_args = fake_sse.send_to_user.call_args
        assert call_args[0][0] == user.id
        assert call_args[0][1] == "household_assigned"


# ---------------------------------------------------------------------------
# SMTP
# ---------------------------------------------------------------------------


class TestSMTP:
    async def test_upsert_encrypts_credentials(self, session: AsyncSession) -> None:
        from app.admin.service import decrypt_field, upsert_smtp_config

        admin = await _make_admin(session)

        with patch(
            "app.admin.service.get_settings", return_value=MagicMock(master_key=_MASTER_KEY)
        ):
            cfg = await upsert_smtp_config(
                session,
                host="smtp.example.com",
                port=587,
                username="user@example.com",
                password="secret123",  # pragma: allowlist secret
                from_address="noreply@example.com",
                use_tls=True,
                configured_by_id=admin.id,
            )

        assert cfg.host_enc != "smtp.example.com"
        assert cfg.password_enc != "secret123"  # pragma: allowlist secret

        host = decrypt_field(cfg.host_enc, _MASTER_KEY)
        assert host == "smtp.example.com"

    async def test_get_smtp_config_none_when_not_configured(self, session: AsyncSession) -> None:
        from app.admin.service import get_smtp_config

        cfg = await get_smtp_config(session)
        assert cfg is None

    async def test_smtp_configured_false_when_no_row(self, session: AsyncSession) -> None:
        from app.admin.service import smtp_configured

        result = await smtp_configured(session)
        assert result is False

    async def test_smtp_configured_true_after_upsert(self, session: AsyncSession) -> None:
        from app.admin.service import smtp_configured, upsert_smtp_config

        admin = await _make_admin(session)
        with patch(
            "app.admin.service.get_settings", return_value=MagicMock(master_key=_MASTER_KEY)
        ):
            await upsert_smtp_config(
                session,
                host="smtp.test.com",
                port=587,
                username="u",
                password="p",  # pragma: allowlist secret
                from_address="f@test.com",
                use_tls=True,
                configured_by_id=admin.id,
            )
        assert await smtp_configured(session) is True

    async def test_send_email_returns_false_when_not_configured(
        self, session: AsyncSession
    ) -> None:
        from app.admin.service import send_email

        success, error = await send_email(
            session,
            to="x@example.com",
            subject="Test",
            body_text="Body",
        )
        assert success is False
        assert error is not None


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------


class TestBackup:
    async def test_trigger_backup_creates_run(self, session: AsyncSession) -> None:
        from app.admin.enums import BackupStatus
        from app.admin.service import trigger_backup

        admin = await _make_admin(session)

        mock_pool = AsyncMock()
        mock_pool.enqueue_job = AsyncMock()
        mock_pool.aclose = AsyncMock()

        with patch("app.admin.service.create_pool", return_value=mock_pool):
            with patch("app.admin.service.RedisSettings"):
                run = await trigger_backup(session, triggered_by_id=admin.id)

        assert run.status == BackupStatus.RUNNING
        assert run.triggered_by_id == admin.id
        mock_pool.enqueue_job.assert_called_once()

    async def test_run_backup_job_success(self, session: AsyncSession, tmp_path: Any) -> None:
        """run_backup_job sets status=success on success."""
        import sqlalchemy as sa

        from app.admin.enums import BackupStatus, BackupTrigger
        from app.admin.jobs import run_backup_job
        from app.admin.models import BackupRun

        run = BackupRun(
            triggered_by=BackupTrigger.MANUAL,
            triggered_by_id=None,
            status=BackupStatus.RUNNING,
        )
        session.add(run)
        await session.commit()
        run_id = run.id

        call_count = {"n": 0}
        original_session = session

        def fake_factory() -> Any:
            class FakeSession:
                async def __aenter__(self) -> AsyncSession:
                    call_count["n"] += 1
                    return original_session

                async def __aexit__(self, *_: Any) -> None:
                    pass

            class FakeFactory:
                def __call__(self) -> FakeSession:
                    return FakeSession()

            return FakeFactory()

        with (
            patch("app.admin.jobs._BACKUP_DIR", tmp_path),
            patch("app.admin.jobs.subprocess.run") as mock_run,
            patch("app.database.get_session_factory", return_value=fake_factory()),
            patch(
                "app.admin.jobs.get_settings",
                return_value=MagicMock(
                    database_url="postgresql+asyncpg://x",
                    redis_url="redis://localhost",
                    master_key=_MASTER_KEY,
                ),
            ),
        ):
            mock_run.return_value = MagicMock(stdout=b"-- SQL dump content")
            await run_backup_job({}, backup_run_id=str(run_id))

        result = await session.execute(sa.select(BackupRun).where(BackupRun.id == run_id))
        updated_run = result.scalar_one()
        assert updated_run.status == BackupStatus.SUCCESS

    async def test_run_backup_job_failure_enqueues_notification(
        self, session: AsyncSession, tmp_path: Any
    ) -> None:
        import sqlalchemy as sa

        from app.admin.enums import BackupStatus, BackupTrigger
        from app.admin.jobs import run_backup_job
        from app.admin.models import BackupRun

        run = BackupRun(
            triggered_by=BackupTrigger.MANUAL,
            triggered_by_id=None,
            status=BackupStatus.RUNNING,
        )
        session.add(run)
        await session.commit()
        run_id = run.id

        mock_pool = AsyncMock()
        mock_pool.enqueue_job = AsyncMock()
        mock_pool.aclose = AsyncMock()

        original_session = session

        def fake_factory() -> Any:
            class FakeSession:
                async def __aenter__(self) -> AsyncSession:
                    return original_session

                async def __aexit__(self, *_: Any) -> None:
                    pass

            class FakeFactory:
                def __call__(self) -> FakeSession:
                    return FakeSession()

            return FakeFactory()

        with (
            patch("app.admin.jobs._BACKUP_DIR", tmp_path),
            patch("app.admin.jobs.subprocess.run", side_effect=Exception("pg_dump not found")),
            patch("app.database.get_session_factory", return_value=fake_factory()),
            patch(
                "app.admin.jobs.get_settings",
                return_value=MagicMock(
                    database_url="postgresql+asyncpg://x",
                    redis_url="redis://localhost",
                    master_key=_MASTER_KEY,
                ),
            ),
            patch("app.admin.jobs._get_pool", return_value=mock_pool),
        ):
            await run_backup_job({}, backup_run_id=str(run_id))

        result = await session.execute(sa.select(BackupRun).where(BackupRun.id == run_id))
        updated_run = result.scalar_one()
        assert updated_run.status == BackupStatus.FAILED
        mock_pool.enqueue_job.assert_called_once()


# ---------------------------------------------------------------------------
# Registration settings
# ---------------------------------------------------------------------------


class TestRegistrationSettings:
    async def test_update_registration_settings_writes_db(self, session: AsyncSession) -> None:
        from unittest.mock import MagicMock

        from app.admin.service import get_registration_settings, update_registration_settings

        admin = await _make_admin(session)

        mock_settings = MagicMock()
        mock_settings.allow_registration = False
        mock_settings.registration_limit = None
        mock_settings.unassigned_account_ttl_days = 7

        with patch("app.admin.service.get_settings", return_value=mock_settings):
            await update_registration_settings(
                session,
                allow_registration=True,
                registration_limit=50,
                unassigned_account_ttl_days=14,
                updated_by_id=admin.id,
            )
            await session.commit()

            result = await get_registration_settings(session)

        assert result["allow_registration"] is True
        assert result["registration_limit"] == 50
        assert result["unassigned_account_ttl_days"] == 14

    async def test_register_user_reads_db_override(self, session: AsyncSession) -> None:
        """register_user uses DB override over env var."""
        from app.admin.service import update_registration_settings
        from app.households import service as hh_service

        admin = await _make_admin(session)

        mock_settings = MagicMock()
        mock_settings.allow_registration = False
        mock_settings.registration_limit = None
        mock_settings.unassigned_account_ttl_days = 7

        with patch("app.admin.service.get_settings", return_value=mock_settings):
            await update_registration_settings(
                session,
                allow_registration=True,
                registration_limit=None,
                unassigned_account_ttl_days=7,
                updated_by_id=admin.id,
            )
            await session.commit()

        with patch("app.households.service.get_settings", return_value=mock_settings):
            user = await hh_service.register_user(
                session,
                email="new@example.com",
                display_name="New",
                password="hunter2hunter2",  # pragma: allowlist secret
            )

        assert user.email == "new@example.com"

    async def test_register_user_blocked_by_db_override(self, session: AsyncSession) -> None:
        """register_user respects DB override setting allow_registration=false."""
        from app.admin.service import update_registration_settings
        from app.households import service as hh_service

        admin = await _make_admin(session)

        mock_settings = MagicMock()
        mock_settings.allow_registration = True
        mock_settings.registration_limit = None
        mock_settings.unassigned_account_ttl_days = 7

        with patch("app.admin.service.get_settings", return_value=mock_settings):
            await update_registration_settings(
                session,
                allow_registration=False,
                registration_limit=None,
                unassigned_account_ttl_days=7,
                updated_by_id=admin.id,
            )
            await session.commit()

        with patch("app.households.service.get_settings", return_value=mock_settings):
            with pytest.raises(hh_service.RegistrationClosedError):
                await hh_service.register_user(
                    session,
                    email="blocked@example.com",
                    display_name="Blocked",
                    password="hunter2hunter2",  # pragma: allowlist secret
                )


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


class TestNotifications:
    async def test_create_and_list_notification(self, session: AsyncSession) -> None:
        from app.admin.enums import NotificationType
        from app.admin.service import create_notification, list_notifications

        notif = await create_notification(
            session,
            notification_type=NotificationType.SYSTEM_ERROR,
            title="Test alert",
            body="Something went wrong",
        )
        await session.commit()

        rows, _cursor = await list_notifications(session)
        assert len(rows) >= 1
        assert any(r.id == notif.id for r in rows)

    async def test_mark_read(self, session: AsyncSession) -> None:
        from app.admin.enums import NotificationType
        from app.admin.service import create_notification, mark_read

        notif = await create_notification(
            session,
            notification_type=NotificationType.BACKUP_FAILED,
            title="Backup failed",
            body="Details",
        )
        await session.commit()

        updated = await mark_read(session, notif.id)
        assert updated.read is True
        assert updated.read_at is not None

    async def test_mark_all_read(self, session: AsyncSession) -> None:
        from app.admin.enums import NotificationType
        from app.admin.service import create_notification, list_notifications, mark_all_read

        await create_notification(
            session,
            notification_type=NotificationType.SYSTEM_ERROR,
            title="A",
            body="B",
        )
        await create_notification(
            session,
            notification_type=NotificationType.BACKUP_FAILED,
            title="C",
            body="D",
        )
        await session.commit()

        await mark_all_read(session)
        await session.commit()

        rows, _ = await list_notifications(session, read=False)
        assert len(rows) == 0


# ---------------------------------------------------------------------------
# SSE connection manager
# ---------------------------------------------------------------------------


class TestSSEManager:
    async def test_broadcast_reaches_all_connections(self) -> None:
        from app.households.sse import SSEConnectionManager

        mgr = SSEConnectionManager()
        uid1 = uuid.uuid4()
        uid2 = uuid.uuid4()

        received: list[tuple[uuid.UUID, str]] = []

        import asyncio

        async def _listen(user_id: uuid.UUID) -> None:
            async with mgr.connect(user_id) as queue:
                chunk = await asyncio.wait_for(queue.get(), timeout=1.0)
                received.append((user_id, chunk))

        t1 = asyncio.create_task(_listen(uid1))
        t2 = asyncio.create_task(_listen(uid2))
        await asyncio.sleep(0)

        await mgr.broadcast("read_only_changed", {"enabled": True})

        await t1
        await t2

        assert len(received) == 2
        for _uid, chunk in received:
            assert "read_only_changed" in chunk

    async def test_send_to_user_reaches_only_target(self) -> None:
        import asyncio

        from app.households.sse import SSEConnectionManager

        mgr = SSEConnectionManager()
        uid1 = uuid.uuid4()
        uid2 = uuid.uuid4()

        received: list[tuple[uuid.UUID, str]] = []
        q2_received: list[str] = []

        async with mgr.connect(uid1) as q1:
            async with mgr.connect(uid2) as q2:
                await mgr.send_to_user(uid1, "household_assigned", {"household_id": "abc"})
                await asyncio.sleep(0)

                if not q1.empty():
                    received.append((uid1, await q1.get()))
                if not q2.empty():
                    q2_received.append(await q2.get())

        assert len(received) == 1
        assert "household_assigned" in received[0][1]
        assert len(q2_received) == 0
