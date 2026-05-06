"""Recurrences module.

Owns: declared and detected recurrences, RecurrenceCandidate,
RecurrenceException, RecurrenceMatch, deviation alerts.

Public interface (consumed by worker registration):
  recurrence_detection_sweep_job  -- ARQ job registered in worker/slow.py
  match_transaction_job           -- ARQ job registered in worker/fast.py
"""

from app.recurrences.jobs import match_transaction_job, recurrence_detection_sweep_job

__all__ = ["match_transaction_job", "recurrence_detection_sweep_job"]
