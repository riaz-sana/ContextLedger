"""Tests for tier 1/2/3 conflict resolution routing.

The resolver examines two profiles and routes each conflicting
section to the appropriate resolution tier.

Task: TASK-009 — Implement conflict resolution router
"""

import pytest


class TestConflictDetection:
    """Test detecting conflicts between parent and fork profiles."""

    def test_no_conflicts_non_overlapping(self):
        """Non-overlapping changes should have no conflicts."""
        from contextledger.merge.resolver import ConflictResolver
        resolver = ConflictResolver()
        parent_changes = {"extraction.sources": ["db"]}
        fork_changes = {"memory_schema.graph_edges": [{"from": "A", "to": "B"}]}
        conflicts = resolver.detect_conflicts(parent_changes, fork_changes)
        assert len(conflicts) == 0

    def test_detects_same_section_conflict(self):
        """Changes to the same section should be flagged as a conflict."""
        from contextledger.merge.resolver import ConflictResolver
        resolver = ConflictResolver()
        parent_changes = {"extraction.sources": ["db_v2"]}
        fork_changes = {"extraction.sources": ["filesystem"]}
        conflicts = resolver.detect_conflicts(parent_changes, fork_changes)
        assert len(conflicts) == 1
        assert "extraction.sources" in [c["section"] for c in conflicts]

    def test_detects_multiple_conflicts(self):
        """Multiple overlapping sections should all be detected."""
        from contextledger.merge.resolver import ConflictResolver
        resolver = ConflictResolver()
        parent_changes = {
            "extraction.sources": ["db_v2"],
            "synthesis.templates.find_patterns": "new prompt v2",
        }
        fork_changes = {
            "extraction.sources": ["filesystem"],
            "synthesis.templates.find_patterns": "fork prompt",
        }
        conflicts = resolver.detect_conflicts(parent_changes, fork_changes)
        assert len(conflicts) == 2


class TestTierClassification:
    """Test classifying conflicts into resolution tiers."""

    def test_tier1_non_overlapping(self):
        """Non-overlapping changes should be classified as tier 1 (auto-merge)."""
        from contextledger.merge.resolver import ConflictResolver
        resolver = ConflictResolver()
        result = resolver.classify(
            section="extraction.sources",
            parent_value=["db"],
            fork_value=["db"],
            has_dag_dependency=False,
        )
        assert result == 1

    def test_tier2_same_section_different_logic(self):
        """Same section with different logic should be tier 2 (semantic eval)."""
        from contextledger.merge.resolver import ConflictResolver
        resolver = ConflictResolver()
        result = resolver.classify(
            section="synthesis.templates.find_patterns",
            parent_value="original prompt",
            fork_value="modified prompt",
            has_dag_dependency=False,
        )
        assert result == 2

    def test_tier3_conflicting_template_no_clear_winner(self):
        """Irreconcilable template conflicts should be tier 3 (manual)."""
        from contextledger.merge.resolver import ConflictResolver
        resolver = ConflictResolver()
        result = resolver.classify(
            section="synthesis.templates.find_patterns",
            parent_value="completely different approach A",
            fork_value="completely different approach B",
            has_dag_dependency=True,
        )
        assert result == 3


class TestMergeExecution:
    """Test executing merges based on tier classification."""

    def test_auto_merge_tier1(self):
        """Tier 1 conflicts should auto-merge without user input."""
        from contextledger.merge.resolver import ConflictResolver
        resolver = ConflictResolver()
        parent = {"extraction": {"sources": ["db"]}, "memory_schema": {"graph_nodes": ["Entity"]}}
        fork = {"extraction": {"sources": ["db"]}, "memory_schema": {"graph_nodes": ["Entity", "File"]}}
        result = resolver.merge(parent, fork)
        assert result["status"] == "merged"
        assert "File" in result["merged"]["memory_schema"]["graph_nodes"]

    def test_tier2_returns_evaluation_needed(self):
        """Tier 2 conflicts should return status requiring evaluation."""
        from contextledger.merge.resolver import ConflictResolver
        resolver = ConflictResolver()
        parent = {"synthesis": {"templates": [{"id": "t1", "prompt": "v1"}]}}
        fork = {"synthesis": {"templates": [{"id": "t1", "prompt": "v2"}]}}
        result = resolver.merge(parent, fork)
        assert result["status"] in ("evaluation_needed", "tier2")
        assert len(result.get("conflicts", [])) > 0

    def test_tier3_blocks_merge(self):
        """Tier 3 conflicts should block the merge entirely."""
        from contextledger.merge.resolver import ConflictResolver
        resolver = ConflictResolver()
        # Simulate irreconcilable conflict
        result = resolver.merge(
            parent={"synthesis": {"dag": {"nodes": [{"id": "a", "depends_on": ["x"]}]}}},
            fork={"synthesis": {"dag": {"nodes": [{"id": "a", "depends_on": ["y"]}]}}},
        )
        assert result["status"] in ("blocked", "tier3", "manual_required")

    def test_merge_never_auto_merges_tier3(self):
        """Tier 3 must NEVER be auto-merged. This is a hard constraint."""
        from contextledger.merge.resolver import ConflictResolver
        resolver = ConflictResolver()
        # Even if everything else is clean, tier 3 blocks
        result = resolver.merge(
            parent={"synthesis": {"dag": {"nodes": [{"id": "a", "depends_on": ["x"]}]}}},
            fork={"synthesis": {"dag": {"nodes": [{"id": "a", "depends_on": ["y"]}]}}},
        )
        assert result["status"] != "merged"
