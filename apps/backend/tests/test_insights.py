"""Tests for insights module — Ollama endpoints and provider test service.

Unit tests mock httpx and do not require a database.
Integration tests (marked @pytest.mark.integration) require Postgres via testcontainers.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.insights.providers.ollama import OllamaProvider

# ===========================================================================
# Unit tests — OllamaProvider.is_available()
# ===========================================================================


class TestOllamaProviderIsAvailable:
    @pytest.mark.asyncio
    async def test_returns_true_when_tags_200(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)
        mock_http.get = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_http):
            provider = OllamaProvider(base_url="http://localhost:11434", model_name="llama3")
            result = await provider.is_available()

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_connection_refused(self) -> None:
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)
        mock_http.get = AsyncMock(side_effect=ConnectionRefusedError("refused"))

        with patch("httpx.AsyncClient", return_value=mock_http):
            provider = OllamaProvider(base_url="http://localhost:11434", model_name="llama3")
            result = await provider.is_available()

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_non_200(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 500

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)
        mock_http.get = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_http):
            provider = OllamaProvider(base_url="http://localhost:11434", model_name="llama3")
            result = await provider.is_available()

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_os_error(self) -> None:
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)
        mock_http.get = AsyncMock(side_effect=OSError("network unreachable"))

        with patch("httpx.AsyncClient", return_value=mock_http):
            provider = OllamaProvider(base_url="http://localhost:11434", model_name="llama3")
            result = await provider.is_available()

        assert result is False

    def test_get_model_name_returns_configured_name(self) -> None:
        provider = OllamaProvider(base_url="http://localhost:11434", model_name="mistral")
        assert provider.get_model_name() == "mistral"

    def test_get_model_name_defaults_to_llama(self) -> None:
        provider = OllamaProvider(base_url="http://localhost:11434", model_name="")
        assert provider.get_model_name() == "llama3.2"


# ===========================================================================
# Unit tests — router helpers (via service mock)
# ===========================================================================


class TestTestProviderConfigService:
    @pytest.mark.asyncio
    async def test_returns_available_true_for_reachable_provider(self) -> None:
        from app.insights.service import test_provider_config

        mock_session = AsyncMock(spec=AsyncSession)

        from app.insights.models import InsightProviderConfig

        config = InsightProviderConfig(
            id=uuid.uuid4(),
            household_id=uuid.uuid4(),
            provider="local_ollama",
            priority=0,
            enabled=True,
            base_url="http://localhost:11434",
            model_name="llama3",
            credentials_encrypted=None,
            ai_data_sharing="generalizations_only",
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=config)
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)
        mock_http.get = AsyncMock(return_value=MagicMock(status_code=200))

        with patch("httpx.AsyncClient", return_value=mock_http):
            available, model_name, error = await test_provider_config(
                mock_session,
                config_id=config.id,
                household_id=config.household_id,
                master_key="test-key",
            )

        assert available is True
        assert model_name == "llama3"
        assert error is None

    @pytest.mark.asyncio
    async def test_returns_available_false_for_unreachable_provider(self) -> None:
        from app.insights.service import test_provider_config

        mock_session = AsyncMock(spec=AsyncSession)

        from app.insights.models import InsightProviderConfig

        config = InsightProviderConfig(
            id=uuid.uuid4(),
            household_id=uuid.uuid4(),
            provider="local_ollama",
            priority=0,
            enabled=True,
            base_url="http://localhost:11434",
            model_name="llama3",
            credentials_encrypted=None,
            ai_data_sharing="generalizations_only",
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=config)
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)
        mock_http.get = AsyncMock(side_effect=ConnectionRefusedError("refused"))

        with patch("httpx.AsyncClient", return_value=mock_http):
            available, model_name, error = await test_provider_config(
                mock_session,
                config_id=config.id,
                household_id=config.household_id,
                master_key="test-key",
            )

        assert available is False
        assert model_name is None
        assert error is not None
        assert "http://localhost:11434" in error

    @pytest.mark.asyncio
    async def test_never_raises_on_connection_failure(self) -> None:
        from app.insights.service import test_provider_config

        mock_session = AsyncMock(spec=AsyncSession)

        from app.insights.models import InsightProviderConfig

        config = InsightProviderConfig(
            id=uuid.uuid4(),
            household_id=uuid.uuid4(),
            provider="local_ollama",
            priority=0,
            enabled=True,
            base_url="http://localhost:11434",
            model_name="llama3",
            credentials_encrypted=None,
            ai_data_sharing="generalizations_only",
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=config)
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)
        mock_http.get = AsyncMock(side_effect=RuntimeError("unexpected crash"))

        with patch("httpx.AsyncClient", return_value=mock_http):
            available, _model_name, _error = await test_provider_config(
                mock_session,
                config_id=config.id,
                household_id=config.household_id,
                master_key="test-key",
            )

        assert available is False


# ===========================================================================
# Integration tests — service layer with real DB
# ===========================================================================


pytestmark = pytest.mark.integration


@pytest.mark.integration
class TestInsightsServiceIntegration:
    async def test_create_and_list_provider_config(self, session: AsyncSession) -> None:
        from app.households.enums import VisibilityMode
        from app.households.service import create_household, create_user
        from app.insights.service import create_provider_config, list_provider_configs

        user = await create_user(
            session,
            email=f"insight_{uuid.uuid4().hex[:6]}@test.com",
            display_name="Test",
            password="testpassword1234",  # pragma: allowlist secret
        )
        household = await create_household(
            session,
            name="Test Household",
            visibility_mode=VisibilityMode.FULLY_SHARED,
            home_currency="USD",
            owner=user,
        )

        config = await create_provider_config(
            session,
            household_id=household.id,
            provider="local_ollama",
            priority=0,
            enabled=True,
            base_url="http://ollama:11434",
            model_name="llama3",
            credentials=None,
            ai_data_sharing="generalizations_only",
            master_key="test-master-key-for-tests-only",
            actor_id=user.id,
        )
        await session.flush()

        configs = await list_provider_configs(session, household.id)
        assert len(configs) == 1
        assert configs[0].id == config.id
        assert configs[0].provider == "local_ollama"
        assert configs[0].model_name == "llama3"

    async def test_test_provider_config_returns_result(self, session: AsyncSession) -> None:
        from app.households.enums import VisibilityMode
        from app.households.service import create_household, create_user
        from app.insights.service import create_provider_config, test_provider_config

        user = await create_user(
            session,
            email=f"insight2_{uuid.uuid4().hex[:6]}@test.com",
            display_name="Test2",
            password="testpassword1234",  # pragma: allowlist secret
        )
        household = await create_household(
            session,
            name="Test Household 2",
            visibility_mode=VisibilityMode.FULLY_SHARED,
            home_currency="USD",
            owner=user,
        )
        config = await create_provider_config(
            session,
            household_id=household.id,
            provider="local_ollama",
            priority=0,
            enabled=True,
            base_url="http://ollama-unreachable:11434",
            model_name="llama3",
            credentials=None,
            ai_data_sharing="generalizations_only",
            master_key="test-master-key-for-tests-only",
            actor_id=user.id,
        )
        await session.flush()

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)
        mock_http.get = AsyncMock(side_effect=ConnectionRefusedError("refused"))

        with patch("httpx.AsyncClient", return_value=mock_http):
            available, _model_name, error = await test_provider_config(
                session,
                config_id=config.id,
                household_id=household.id,
                master_key="test-master-key-for-tests-only",
            )

        assert available is False
        assert error is not None
