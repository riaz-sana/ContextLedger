"""Tests for CMV engine gaps: provenance (GAP 5) and portable archives (GAP 6)."""

import pytest

from contextledger.memory.cmv import CMVEngine


class TestCMVProvenance:
    """GAP 5: CMV snapshots linked to skill versions."""

    def test_snapshot_stores_skill_info(self):
        engine = CMVEngine()
        sid = engine.snapshot(
            {"messages": [{"role": "user", "content": "test"}]},
            skill="agent-prober",
            skill_version="1.2.0",
        )
        node = engine.get_node(sid)
        assert node["skill"] == "agent-prober"
        assert node["skill_version"] == "1.2.0"

    def test_snapshot_without_skill_defaults_none(self):
        engine = CMVEngine()
        sid = engine.snapshot({"messages": [{"role": "user", "content": "test"}]})
        node = engine.get_node(sid)
        assert node["skill"] is None
        assert node["skill_version"] is None

    def test_get_lineage_filters_by_skill(self):
        engine = CMVEngine()
        engine.snapshot(
            {"messages": [{"role": "user", "content": "msg1"}]},
            skill="skill-a", skill_version="1.0",
        )
        engine.snapshot(
            {"messages": [{"role": "user", "content": "msg2"}]},
            skill="skill-b", skill_version="1.0",
        )
        engine.snapshot(
            {"messages": [{"role": "user", "content": "msg3"}]},
            skill="skill-a", skill_version="1.1",
        )

        lineage = engine.get_lineage("skill-a")
        assert len(lineage) == 2
        assert all(n["skill"] == "skill-a" for n in lineage)

    def test_get_lineage_chronological_order(self):
        engine = CMVEngine()
        engine.snapshot(
            {"messages": [{"role": "user", "content": "first"}]},
            skill="test-skill", skill_version="1.0",
        )
        engine.snapshot(
            {"messages": [{"role": "user", "content": "second"}]},
            skill="test-skill", skill_version="1.1",
        )
        lineage = engine.get_lineage("test-skill")
        assert lineage[0]["skill_version"] == "1.0"
        assert lineage[1]["skill_version"] == "1.1"

    def test_get_lineage_empty_for_unknown_skill(self):
        engine = CMVEngine()
        engine.snapshot({"messages": [{"role": "user", "content": "test"}]})
        assert engine.get_lineage("nonexistent") == []


class TestCMVArchive:
    """GAP 6: Portable .cmv archive export/import."""

    def test_export_all_nodes(self):
        engine = CMVEngine()
        engine.snapshot({"messages": [{"role": "user", "content": "a"}]})
        engine.snapshot({"messages": [{"role": "user", "content": "b"}]})

        archive = engine.export_archive()
        assert archive["format"] == "cmv-archive-v1"
        assert len(archive["nodes"]) == 2
        assert archive["skill_filter"] is None

    def test_export_filtered_by_skill(self):
        engine = CMVEngine()
        engine.snapshot(
            {"messages": [{"role": "user", "content": "a"}]},
            skill="target-skill",
        )
        engine.snapshot(
            {"messages": [{"role": "user", "content": "b"}]},
            skill="other-skill",
        )
        archive = engine.export_archive(skill="target-skill")
        assert archive["skill_filter"] == "target-skill"
        assert len(archive["nodes"]) == 1
        assert archive["nodes"][0]["skill"] == "target-skill"

    def test_export_includes_ancestors(self):
        engine = CMVEngine()
        # First snapshot is head, parent of second
        s1 = engine.snapshot({"messages": [{"role": "user", "content": "base"}]})
        s2 = engine.snapshot(
            {"messages": [{"role": "user", "content": "derived"}]},
            skill="my-skill",
        )
        # s2 has parent_id = s1, s1 has no skill tag
        archive = engine.export_archive(skill="my-skill")
        ids = {n["id"] for n in archive["nodes"]}
        assert s1 in ids  # ancestor included
        assert s2 in ids

    def test_import_archive(self):
        # Export from one engine
        engine1 = CMVEngine()
        engine1.snapshot({"messages": [{"role": "user", "content": "test"}]})
        archive = engine1.export_archive()

        # Import into another
        engine2 = CMVEngine()
        imported = engine2.import_archive(archive)
        assert imported == 1
        assert len(engine2.list_nodes()) == 1

    def test_import_skips_duplicates(self):
        engine = CMVEngine()
        engine.snapshot({"messages": [{"role": "user", "content": "test"}]})
        archive = engine.export_archive()

        # Import into same engine — should skip
        imported = engine.import_archive(archive)
        assert imported == 0
        assert len(engine.list_nodes()) == 1

    def test_roundtrip_export_import(self):
        engine1 = CMVEngine()
        s1 = engine1.snapshot(
            {"messages": [{"role": "user", "content": "hello"}]},
            skill="roundtrip-skill",
            skill_version="2.0",
        )
        s2 = engine1.snapshot(
            {"messages": [{"role": "user", "content": "world"}]},
            skill="roundtrip-skill",
            skill_version="2.1",
        )
        archive = engine1.export_archive(skill="roundtrip-skill")

        engine2 = CMVEngine()
        engine2.import_archive(archive)
        node = engine2.get_node(s2)
        assert node is not None
        assert node["skill"] == "roundtrip-skill"
        assert node["skill_version"] == "2.1"
        assert node["parent_id"] == s1

    def test_export_empty_engine(self):
        engine = CMVEngine()
        archive = engine.export_archive()
        assert archive["nodes"] == []

    def test_import_empty_archive(self):
        engine = CMVEngine()
        imported = engine.import_archive({"nodes": []})
        assert imported == 0

    def test_import_sets_head_for_chaining(self):
        """After import into empty engine, new snapshots chain correctly."""
        engine1 = CMVEngine()
        s1 = engine1.snapshot(
            {"messages": [{"role": "user", "content": "imported"}]},
            skill="test",
        )
        archive = engine1.export_archive()

        engine2 = CMVEngine()
        engine2.import_archive(archive)
        # Now create a new snapshot — it should chain to the imported node
        s2 = engine2.snapshot({"messages": [{"role": "user", "content": "new"}]})
        node2 = engine2.get_node(s2)
        assert node2["parent_id"] == s1
