"""Tests for core data types (MemoryUnit, SkillBundle, ProfileMetadata, ProfileDiff).

These tests validate the data type contracts that all other modules depend on.
They should pass before any backend or layer implementation begins.

Task: TASK-001 — Implement core data types
"""

import pytest
from datetime import datetime, timezone


class TestMemoryUnit:
    """MemoryUnit is the atomic unit of stored context."""

    def test_create_with_required_fields(self):
        """MemoryUnit must be constructable with id, content, unit_type, and profile_name."""
        from contextledger.core.types import MemoryUnit
        unit = MemoryUnit(
            id="mem-001",
            content="Database schema has 3 tables",
            unit_type="finding",
            profile_name="db-research",
        )
        assert unit.id == "mem-001"
        assert unit.content == "Database schema has 3 tables"
        assert unit.unit_type == "finding"
        assert unit.profile_name == "db-research"

    def test_create_with_optional_fields(self):
        """MemoryUnit should support embedding, tags, timestamp, parent_id, metadata."""
        from contextledger.core.types import MemoryUnit
        ts = datetime.now(timezone.utc)
        unit = MemoryUnit(
            id="mem-002",
            content="Found anomaly in column X",
            unit_type="finding",
            profile_name="db-research",
            embedding=[0.1, 0.2, 0.3],
            tags=["anomaly", "column-x"],
            timestamp=ts,
            parent_id="mem-001",
            metadata={"confidence": 0.95},
        )
        assert unit.embedding == [0.1, 0.2, 0.3]
        assert "anomaly" in unit.tags
        assert unit.timestamp == ts
        assert unit.parent_id == "mem-001"
        assert unit.metadata["confidence"] == 0.95

    def test_default_timestamp(self):
        """MemoryUnit should auto-set timestamp if not provided."""
        from contextledger.core.types import MemoryUnit
        unit = MemoryUnit(
            id="mem-003",
            content="test",
            unit_type="finding",
            profile_name="test",
        )
        assert unit.timestamp is not None
        assert isinstance(unit.timestamp, datetime)

    def test_default_empty_collections(self):
        """Tags, embedding, metadata should default to empty, not None."""
        from contextledger.core.types import MemoryUnit
        unit = MemoryUnit(
            id="mem-004",
            content="test",
            unit_type="finding",
            profile_name="test",
        )
        assert unit.tags == [] or unit.tags is not None
        assert unit.metadata == {} or unit.metadata is not None

    def test_unit_type_values(self):
        """unit_type should accept: finding, hypothesis, entity, observation."""
        from contextledger.core.types import MemoryUnit
        for ut in ["finding", "hypothesis", "entity", "observation"]:
            unit = MemoryUnit(
                id=f"mem-{ut}",
                content=f"test {ut}",
                unit_type=ut,
                profile_name="test",
            )
            assert unit.unit_type == ut


class TestSkillBundle:
    """SkillBundle represents a complete skill directory."""

    def test_create_with_required_fields(self):
        """SkillBundle needs name, version, profile_yaml content."""
        from contextledger.core.types import SkillBundle
        bundle = SkillBundle(
            name="supervised-db-research",
            version="1.0.0",
            profile_yaml="name: supervised-db-research\nversion: 1.0.0",
        )
        assert bundle.name == "supervised-db-research"
        assert bundle.version == "1.0.0"

    def test_parent_field(self):
        """Forked bundles must reference their parent."""
        from contextledger.core.types import SkillBundle
        bundle = SkillBundle(
            name="filesystem-research",
            version="1.0.0-fs-1",
            profile_yaml="name: filesystem-research",
            parent="supervised-db-research",
        )
        assert bundle.parent == "supervised-db-research"

    def test_base_bundle_has_no_parent(self):
        """Base bundles should have parent=None."""
        from contextledger.core.types import SkillBundle
        bundle = SkillBundle(
            name="base-research-skill",
            version="1.0.0",
            profile_yaml="name: base-research-skill",
        )
        assert bundle.parent is None

    def test_tools_and_refs_lists(self):
        """Bundle should track tool file paths and ref file paths."""
        from contextledger.core.types import SkillBundle
        bundle = SkillBundle(
            name="test-skill",
            version="1.0.0",
            profile_yaml="name: test-skill",
            tools=["tools/db_connector.py", "tools/query_builder.py"],
            refs=["refs/schema_docs.pdf"],
        )
        assert len(bundle.tools) == 2
        assert "tools/db_connector.py" in bundle.tools
        assert len(bundle.refs) == 1


class TestProfileMetadata:
    """ProfileMetadata is the lightweight index entry for a skill profile."""

    def test_create_metadata(self):
        """Should capture name, version, parent, created_at, updated_at."""
        from contextledger.core.types import ProfileMetadata
        meta = ProfileMetadata(
            name="db-research",
            version="1.0.0",
        )
        assert meta.name == "db-research"
        assert meta.version == "1.0.0"

    def test_metadata_with_parent(self):
        """Forked profile metadata should include parent reference."""
        from contextledger.core.types import ProfileMetadata
        meta = ProfileMetadata(
            name="fs-research",
            version="1.0.0-fs-1",
            parent="db-research",
        )
        assert meta.parent == "db-research"

    def test_metadata_timestamps(self):
        """Metadata should have created_at and updated_at timestamps."""
        from contextledger.core.types import ProfileMetadata
        meta = ProfileMetadata(
            name="test",
            version="1.0.0",
        )
        assert hasattr(meta, "created_at")
        assert hasattr(meta, "updated_at")


class TestProfileDiff:
    """ProfileDiff captures semantic differences between two profiles."""

    def test_create_diff(self):
        """Diff should identify the two profiles being compared."""
        from contextledger.core.types import ProfileDiff
        diff = ProfileDiff(
            profile_a="supervised-db-research",
            profile_b="filesystem-research",
            changed_sections=["extraction.sources", "extraction.entities"],
        )
        assert diff.profile_a == "supervised-db-research"
        assert diff.profile_b == "filesystem-research"
        assert len(diff.changed_sections) == 2

    def test_diff_with_no_changes(self):
        """Identical profiles should produce empty diff."""
        from contextledger.core.types import ProfileDiff
        diff = ProfileDiff(
            profile_a="same-skill",
            profile_b="same-skill",
            changed_sections=[],
        )
        assert len(diff.changed_sections) == 0

    def test_diff_categorizes_changes(self):
        """Diff should distinguish added, removed, and modified sections."""
        from contextledger.core.types import ProfileDiff
        diff = ProfileDiff(
            profile_a="parent",
            profile_b="fork",
            changed_sections=["extraction.sources"],
            added_sections=["synthesis.dag.nodes.new_node"],
            removed_sections=["extraction.rules.old_rule"],
        )
        assert "extraction.sources" in diff.changed_sections
        assert "synthesis.dag.nodes.new_node" in diff.added_sections
        assert "extraction.rules.old_rule" in diff.removed_sections

    def test_diff_conflict_tier(self):
        """Each changed section should be classifiable by conflict tier."""
        from contextledger.core.types import ProfileDiff
        diff = ProfileDiff(
            profile_a="parent",
            profile_b="fork",
            changed_sections=["extraction.sources", "synthesis.templates.find_patterns"],
            conflict_tiers={"extraction.sources": 1, "synthesis.templates.find_patterns": 2},
        )
        assert diff.conflict_tiers["extraction.sources"] == 1
        assert diff.conflict_tiers["synthesis.templates.find_patterns"] == 2
