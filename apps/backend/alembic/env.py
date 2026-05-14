"""Alembic migration environment — async SQLAlchemy 2.0."""

import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# Alembic Config object — provides access to .ini values
config = context.config

# Set up Python logging from the alembic.ini [loggers] section
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import Base from app.database so autogenerate can detect schema changes.
# Every module's models must be imported here — importing registers them with
# Base.metadata. Add a new import line each time a new module adds models.
from app.accounts.models import (  # noqa: E402, F401
    Account,
    AccountGroup,
    DebtAccount,
    DebtBalance,
    ManualAccount,
)
from app.audit.models import AuditEvent  # noqa: E402, F401
from app.budgets.models import (  # noqa: E402, F401
    Budget,
    BudgetLine,
    BudgetPeriodActual,
    BudgetPeriodIncome,
)
from app.classification.models import (  # noqa: E402, F401
    Category,
    HouseholdClassificationSettings,
    IncomeSource,
    Rule,
    Tag,
)
from app.database import Base  # noqa: E402
from app.debts.models import (  # noqa: E402, F401
    DebtPlan,
    DebtPlanSchedule,
    DebtPlanSummary,
)
from app.goals.models import (  # noqa: E402, F401
    Goal,
    GoalContribution,
    GoalFundingSource,
    GoalSnapshot,
)
from app.households.models import (  # noqa: E402, F401
    Household,
    HouseholdMembership,
    RefreshToken,
    User,
)
from app.ingest.models import ImportJob, SyncConfig  # noqa: E402, F401
from app.insights.models import (  # noqa: E402, F401
    InsightAuditLog,
    InsightProviderConfig,
    TokenBudget,
)
from app.platform.fx import FxRate  # noqa: E402, F401
from app.projections.models import (  # noqa: E402, F401
    ProjectedEvent,
    ProjectionBreachEvent,
    ProjectionRun,
    ProjectionScenario,
)
from app.recommendations.models import AutoApplyRule, Recommendation  # noqa: E402, F401

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no DB connection, emits SQL to stdout)."""
    from app.config import get_settings

    url = str(get_settings().database_url)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: object) -> None:
    context.configure(
        connection=connection,  # type: ignore[arg-type]
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    from app.config import get_settings

    engine = create_async_engine(str(get_settings().database_url))
    async with engine.begin() as conn:
        await conn.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
