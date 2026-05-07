"""Debts module.

Owns: DebtPlan, DebtPlanSchedule, DebtPlanSummary; payoff scheduling;
strategy implementations (avalanche, snowball, custom, none).
Emits Recommendations -- never writes directly to budgets tables.
"""

from app.debts.enums import DebtPlanMethod
from app.debts.jobs import recompute_debt_schedule_job
from app.debts.models import DebtPlan, DebtPlanSchedule, DebtPlanSummary
from app.debts.service import (
    BaselineSummary,
    ComparisonSummary,
    ConflictError,
    DebtPlanScheduleByAccount,
    NotFoundError,
    ValidationError,
    archive_plan,
    check_payment_deviation,
    compute_comparison,
    compute_minimums_baseline,
    compute_schedule,
    create_plan,
    get_active_plan,
    get_plan,
    get_schedule,
    get_summary,
    list_plan_history,
    list_plans,
    recommend_budget_line,
    simulate_schedule,
    update_plan,
)

__all__ = [
    "BaselineSummary",
    "ComparisonSummary",
    "ConflictError",
    "DebtPlan",
    "DebtPlanMethod",
    "DebtPlanSchedule",
    "DebtPlanScheduleByAccount",
    "DebtPlanSummary",
    "NotFoundError",
    "ValidationError",
    "archive_plan",
    "check_payment_deviation",
    "compute_comparison",
    "compute_minimums_baseline",
    "compute_schedule",
    "create_plan",
    "get_active_plan",
    "get_plan",
    "get_schedule",
    "get_summary",
    "list_plan_history",
    "list_plans",
    "recommend_budget_line",
    "recompute_debt_schedule_job",
    "simulate_schedule",
    "update_plan",
]
