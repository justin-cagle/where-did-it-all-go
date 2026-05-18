"""ARQ worker-fast pool — short jobs, high concurrency.

Handles: event handlers, projection cache invalidations, single-transaction
processing. Hard timeout: 60 seconds per job.

To run: arq app.worker.fast.WorkerSettings
"""

from typing import ClassVar

from arq import cron
from arq.connections import RedisSettings

from app.admin.jobs import check_worker_health_job, send_admin_notification_job
from app.projections import invalidate_projection_cache_job
from app.recurrences import match_transaction_job
from app.worker.settings import get_redis_settings


class WorkerSettings:
    # Job functions registered by domain modules as they are built out.
    # Each function must be idempotent (safe to run twice).
    functions: ClassVar[list[object]] = [
        match_transaction_job,
        invalidate_projection_cache_job,
        send_admin_notification_job,
        check_worker_health_job,
    ]

    cron_jobs: ClassVar[list[object]] = [
        cron(check_worker_health_job, minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}),
    ]

    redis_settings: RedisSettings = get_redis_settings()
    max_jobs: int = 50
    job_timeout: int = 60  # seconds
    keep_result: int = 86_400  # 24 hours (for debugging)
