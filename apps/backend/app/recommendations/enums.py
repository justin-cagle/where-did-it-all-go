"""Enums for the recommendations domain."""

from enum import StrEnum


class RecommendationSource(StrEnum):
    DEBT_ENGINE = "debt_engine"
    GOAL_ENGINE = "goal_engine"
    RECURRENCE_DETECTOR = "recurrence_detector"
    REFUND_PAIRING = "refund_pairing"
    TRANSFER_DETECTION = "transfer_detection"
    AI_INSIGHTS = "ai_insights"
    CLASSIFICATION_PIPELINE = "classification_pipeline"
    INGEST = "ingest"


class RecommendationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
