"""Goals module.

Owns: Goal entities (8 types: savings_target, purchase, debt_payoff,
net_worth, category_reduction, emergency_fund, recurring_contribution,
minimum_balance), burn-up tracking, completion policies, funding sources.

Emits Recommendations -- never writes directly to other module tables.
"""

from app.goals.enums import (
    BurnUpStatus,
    CompletionPolicy,
    ContributionType,
    FundingSourceType,
    FundingStrategy,
    GoalStatus,
    GoalType,
)
from app.goals.jobs import goal_status_recalc_job
from app.goals.models import Goal, GoalContribution, GoalFundingSource, GoalSnapshot
from app.goals.service import (
    ConflictError,
    NotFoundError,
    PerUserBreakdown,
    UserContributionTotal,
    ValidationError,
    archive_goal,
    check_category_reduction,
    check_completion,
    check_minimum_balance,
    compute_burn_up,
    compute_burn_up_pure,
    create_funding_source,
    create_goal,
    delete_funding_source,
    get_all_status,
    get_contributions,
    get_goal,
    get_latest_snapshot,
    get_per_user_contributions,
    list_funding_sources,
    list_goals,
    list_snapshots,
    log_contribution,
    manual_complete,
    pause_goal,
    resume_goal,
    scan_tag_contributions,
    update_goal,
)

__all__ = [
    # Enums
    "BurnUpStatus",
    "CompletionPolicy",
    # Service errors
    "ConflictError",
    "ContributionType",
    "FundingSourceType",
    "FundingStrategy",
    # Models
    "Goal",
    "GoalContribution",
    "GoalFundingSource",
    "GoalSnapshot",
    "GoalStatus",
    "GoalType",
    "NotFoundError",
    "PerUserBreakdown",
    "UserContributionTotal",
    "ValidationError",
    # Service operations
    "archive_goal",
    "check_category_reduction",
    "check_completion",
    "check_minimum_balance",
    "compute_burn_up",
    "compute_burn_up_pure",
    "create_funding_source",
    "create_goal",
    "delete_funding_source",
    "get_all_status",
    "get_contributions",
    "get_goal",
    "get_latest_snapshot",
    "get_per_user_contributions",
    # Jobs
    "goal_status_recalc_job",
    "list_funding_sources",
    "list_goals",
    "list_snapshots",
    "log_contribution",
    "manual_complete",
    "pause_goal",
    "resume_goal",
    "scan_tag_contributions",
    "update_goal",
]
