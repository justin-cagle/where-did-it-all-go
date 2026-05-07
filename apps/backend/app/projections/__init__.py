"""Projections module.

Owns: single deterministic projection engine consumed by budgets, debts,
goals, and calendar. Supports scenario/what-if analysis. Cache keyed to
(inputs hash, as_of date), invalidated on any input change.
"""

from app.projections.jobs import (
    cleanup_transient_scenarios_job,
    invalidate_projection_cache_job,
)

__all__ = [
    "cleanup_transient_scenarios_job",
    "invalidate_projection_cache_job",
]
