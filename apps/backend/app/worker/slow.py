"""ARQ worker-slow pool — long jobs, low concurrency.

Handles: statement parsing, historical imports, AI provider calls, recurrence
detection sweeps. Hard timeout: 1 hour per job.

To run: arq app.worker.slow.WorkerSettings
"""

from typing import ClassVar

from arq.connections import RedisSettings

from app.classification import reclassify_all_job
from app.worker.settings import get_redis_settings


class WorkerSettings:
    # Job functions registered by domain modules as they are built out.
    # Each function must be idempotent (safe to run twice).
    functions: ClassVar[list[object]] = [
        reclassify_all_job,
    ]

    redis_settings: RedisSettings = get_redis_settings()
    max_jobs: int = 5
    job_timeout: int = 3_600  # 1 hour
    keep_result: int = 86_400  # 24 hours (for debugging)
