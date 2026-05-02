"""Projections module.

Owns: single deterministic projection engine consumed by budgets, debts,
goals, and calendar. Supports scenario/what-if analysis. Cache keyed to
(inputs hash, as_of date), invalidated on any input change.
"""

__all__: list[str] = []
