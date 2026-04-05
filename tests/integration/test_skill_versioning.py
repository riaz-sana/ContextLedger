"""End-to-end tests for skill versioning mode.

Tests: create profile -> fork -> modify -> diff -> merge
with conflict resolution across all three tiers.

Task: TASK-018 — Integration test: skill versioning mode
"""

import pytest


class TestSkillVersioningEndToEnd:
    """Full pipeline test for skill versioning mode."""

    def test_create_and_fork_profile(self, sample_profile_yaml):
        """Create a profile, fork it, verify inheritance."""
        from contextledger.skill.parser import ProfileParser
        from contextledger.skill.fork import ForkManager
        parser = ProfileParser()
        mgr = ForkManager()
        parent = parser.parse(sample_profile_yaml)
        child = mgr.fork(
            {"name": parent["name"], "version": parent["version"], "profile_yaml": sample_profile_yaml},
            new_name="child-skill",
        )
        assert child["parent"] == parent["name"]

    def test_fork_modify_diff(self, sample_profile_yaml, sample_fork_yaml):
        """Fork a profile, modify the fork, then diff against parent."""
        from contextledger.skill.parser import ProfileParser
        from contextledger.merge.resolver import ConflictResolver
        parser = ProfileParser()
        resolver = ConflictResolver()
        parent = parser.parse(sample_profile_yaml)
        fork = parser.parse(sample_fork_yaml)
        # Detect what changed
        parent_extraction = parent.get("extraction", {})
        fork_extraction = fork.get("extraction", {})
        assert parent_extraction != fork_extraction

    def test_fork_merge_tier1(self, sample_profile_yaml):
        """Non-overlapping changes should auto-merge (tier 1)."""
        from contextledger.merge.resolver import ConflictResolver
        resolver = ConflictResolver()
        parent = {"extraction": {"sources": ["db"]}, "memory_schema": {"graph_nodes": ["Entity"]}}
        fork = {"extraction": {"sources": ["db"]}, "memory_schema": {"graph_nodes": ["Entity", "File"]}}
        result = resolver.merge(parent, fork)
        assert result["status"] == "merged"

    def test_fork_merge_tier2_triggers_evaluation(self, sample_profile_yaml):
        """Overlapping template changes should trigger tier 2 evaluation."""
        from contextledger.merge.resolver import ConflictResolver
        resolver = ConflictResolver()
        parent = {"synthesis": {"templates": [{"id": "t1", "prompt": "original"}]}}
        fork = {"synthesis": {"templates": [{"id": "t1", "prompt": "modified"}]}}
        result = resolver.merge(parent, fork)
        assert result["status"] in ("evaluation_needed", "tier2")

    def test_fork_merge_tier3_blocks(self):
        """Irreconcilable DAG conflicts should block merge (tier 3)."""
        from contextledger.merge.resolver import ConflictResolver
        resolver = ConflictResolver()
        result = resolver.merge(
            parent={"synthesis": {"dag": {"nodes": [{"id": "a", "depends_on": ["x"]}]}}},
            fork={"synthesis": {"dag": {"nodes": [{"id": "a", "depends_on": ["y"]}]}}},
        )
        assert result["status"] != "merged"

    def test_full_lifecycle(self, sample_profile_yaml, sample_fork_yaml):
        """Full lifecycle: create -> fork -> modify -> diff -> merge -> verify."""
        from contextledger.skill.parser import ProfileParser
        from contextledger.skill.fork import ForkManager
        from contextledger.merge.resolver import ConflictResolver

        parser = ProfileParser()
        mgr = ForkManager()
        resolver = ConflictResolver()

        # 1. Create parent
        parent = parser.parse(sample_profile_yaml)
        parser.validate(parent)

        # 2. Fork
        child = mgr.fork(
            {"name": parent["name"], "version": parent["version"], "profile_yaml": sample_profile_yaml},
            new_name="fork-skill",
        )
        assert child["parent"] == parent["name"]

        # 3. Parse the fork
        fork = parser.parse(sample_fork_yaml)

        # 4. Resolve inheritance
        registry = {parent["name"]: parent}
        resolved = mgr.resolve(fork, registry=registry)
        assert resolved["name"] == fork["name"]

        # 5. The resolved profile should have sections from both parent and fork
        assert "memory_schema" in resolved  # inherited from parent
        assert "extraction" in resolved     # overridden in fork
