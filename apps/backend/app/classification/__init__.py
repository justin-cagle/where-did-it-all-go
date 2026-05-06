"""Classification module.

Owns: Category (2-level hierarchy), Tag, rules engine, transaction-type
detector, IncomeSource registry.

Pipeline order (deterministic):
  1. Type detection
  2. Income source match
  3. User rules
  4. Fallback uncategorized

Public interface:
  seed_default_categories  -- called by platform.events after household creation
  reclassify_all_job       -- ARQ job registered in worker/slow.py
"""

from app.classification.service import reclassify_all_job, seed_default_categories

__all__ = ["reclassify_all_job", "seed_default_categories"]
