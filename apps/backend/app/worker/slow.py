"""ARQ worker-slow pool — long jobs, low concurrency.

Handles: statement parsing, historical imports, AI provider calls, recurrence
detection sweeps. Hard timeout: 1 hour per job.

To run: arq app.worker.slow.WorkerSettings
"""

from typing import ClassVar

from arq import cron
from arq.connections import RedisSettings

from app.admin.jobs import check_backup_health_job, run_backup_job
from app.budgets import budget_period_close_job
from app.classification import reclassify_all_job
from app.debts import recompute_debt_schedule_job
from app.goals import goal_status_recalc_job
from app.households.jobs import cleanup_unassigned_accounts
from app.ingest import process_upload_job, sync_account_job
from app.insights import generate_insights_job
from app.projections import cleanup_transient_scenarios_job
from app.recurrences import recurrence_detection_sweep_job
from app.worker.settings import get_redis_settings


class WorkerSettings:
    # Job functions registered by domain modules as they are built out.
    # Each function must be idempotent (safe to run twice).
    functions: ClassVar[list[object]] = [
        reclassify_all_job,
        sync_account_job,
        process_upload_job,
        recurrence_detection_sweep_job,
        budget_period_close_job,
        recompute_debt_schedule_job,
        goal_status_recalc_job,
        cleanup_transient_scenarios_job,
        generate_insights_job,
        cleanup_unassigned_accounts,
        run_backup_job,
        check_backup_health_job,
    ]

    cron_jobs: ClassVar[list[object]] = [
        cron(check_backup_health_job, hour=2, minute=0),
    ]

    redis_settings: RedisSettings = get_redis_settings()
    max_jobs: int = 5
    job_timeout: int = 3_600  # 1 hour
    keep_result: int = 86_400  # 24 hours (for debugging)
