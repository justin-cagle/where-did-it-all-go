"""Classification module.

Owns: Category (2-level hierarchy), Tag, rules engine, transaction-type
detector, IncomeSource registry.

Pipeline order (deterministic):
  1. Type detection
  2. Income source match
  3. User rules
  4. Fallback uncategorized
"""

__all__: list[str] = []
