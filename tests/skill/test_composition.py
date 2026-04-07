"""Tests for skill composition, section-level inheritance, and dependency checking.

Covers GAP 1 (section-level inheritance), GAP 2 (backend plugin slots),
GAP 3 (three-layer composition), and GAP 4 (dependency declarations).
"""

import pytest
import yaml


# ---------------------------------------------------------------------------
# GAP 3: Three-layer composition model
# ---------------------------------------------------------------------------


class TestThreeLayerComposition:
    """Tests for core → backend → domain composition."""

    def test_fork_with_backend(self, sample_profile_yaml):
        from contextledger.skill.fork import ForkManager
        mgr = ForkManager()
        parent = {"name": "core-skill", "version": "1.2.0", "profile_yaml": sample_profile_yaml}
        child = mgr.fork(parent, "domain-skill", backend="filesystem-handler")
        parsed = yaml.safe_load(child["profile_yaml"])
        assert parsed["backends"]["storage"] == "filesystem-handler"
        assert parsed["composition"]["base"] == "core-skill:1.2.0"

    def test_fork_with_domain_config(self, sample_profile_yaml):
        from contextledger.skill.fork import ForkManager
        mgr = ForkManager()
        parent = {"name": "core-skill", "version": "1.0.0", "profile_yaml": sample_profile_yaml}
        domain = {"extraction": {"entities": ["project", "emission"]}}
        child = mgr.fork(parent, "sustainability-skill", domain_config=domain)
        parsed = yaml.safe_load(child["profile_yaml"])
        assert "extraction" in parsed["composition"]["overrides"]
        assert "project" in parsed["composition"]["overrides"]["extraction"]["entities"]

    def test_fork_with_backend_and_domain(self, sample_profile_yaml):
        from contextledger.skill.fork import ForkManager
        mgr = ForkManager()
        parent = {"name": "core-skill", "version": "1.0.0", "profile_yaml": sample_profile_yaml}
        domain = {"extraction": {"entities": ["target"]}}
        child = mgr.fork(parent, "full-fork", backend="supabase-handler", domain_config=domain)
        parsed = yaml.safe_load(child["profile_yaml"])
        assert parsed["backends"]["storage"] == "supabase-handler"
        assert "extraction" in parsed["composition"]["overrides"]
        assert parsed["composition"]["base"] == "core-skill:1.0.0"

    def test_fork_without_layers_is_unchanged(self, sample_profile_yaml):
        """Existing fork without backend/domain_config works as before."""
        from contextledger.skill.fork import ForkManager
        mgr = ForkManager()
        parent = {"name": "parent-skill", "version": "1.0.0", "profile_yaml": sample_profile_yaml}
        child = mgr.fork(parent, "child-skill")
        parsed = yaml.safe_load(child["profile_yaml"])
        assert "composition" not in parsed
        assert "backends" not in parsed
        assert child["parent"] == "parent-skill"

    def test_resolve_three_layer_chain(self):
        """core → backend → domain should resolve correctly."""
        from contextledger.skill.fork import ForkManager
        mgr = ForkManager()

        core = {
            "name": "core",
            "version": "1.0.0",
            "parent": None,
            "extraction": {"entities": ["table", "finding"], "sources": ["db"]},
            "synthesis": {"dag": {"nodes": []}},
        }
        backend_layer = {
            "name": "backend-layer",
            "version": "1.0.0",
            "parent": "core",
            "backends": {"storage": "supabase"},
        }
        domain_layer = {
            "name": "domain-layer",
            "version": "1.0.0",
            "composition": {"base": "backend-layer:1.0.0"},
            "extraction": {"entities": ["emission", "target"]},
        }
        registry = {"core": core, "backend-layer": backend_layer}

        resolved = mgr.resolve(domain_layer, registry)
        # Domain entities override parent
        assert "emission" in resolved["extraction"]["entities"]
        # But synthesis comes from core
        assert "dag" in resolved.get("synthesis", {})
        # Backend slot from middle layer
        assert resolved.get("backends", {}).get("storage") == "supabase"


# ---------------------------------------------------------------------------
# GAP 1: Section-level inheritance
# ---------------------------------------------------------------------------


class TestSectionLevelInheritance:
    """Tests for composition.overrides section-level replacement."""

    def test_section_override_replaces_entirely(self):
        from contextledger.skill.fork import ForkManager
        mgr = ForkManager()

        parent = {
            "name": "parent",
            "version": "1.0.0",
            "parent": None,
            "extraction": {"entities": ["a", "b"], "sources": ["old"]},
            "synthesis": {"dag": {"nodes": []}},
        }
        child = {
            "name": "child",
            "version": "1.0.0",
            "parent": "parent",
            "composition": {
                "base": "parent:1.0.0",
                "overrides": {
                    "extraction": {"entities": ["x"], "sources": ["new"]},
                },
            },
        }
        registry = {"parent": parent}
        resolved = mgr.resolve(child, registry)
        # Extraction replaced entirely — not merged with parent
        assert resolved["extraction"]["entities"] == ["x"]
        assert resolved["extraction"]["sources"] == ["new"]
        # Synthesis inherited from parent
        assert "dag" in resolved["synthesis"]

    def test_override_single_section_inherits_rest(self):
        from contextledger.skill.fork import ForkManager
        mgr = ForkManager()

        parent = {
            "name": "parent",
            "version": "1.0.0",
            "parent": None,
            "extraction": {"entities": ["a"]},
            "synthesis": {"dag": {"nodes": []}},
            "memory_schema": {"graph_nodes": ["Entity"]},
        }
        child = {
            "name": "child",
            "version": "1.0.0",
            "parent": "parent",
            "composition": {
                "overrides": {
                    "synthesis": {"dag": {"nodes": [{"id": "new", "type": "extraction", "depends_on": []}]}},
                },
            },
        }
        registry = {"parent": parent}
        resolved = mgr.resolve(child, registry)
        # Synthesis replaced
        assert len(resolved["synthesis"]["dag"]["nodes"]) == 1
        assert resolved["synthesis"]["dag"]["nodes"][0]["id"] == "new"
        # Extraction and memory_schema inherited
        assert resolved["extraction"]["entities"] == ["a"]
        assert resolved["memory_schema"]["graph_nodes"] == ["Entity"]


# ---------------------------------------------------------------------------
# GAP 2: Backend plugin slots
# ---------------------------------------------------------------------------


class TestBackendPluginSlots:
    """Tests for backends: block in profile YAML."""

    def test_parser_reads_backends(self):
        from contextledger.skill.parser import ProfileParser
        parser = ProfileParser()
        profile = parser.parse("""
name: test-skill
version: 1.0.0
parent: null
backends:
  storage: supabase-handler:2.1
  embedding: jina-local:1.0
""")
        assert profile["backends"]["storage"] == "supabase-handler:2.1"
        assert profile["backends"]["embedding"] == "jina-local:1.0"

    def test_backends_inherited_and_overridable(self):
        from contextledger.skill.fork import ForkManager
        mgr = ForkManager()

        parent = {
            "name": "parent",
            "version": "1.0.0",
            "parent": None,
            "backends": {"storage": "sqlite", "embedding": "jina-local"},
            "extraction": {},
        }
        child = {
            "name": "child",
            "version": "1.0.0",
            "parent": "parent",
            "backends": {"storage": "supabase"},
        }
        registry = {"parent": parent}
        resolved = mgr.resolve(child, registry)
        # Storage overridden, embedding inherited
        assert resolved["backends"]["storage"] == "supabase"
        assert resolved["backends"]["embedding"] == "jina-local"


# ---------------------------------------------------------------------------
# GAP 4: Dependency declarations
# ---------------------------------------------------------------------------


class TestDependencyDeclarations:
    """Tests for requires: block and check_dependencies."""

    def test_parser_reads_requires(self):
        from contextledger.skill.parser import ProfileParser
        parser = ProfileParser()
        profile = parser.parse("""
name: test-skill
version: 1.0.0
parent: null
requires:
  core-skill: ">=1.2,<2.0"
  supabase-handler: ">=2.1"
""")
        assert profile["requires"]["core-skill"] == ">=1.2,<2.0"

    def test_check_deps_all_satisfied(self):
        from contextledger.skill.deps import check_dependencies
        registry = {
            "core-skill": {"name": "core-skill", "version": "1.5.0"},
            "domain-skill": {
                "name": "domain-skill",
                "version": "1.0.0",
                "requires": {"core-skill": ">=1.2,<2.0"},
            },
        }
        assert check_dependencies(registry) == []

    def test_check_deps_missing_dependency(self):
        from contextledger.skill.deps import check_dependencies
        registry = {
            "domain-skill": {
                "name": "domain-skill",
                "version": "1.0.0",
                "requires": {"core-skill": ">=1.0"},
            },
        }
        issues = check_dependencies(registry)
        assert len(issues) == 1
        assert "not in the registry" in issues[0]

    def test_check_deps_version_too_low(self):
        from contextledger.skill.deps import check_dependencies
        registry = {
            "core-skill": {"name": "core-skill", "version": "0.9.0"},
            "domain-skill": {
                "name": "domain-skill",
                "version": "1.0.0",
                "requires": {"core-skill": ">=1.2"},
            },
        }
        issues = check_dependencies(registry)
        assert len(issues) == 1
        assert "0.9.0" in issues[0]

    def test_check_deps_version_too_high(self):
        from contextledger.skill.deps import check_dependencies
        registry = {
            "core-skill": {"name": "core-skill", "version": "3.0.0"},
            "domain-skill": {
                "name": "domain-skill",
                "version": "1.0.0",
                "requires": {"core-skill": ">=1.0,<2.0"},
            },
        }
        issues = check_dependencies(registry)
        assert len(issues) == 1

    def test_check_deps_caret_notation(self):
        from contextledger.skill.deps import check_dependencies
        registry = {
            "core-skill": {"name": "core-skill", "version": "1.5.3"},
            "domain-skill": {
                "name": "domain-skill",
                "version": "1.0.0",
                "requires": {"core-skill": "^1.2"},
            },
        }
        assert check_dependencies(registry) == []

    def test_check_deps_caret_major_bump_fails(self):
        from contextledger.skill.deps import check_dependencies
        registry = {
            "core-skill": {"name": "core-skill", "version": "2.0.0"},
            "domain-skill": {
                "name": "domain-skill",
                "version": "1.0.0",
                "requires": {"core-skill": "^1.2"},
            },
        }
        issues = check_dependencies(registry)
        assert len(issues) == 1

    def test_no_requires_no_issues(self):
        from contextledger.skill.deps import check_dependencies
        registry = {
            "simple-skill": {"name": "simple-skill", "version": "1.0.0"},
        }
        assert check_dependencies(registry) == []

    def test_fork_version_suffix_stripped(self):
        from contextledger.skill.deps import check_dependencies
        registry = {
            "core-skill": {"name": "core-skill", "version": "1.5.0-fork-1"},
            "domain-skill": {
                "name": "domain-skill",
                "version": "1.0.0",
                "requires": {"core-skill": ">=1.2"},
            },
        }
        assert check_dependencies(registry) == []

    def test_exact_version_match(self):
        from contextledger.skill.deps import check_dependencies
        registry = {
            "core": {"name": "core", "version": "1.2.0"},
            "child": {
                "name": "child", "version": "1.0.0",
                "requires": {"core": "1.2.0"},
            },
        }
        assert check_dependencies(registry) == []

    def test_not_equal_version(self):
        from contextledger.skill.deps import check_dependencies
        registry = {
            "core": {"name": "core", "version": "1.0.0"},
            "child": {
                "name": "child", "version": "1.0.0",
                "requires": {"core": "!=1.0.0"},
            },
        }
        issues = check_dependencies(registry)
        assert len(issues) == 1

    def test_less_than_or_equal(self):
        from contextledger.skill.deps import check_dependencies
        registry = {
            "core": {"name": "core", "version": "2.0.0"},
            "child": {
                "name": "child", "version": "1.0.0",
                "requires": {"core": "<=2.0.0"},
            },
        }
        assert check_dependencies(registry) == []


# ---------------------------------------------------------------------------
# Parser: derived_from and unknown fields
# ---------------------------------------------------------------------------


class TestParserExtendedFields:
    """Tests for derived_from, unknown fields, etc."""

    def test_parser_reads_derived_from(self):
        from contextledger.skill.parser import ProfileParser
        parser = ProfileParser()
        profile = parser.parse("""
name: test-skill
version: 1.1.0
parent: null
derived_from:
  - snapshot_id: abc123
    findings_applied: [semantic-drift-v2]
""")
        assert len(profile["derived_from"]) == 1
        assert profile["derived_from"][0]["snapshot_id"] == "abc123"

    def test_parser_preserves_unknown_fields(self):
        from contextledger.skill.parser import ProfileParser
        parser = ProfileParser()
        profile = parser.parse("""
name: test-skill
version: 1.0.0
parent: null
custom_metadata:
  team: research
  priority: high
""")
        assert profile["custom_metadata"]["team"] == "research"
        assert profile["custom_metadata"]["priority"] == "high"


# ---------------------------------------------------------------------------
# Resolve: version pin warning
# ---------------------------------------------------------------------------


class TestVersionPinWarning:
    """Tests for composition.base version pin checks."""

    def test_resolve_warns_on_version_mismatch(self):
        import warnings
        from contextledger.skill.fork import ForkManager
        mgr = ForkManager()

        parent = {
            "name": "core",
            "version": "2.0.0",
            "parent": None,
            "extraction": {"entities": ["a"]},
        }
        child = {
            "name": "child",
            "version": "1.0.0",
            "composition": {"base": "core:1.0.0"},
        }
        registry = {"core": parent}
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            mgr.resolve(child, registry)
            assert len(w) == 1
            assert "core:1.0.0" in str(w[0].message)
            assert "2.0.0" in str(w[0].message)

    def test_resolve_no_warning_when_version_matches(self):
        import warnings
        from contextledger.skill.fork import ForkManager
        mgr = ForkManager()

        parent = {
            "name": "core",
            "version": "1.2.0",
            "parent": None,
            "extraction": {},
        }
        child = {
            "name": "child",
            "version": "1.0.0",
            "composition": {"base": "core:1.2"},
        }
        registry = {"core": parent}
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            mgr.resolve(child, registry)
            assert len(w) == 0
