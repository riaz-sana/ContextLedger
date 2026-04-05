"""Tier 1/2/3 conflict resolution router.

Routes merge conflicts to the appropriate resolution strategy:
- Tier 1: Automatic merge (non-overlapping changes)
- Tier 2: Semantic evaluation (same section, different logic)
- Tier 3: Manual override (irreconcilable conflicts)
"""
