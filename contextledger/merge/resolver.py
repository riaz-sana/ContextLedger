"""Tier 1/2/3 conflict resolution router.

Routes merge conflicts to the appropriate resolution strategy:
- Tier 1: Automatic merge (non-overlapping changes)
- Tier 2: Semantic evaluation (same section, different logic)
- Tier 3: Manual override (irreconcilable conflicts)
"""

from __future__ import annotations

from typing import Any


def _flatten(d: dict, prefix: str = "") -> dict[str, Any]:
    """Flatten a nested dict into dotted-path keys."""
    items: dict[str, Any] = {}
    for k, v in d.items():
        path = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            items.update(_flatten(v, path))
        else:
            items[path] = v
    return items


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep-merge two dicts; override values take precedence."""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


class ConflictResolver:
    """Routes merge conflicts to the appropriate resolution tier."""

    def detect_conflicts(
        self, parent_changes: dict, fork_changes: dict
    ) -> list[dict]:
        """Find overlapping section keys between parent and fork changes.

        Returns a list of dicts like ``{"section": key}`` for each key
        present in both *parent_changes* and *fork_changes*.
        """
        overlapping = set(parent_changes) & set(fork_changes)
        return [{"section": key} for key in sorted(overlapping)]

    def classify(
        self,
        section: str,
        parent_value: Any,
        fork_value: Any,
        has_dag_dependency: bool,
    ) -> int:
        """Classify a conflict into a resolution tier.

        Returns:
            1 — Tier 1: values identical (auto-merge)
            3 — Tier 3: has_dag_dependency AND values differ (block)
            2 — Tier 2: values differ, no DAG dependency (evaluation)
        """
        if parent_value == fork_value:
            return 1
        if has_dag_dependency:
            return 3
        return 2

    def merge(self, parent: dict, fork: dict) -> dict:
        """Merge two profile dicts with tier-based conflict resolution.

        Tier 3 conflicts NEVER auto-merge — always block.
        """
        flat_parent = _flatten(parent)
        flat_fork = _flatten(fork)

        all_keys = set(flat_parent) | set(flat_fork)

        conflicts: list[dict] = []
        max_tier = 0

        for key in sorted(all_keys):
            p_val = flat_parent.get(key)
            f_val = flat_fork.get(key)

            # Only care about keys present in both with different values,
            # or keys present in both with same values (tier 1).
            # Keys only in one side are non-conflicting additions.
            if key not in flat_parent or key not in flat_fork:
                continue

            if p_val == f_val:
                # Tier 1 — identical, no conflict to record
                continue

            # Values differ — classify
            has_dag = "dag" in key.lower()

            # Tier 3: anything involving DAG dependencies
            if has_dag:
                tier = 3
            # Tier 2: template changes need semantic evaluation
            elif "templates" in key.lower():
                tier = 2
            else:
                # Non-dag, non-template differences auto-merge (tier 1)
                tier = 1

            conflicts.append({"section": key, "tier": tier})
            max_tier = max(max_tier, tier)

        merged = _deep_merge(parent, fork)

        if max_tier >= 3:
            return {"status": "blocked", "conflicts": conflicts}
        if max_tier == 2:
            return {
                "status": "evaluation_needed",
                "conflicts": conflicts,
                "merged": merged,
            }
        # All tier 1 or no conflicts at all
        return {"status": "merged", "merged": merged}
