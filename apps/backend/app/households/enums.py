"""Enumerations for the households domain."""

from enum import StrEnum


class VisibilityMode(StrEnum):
    """Controls what financial data household members can see."""

    FULLY_SHARED = "fully_shared"
    SEPARATE_WITH_JOINT_VIEW = "separate_with_joint_view"
    ROLE_BASED = "role_based"
    ADMIN_CONTROLLED = "admin_controlled"


class HouseholdRole(StrEnum):
    """Financial role within a household."""

    OWNER = "owner"
    MEMBER = "member"
