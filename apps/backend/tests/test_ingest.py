"""Tests for the ingest module.

Unit tests (no DB) cover parsers, encryption, and pipeline helpers.
Integration tests (marked @pytest.mark.integration) require Docker via testcontainers.

Coverage targets (per testing.md): 70%+ line coverage on ingest module.

Hypothesis property tests cover:
  - CSV sign convention both directions
  - OFX posted_date TZ-safety (extracted in source TZ, not UTC-shifted)
  - Pipeline idempotency: same external_id ingested twice → one transaction
  - ImportJob counter invariant: imported + duplicate + error == row_count
  - Fuzzy dedup below threshold → pending row, no auto-merge
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import date
from decimal import Decimal
from typing import ClassVar

import pytest
import sqlalchemy as sa
from hypothesis import given
from hypothesis import strategies as st
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.accounts import service as accounts_service
from app.accounts.enums import AccountType
from app.database import Base
from app.households import service as households_service
from app.households.enums import VisibilityMode
from app.ingest.parsers import ParsedTransaction
from app.ingest.parsers.csv import CsvParseError, _parse_row_amount, parse_csv
from app.ingest.parsers.ofx import _parse_dtposted, parse_ofx
from app.ingest.pipeline import _map_direction, _map_type_hint, run_pipeline
from app.security.encryption import DecryptionError, decrypt_dict, encrypt_dict
from app.transactions.enums import TransactionDirection, TransactionType

# ===========================================================================
# Unit tests — encryption (no DB)
# ===========================================================================


class TestEncryption:
    def test_roundtrip(self) -> None:
        data = {"access_url": "https://token@bridge.simplefin.org/simplefin"}
        token = encrypt_dict(data, "test-master-key")
        assert isinstance(token, str)
        result = decrypt_dict(token, "test-master-key")
        assert result == data

    def test_wrong_key_raises(self) -> None:
        token = encrypt_dict({"x": 1}, "key-a")
        with pytest.raises(DecryptionError):
            decrypt_dict(token, "key-b")

    def test_tampered_token_raises(self) -> None:
        token = encrypt_dict({"x": 1}, "mykey")
        tampered = token[:-4] + "XXXX"
        with pytest.raises(DecryptionError):
            decrypt_dict(tampered, "mykey")

    def test_empty_dict_roundtrip(self) -> None:
        assert decrypt_dict(encrypt_dict({}, "k"), "k") == {}

    def test_nested_values_roundtrip(self) -> None:
        data = {"a": {"b": [1, 2, 3]}, "c": True}
        assert decrypt_dict(encrypt_dict(data, "k"), "k") == data


# ===========================================================================
# Unit tests — OFX parser (no DB)
# ===========================================================================


class TestOfxParser:
    _SGML_SAMPLE = b"""
OFXHEADER:100
DATA:OFXSGML
VERSION:151
<OFX>
<BANKMSGSRSV1>
<STMTTRNRS>
<STMTRS>
<CURDEF>USD
<STMTTRNLIST>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20231215120000[-5:EST]
<TRNAMT>-42.50
<FITID>202312151234
<NAME>WALMART SUPERCENTER
<MEMO>Purchase
</STMTTRN>
<STMTTRN>
<TRNTYPE>DIRECTDEP
<DTPOSTED>20231201080000[-5:EST]
<TRNAMT>2500.00
<FITID>202312011
<NAME>ACME CORP PAYROLL
</STMTTRN>
</STMTTRNLIST>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
"""

    _XML_SAMPLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<OFX>
  <STMTTRNLIST>
    <STMTTRN>
      <TRNTYPE>DEBIT</TRNTYPE>
      <DTPOSTED>20231215230000</DTPOSTED>
      <TRNAMT>-19.99</TRNAMT>
      <FITID>xml-001</FITID>
      <NAME>NETFLIX</NAME>
    </STMTTRN>
  </STMTTRNLIST>
</OFX>
"""

    def test_sgml_parse_count(self) -> None:
        results = parse_ofx(self._SGML_SAMPLE)
        assert len(results) == 2

    def test_sgml_debit_direction(self) -> None:
        results = parse_ofx(self._SGML_SAMPLE)
        debit = next(r for r in results if r.external_id == "202312151234")
        assert debit.direction == "debit"
        assert debit.amount == Decimal("42.50")

    def test_sgml_credit_direction(self) -> None:
        results = parse_ofx(self._SGML_SAMPLE)
        credit = next(r for r in results if r.external_id == "202312011")
        assert credit.direction == "credit"
        assert credit.amount == Decimal("2500.00")

    def test_ofx_date_not_utc_shifted(self) -> None:
        """DTPOSTED date extracted from first 8 chars — no TZ conversion."""
        # DTPOSTED=20231215120000[-5:EST] → date must be 2023-12-15, not shifted
        results = parse_ofx(self._SGML_SAMPLE)
        debit = next(r for r in results if r.external_id == "202312151234")
        assert debit.posted_date == date(2023, 12, 15)

    def test_xml_parse(self) -> None:
        results = parse_ofx(self._XML_SAMPLE)
        assert len(results) == 1
        assert results[0].external_id == "xml-001"
        assert results[0].amount == Decimal("19.99")
        assert results[0].direction == "debit"

    def test_trntype_hint_directdep(self) -> None:
        results = parse_ofx(self._SGML_SAMPLE)
        payroll = next(r for r in results if r.external_id == "202312011")
        assert payroll.transaction_type_hint == "payroll"

    def test_trntype_hint_none_for_debit(self) -> None:
        results = parse_ofx(self._SGML_SAMPLE)
        debit = next(r for r in results if r.external_id == "202312151234")
        assert debit.transaction_type_hint is None

    def test_missing_fitid_skipped(self) -> None:
        content = b"<STMTTRN><DTPOSTED>20231215<TRNAMT>-10.00</STMTTRN>"
        results = parse_ofx(content)
        assert results == []

    def test_missing_trnamt_skipped(self) -> None:
        content = b"<STMTTRN><FITID>X1<DTPOSTED>20231215</STMTTRN>"
        results = parse_ofx(content)
        assert results == []

    def test_late_night_date_preserved(self) -> None:
        """11pm UTC offset date must NOT become next day."""
        raw_date = "20231215230000"
        parsed = _parse_dtposted(raw_date)
        assert parsed == date(2023, 12, 15)

    def test_dtposted_with_tz_suffix_uses_local_date(self) -> None:
        """[-8:PST] suffix must be ignored — only YYYYMMDD extracted."""
        parsed = _parse_dtposted("20231215235900[-8:PST]")
        assert parsed == date(2023, 12, 15)


# ===========================================================================
# Unit tests — CSV parser (no DB)
# ===========================================================================


class TestCsvParser:
    _CONFIG_DEBIT_POSITIVE: ClassVar[dict] = {
        "column_mapping": {
            "date": "Date",
            "amount": "Amount",
            "description": "Description",
            "merchant": "Merchant",
        },
        "date_format": "%Y-%m-%d",
        "amount_sign": "positive_is_debit",
        "default_currency": "USD",
    }

    _CONFIG_CREDIT_POSITIVE: ClassVar[dict] = {
        "column_mapping": {
            "date": "Date",
            "amount": "Amount",
            "description": "Description",
        },
        "date_format": "%m/%d/%Y",
        "amount_sign": "positive_is_credit",
        "default_currency": "USD",
    }

    def _make_csv(self, rows: list[str], header: str = "Date,Amount,Description,Merchant") -> bytes:
        return (header + "\n" + "\n".join(rows)).encode()

    def test_positive_is_debit_positive_amount(self) -> None:
        csv_bytes = self._make_csv(["2023-12-15,42.50,Walmart,Walmart"])
        results = parse_csv(csv_bytes, self._CONFIG_DEBIT_POSITIVE)
        assert len(results) == 1
        assert results[0].direction == "debit"
        assert results[0].amount == Decimal("42.50")

    def test_positive_is_debit_negative_amount(self) -> None:
        csv_bytes = self._make_csv(["2023-12-15,-100.00,Refund,Shop"])
        results = parse_csv(csv_bytes, self._CONFIG_DEBIT_POSITIVE)
        assert results[0].direction == "credit"
        assert results[0].amount == Decimal("100.00")

    def test_positive_is_credit_positive_amount(self) -> None:
        csv_bytes = self._make_csv(
            ["12/01/2023,2500.00,Payroll"],
            header="Date,Amount,Description",
        )
        results = parse_csv(csv_bytes, self._CONFIG_CREDIT_POSITIVE)
        assert results[0].direction == "credit"
        assert results[0].amount == Decimal("2500.00")

    def test_positive_is_credit_negative_amount(self) -> None:
        csv_bytes = self._make_csv(
            ["12/15/2023,-50.00,Grocery"],
            header="Date,Amount,Description",
        )
        results = parse_csv(csv_bytes, self._CONFIG_CREDIT_POSITIVE)
        assert results[0].direction == "debit"
        assert results[0].amount == Decimal("50.00")

    def test_configurable_date_format(self) -> None:
        csv_bytes = self._make_csv(
            ["12/15/2023,10.00,Coffee"],
            header="Date,Amount,Description",
        )
        results = parse_csv(csv_bytes, self._CONFIG_CREDIT_POSITIVE)
        assert results[0].posted_date == date(2023, 12, 15)

    def test_empty_rows_skipped(self) -> None:
        csv_bytes = self._make_csv(["", "2023-12-15,10.00,Coffee,Starbucks"])
        results = parse_csv(csv_bytes, self._CONFIG_DEBIT_POSITIVE)
        assert len(results) == 1

    def test_missing_required_column_raises(self) -> None:
        bad_config = {
            "column_mapping": {"date": "Date", "amount": "Amount"},  # missing description
            "date_format": "%Y-%m-%d",
            "amount_sign": "positive_is_debit",
        }
        with pytest.raises(CsvParseError):
            parse_csv(b"Date,Amount\n2023-01-01,10.00", bad_config)

    def test_amounts_with_commas_parsed(self) -> None:
        csv_bytes = self._make_csv(['2023-12-15,"1,234.56",BigPurchase,Shop'])
        results = parse_csv(csv_bytes, self._CONFIG_DEBIT_POSITIVE)
        assert results[0].amount == Decimal("1234.56")

    def test_stable_external_id_idempotent(self) -> None:
        """Same CSV row produces same external_id across runs."""
        csv_bytes = self._make_csv(["2023-12-15,42.50,Walmart,Walmart"])
        r1 = parse_csv(csv_bytes, self._CONFIG_DEBIT_POSITIVE)
        r2 = parse_csv(csv_bytes, self._CONFIG_DEBIT_POSITIVE)
        assert r1[0].external_id == r2[0].external_id


# ===========================================================================
# Property-based tests — pure helpers
# ===========================================================================


_pos_decimal = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("99999.9999"),
    places=4,
    allow_nan=False,
    allow_infinity=False,
)


class TestAmountSignConventionProperty:
    @given(amount=_pos_decimal)
    def test_positive_is_debit_round_trips(self, amount: Decimal) -> None:
        raw = str(amount)
        parsed_amount, direction = _parse_row_amount(raw, "positive_is_debit")
        assert direction == "debit"
        assert parsed_amount == amount

    @given(amount=_pos_decimal)
    def test_positive_is_credit_round_trips(self, amount: Decimal) -> None:
        raw = str(amount)
        parsed_amount, direction = _parse_row_amount(raw, "positive_is_credit")
        assert direction == "credit"
        assert parsed_amount == amount

    @given(amount=_pos_decimal)
    def test_negative_positive_is_debit_gives_credit(self, amount: Decimal) -> None:
        raw = "-" + str(amount)
        parsed_amount, direction = _parse_row_amount(raw, "positive_is_debit")
        assert direction == "credit"
        assert parsed_amount == amount

    @given(amount=_pos_decimal)
    def test_negative_positive_is_credit_gives_debit(self, amount: Decimal) -> None:
        raw = "-" + str(amount)
        parsed_amount, direction = _parse_row_amount(raw, "positive_is_credit")
        assert direction == "debit"
        assert parsed_amount == amount


# ===========================================================================
# Unit tests — pipeline helpers (no DB)
# ===========================================================================


class TestPipelineHelpers:
    def test_map_direction_debit(self) -> None:
        assert _map_direction("debit") == TransactionDirection.DEBIT

    def test_map_direction_credit(self) -> None:
        assert _map_direction("credit") == TransactionDirection.CREDIT

    def test_map_direction_default_debit(self) -> None:
        assert _map_direction("unknown") == TransactionDirection.DEBIT

    def test_map_type_hint_none(self) -> None:
        assert _map_type_hint(None) is None

    def test_map_type_hint_valid(self) -> None:
        assert _map_type_hint("payroll") == TransactionType.PAYROLL

    def test_map_type_hint_unknown_returns_none(self) -> None:
        assert _map_type_hint("bogus_type") is None


# ===========================================================================
# Integration tests — require Postgres (testcontainers)
# ===========================================================================


@pytest.fixture()
async def ingest_db(
    postgres_url: str,
) -> AsyncGenerator[tuple[object, async_sessionmaker[AsyncSession]], None]:

    engine = create_async_engine(postgres_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield engine, factory

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _seed_household_and_account(
    session: AsyncSession,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Create a household, user, and account. Returns (household_id, user_id, account_id)."""
    user = await households_service.create_user(
        session,
        email="test@example.com",
        display_name="Tester",
        password="testpassword1",  # pragma: allowlist secret
    )
    hh = await households_service.create_household(
        session,
        name="Test HH",
        visibility_mode=VisibilityMode.FULLY_SHARED,
        home_currency="USD",
        owner=user,
    )
    account = await accounts_service.create_account(
        session,
        household_id=hh.id,
        actor_id=user.id,
        name="Checking",
        institution=None,
        account_type=AccountType.CHECKING,
        currency="USD",
        current_balance=Decimal("0"),
    )
    return hh.id, user.id, account.id


@pytest.mark.integration
async def test_pipeline_idempotency(ingest_db: tuple) -> None:
    """Same external_id ingested twice → one transaction, second counted as duplicate."""
    from app.ingest import service
    from app.ingest.enums import ImportSource

    _engine, factory = ingest_db

    async with factory() as session:
        hh_id, _user_id, acc_id = await _seed_household_and_account(session)
        await session.commit()

    pt = ParsedTransaction(
        external_id="dedup-test-001",
        amount=Decimal("50.00"),
        currency="USD",
        direction="debit",
        posted_date=date(2024, 1, 15),
        occurred_at=date(2024, 1, 15),
        description="Test Store",
    )

    async with factory() as session:
        job1 = await service.create_import_job(
            session, household_id=hh_id, source=ImportSource.CSV_UPLOAD
        )
        await session.commit()

    result1 = await run_pipeline(
        factory,
        parsed=[pt],
        import_job_id=job1.id,
        household_id=hh_id,
        account_id=acc_id,
        source="csv_upload",
    )

    async with factory() as session:
        job2 = await service.create_import_job(
            session, household_id=hh_id, source=ImportSource.CSV_UPLOAD
        )
        await session.commit()

    result2 = await run_pipeline(
        factory,
        parsed=[pt],
        import_job_id=job2.id,
        household_id=hh_id,
        account_id=acc_id,
        source="csv_upload",
    )

    assert result1.imported == 1
    assert result1.duplicate == 0
    assert result2.imported == 0
    assert result2.duplicate == 1


@pytest.mark.integration
async def test_import_job_counter_invariant(ingest_db: tuple) -> None:
    """imported + duplicate + error always sums to row_count (number of parsed rows)."""
    from app.ingest import service
    from app.ingest.enums import ImportSource

    _engine, factory = ingest_db

    async with factory() as session:
        hh_id, _user_id, acc_id = await _seed_household_and_account(session)
        await session.commit()

    pt1 = ParsedTransaction(
        external_id="counter-test-001",
        amount=Decimal("10.00"),
        currency="USD",
        direction="debit",
        posted_date=date(2024, 2, 1),
        occurred_at=date(2024, 2, 1),
        description="Coffee",
    )
    pt2 = ParsedTransaction(
        external_id="counter-test-001",  # duplicate external_id
        amount=Decimal("10.00"),
        currency="USD",
        direction="debit",
        posted_date=date(2024, 2, 1),
        occurred_at=date(2024, 2, 1),
        description="Coffee",
    )

    async with factory() as session:
        job = await service.create_import_job(
            session, household_id=hh_id, source=ImportSource.CSV_UPLOAD
        )
        await session.commit()

    result = await run_pipeline(
        factory,
        parsed=[pt1, pt2],
        import_job_id=job.id,
        household_id=hh_id,
        account_id=acc_id,
        source="csv_upload",
    )

    total = result.imported + result.duplicate + result.errors
    assert total == 2, f"expected 2 but got {total}"
    assert result.imported == 1
    assert result.duplicate == 1


@pytest.mark.integration
async def test_fuzzy_dedup_creates_hitl_row(ingest_db: tuple) -> None:
    """Fuzzy-match below threshold creates a Recommendation row (not auto-merged)."""
    from app.ingest import service
    from app.ingest.enums import ImportSource
    from app.recommendations.enums import RecommendationSource
    from app.recommendations.models import Recommendation
    from app.transactions import service as tx_service
    from app.transactions.enums import TransactionState

    _engine, factory = ingest_db

    async with factory() as session:
        hh_id, user_id, acc_id = await _seed_household_and_account(session)
        await session.commit()

    # Create an existing transaction (not via pipeline — bypasses dedup)
    async with factory() as session:
        await tx_service.create_transaction(
            session,
            household_id=hh_id,
            account_id=acc_id,
            actor_id=user_id,
            amount=Decimal("25.00"),
            currency="USD",
            direction=TransactionDirection.DEBIT,
            transaction_type=None,
            state=TransactionState.POSTED,
            posted_date=date(2024, 3, 1),
            pending_date=None,
            occurred_at=date(2024, 3, 1),
            description="WHOLE FOODS MARKET",
            external_id="existing-fuzzy-001",
        )
        await session.commit()

    # Ingest a similar transaction without external_id so fuzzy matching kicks in
    pt = ParsedTransaction(
        external_id=None,
        amount=Decimal("25.00"),
        currency="USD",
        direction="debit",
        posted_date=date(2024, 3, 1),
        occurred_at=date(2024, 3, 1),
        description="WHOLE FOODS MARKET 1234",
    )

    async with factory() as session:
        job = await service.create_import_job(
            session, household_id=hh_id, source=ImportSource.CSV_UPLOAD
        )
        await session.commit()

    result = await run_pipeline(
        factory,
        parsed=[pt],
        import_job_id=job.id,
        household_id=hh_id,
        account_id=acc_id,
        source="csv_upload",
    )

    # Transaction imported (source != "simplefin" so no auto-merge)
    assert result.imported == 1

    async with factory() as session:
        recs_result = await session.execute(
            sa.select(Recommendation).where(
                Recommendation.household_id == hh_id,
                Recommendation.source == str(RecommendationSource.INGEST),
            )
        )
        pending = list(recs_result.scalars().all())
        assert len(pending) >= 1


@pytest.mark.integration
async def test_sync_config_credential_encryption(ingest_db: tuple) -> None:
    """Credentials stored encrypted; decryption succeeds with correct key."""
    from app.ingest import service as ingest_service
    from app.ingest.enums import IngestProvider

    _engine, factory = ingest_db

    async with factory() as session:
        hh_id, _user_id, _acc_id = await _seed_household_and_account(session)
        await session.commit()

    plaintext_creds = {"access_url": "https://secret-token@bridge.simplefin.org/simplefin"}

    async with factory() as session:
        config = await ingest_service.create_sync_config(
            session,
            household_id=hh_id,
            provider=IngestProvider.SIMPLEFIN,
            credentials=plaintext_creds,
            master_key="test-master-key",
        )
        await session.commit()
        config_id = config.id

    async with factory() as session:
        loaded = await ingest_service.get_sync_config(
            session, config_id=config_id, household_id=hh_id
        )
        # Raw column must NOT contain plaintext
        assert "secret-token" not in str(loaded.credentials)
        assert "_enc" in loaded.credentials

        # Decryption with correct key must succeed
        decrypted = ingest_service.get_credentials(loaded, "test-master-key")
        assert decrypted == plaintext_creds
