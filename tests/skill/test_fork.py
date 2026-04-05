"""Tests for fork and inheritance chain resolution.

Forks store only overrides. Everything else resolves to
parent via content-addressable lookup at runtime.

Task: TASK-008 — Implement fork/inheritance resolution
"""

import pytest


class TestForkCreation:
    """Test creating forks from parent profiles."""

    def test_fork_creates_child(self, sample_profile_yaml):
        """Forking should create a new profile referencing the parent."""
        from contextledger.skill.fork import ForkManager
        mgr = ForkManager()
        parent = {"name": "parent-skill", "version": "1.0.0", "profile_yaml": sample_profile_yaml}
        child = mgr.fork(parent, new_name="child-skill")
        assert child["name"] == "child-skill"
        assert child["parent"] == "parent-skill"

    def test_fork_generates_version(self, sample_profile_yaml):
        """Fork should auto-generate a version derived from parent."""
        from contextledger.skill.fork import ForkManager
        mgr = ForkManager()
        parent = {"name": "parent-skill", "version": "1.0.0", "profile_yaml": sample_profile_yaml}
        child = mgr.fork(parent, new_name="child-skill")
        assert child["version"] is not None
        assert child["version"] != parent["version"]

    def test_fork_does_not_copy_tools(self, sample_profile_yaml):
        """Fork should reference parent tools, not duplicate them."""
        from contextledger.skill.fork import ForkManager
        mgr = ForkManager()
        parent = {
            "name": "parent-skill",
            "version": "1.0.0",
            "profile_yaml": sample_profile_yaml,
            "tools": ["tools/db_connector.py", "tools/query_builder.py"],
        }
        child = mgr.fork(parent, new_name="child-skill")
        # Child should have tool references, not copies
        assert child.get("inherited_tools") is not None or child.get("tools") == []

    def test_fork_does_not_copy_refs(self, sample_profile_yaml):
        """Fork should reference parent refs, not duplicate them."""
        from contextledger.skill.fork import ForkManager
        mgr = ForkManager()
        parent = {
            "name": "parent-skill",
            "version": "1.0.0",
            "profile_yaml": sample_profile_yaml,
            "refs": ["refs/glossary.md"],
        }
        child = mgr.fork(parent, new_name="child-skill")
        assert child.get("inherited_refs") is not None or child.get("refs") == []


class TestInheritanceResolution:
    """Test resolving the full profile by walking the inheritance chain."""

    def test_resolve_base_profile(self, sample_profile_yaml):
        """Base profile (no parent) should resolve to itself."""
        from contextledger.skill.fork import ForkManager
        mgr = ForkManager()
        base = {"name": "base", "version": "1.0.0", "parent": None, "profile_yaml": sample_profile_yaml}
        resolved = mgr.resolve(base, registry={})
        assert resolved["name"] == "base"
        assert "extraction" in resolved

    def test_resolve_inherits_from_parent(self, sample_profile_yaml, sample_fork_yaml):
        """Child should inherit unoverridden sections from parent."""
        from contextledger.skill.fork import ForkManager
        from contextledger.skill.parser import ProfileParser
        parser = ProfileParser()
        mgr = ForkManager()
        parent_profile = parser.parse(sample_profile_yaml)
        child_profile = parser.parse(sample_fork_yaml)
        registry = {"supervised-db-research": parent_profile}
        resolved = mgr.resolve(child_profile, registry=registry)
        # Child overrides extraction.sources, but memory_schema should come from parent
        assert "graph_nodes" in resolved.get("memory_schema", {})

    def test_resolve_override_takes_precedence(self, sample_profile_yaml, sample_fork_yaml):
        """Overridden sections in child should replace parent's."""
        from contextledger.skill.fork import ForkManager
        from contextledger.skill.parser import ProfileParser
        parser = ProfileParser()
        mgr = ForkManager()
        parent_profile = parser.parse(sample_profile_yaml)
        child_profile = parser.parse(sample_fork_yaml)
        registry = {"supervised-db-research": parent_profile}
        resolved = mgr.resolve(child_profile, registry=registry)
        # Child overrides extraction.sources to filesystem
        assert "filesystem" in resolved["extraction"]["sources"]

    def test_resolve_deep_chain(self, sample_profile_yaml):
        """Should resolve through multiple levels of inheritance (grandparent -> parent -> child)."""
        from contextledger.skill.fork import ForkManager
        from contextledger.skill.parser import ProfileParser
        parser = ProfileParser()
        mgr = ForkManager()

        grandparent = parser.parse(sample_profile_yaml)
        parent = {
            "name": "parent",
            "version": "1.0.0",
            "parent": "supervised-db-research",
            "extraction": {"sources": ["api"]},
        }
        child = {
            "name": "child",
            "version": "1.0.0",
            "parent": "parent",
            "extraction": {"entities": ["endpoint"]},
        }
        registry = {
            "supervised-db-research": grandparent,
            "parent": parent,
        }
        resolved = mgr.resolve(child, registry=registry)
        # entities from child, sources from parent, everything else from grandparent
        assert "endpoint" in resolved["extraction"]["entities"]
        assert "api" in resolved["extraction"]["sources"]

    def test_resolve_missing_parent_raises(self):
        """Resolving with a missing parent in registry should raise."""
        from contextledger.skill.fork import ForkManager
        mgr = ForkManager()
        child = {"name": "orphan", "version": "1.0.0", "parent": "nonexistent"}
        with pytest.raises((ValueError, KeyError)):
            mgr.resolve(child, registry={})
