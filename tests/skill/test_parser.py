"""Tests for profile YAML parser and validator.

Validates parsing of profile.yaml files including
extraction rules, synthesis DAG, memory schema, and session context.

Task: TASK-006 — Implement profile YAML parser/validator
"""

import pytest


class TestProfileParsing:
    """Test parsing of well-formed profile YAML."""

    def test_parse_valid_profile(self, sample_profile_yaml):
        """Should parse a valid profile YAML string into a structured object."""
        from contextledger.skill.parser import ProfileParser
        parser = ProfileParser()
        profile = parser.parse(sample_profile_yaml)
        assert profile["name"] == "supervised-db-research"
        assert profile["version"] == "1.0.0"

    def test_parse_extracts_entities(self, sample_profile_yaml):
        """Should extract entity types from extraction section."""
        from contextledger.skill.parser import ProfileParser
        parser = ProfileParser()
        profile = parser.parse(sample_profile_yaml)
        entities = profile["extraction"]["entities"]
        assert "table" in entities
        assert "finding" in entities

    def test_parse_extracts_sources(self, sample_profile_yaml):
        """Should extract data sources from extraction section."""
        from contextledger.skill.parser import ProfileParser
        parser = ProfileParser()
        profile = parser.parse(sample_profile_yaml)
        sources = profile["extraction"]["sources"]
        assert "supervised_database" in sources

    def test_parse_extracts_dag(self, sample_profile_yaml):
        """Should parse the synthesis DAG with nodes and dependencies."""
        from contextledger.skill.parser import ProfileParser
        parser = ProfileParser()
        profile = parser.parse(sample_profile_yaml)
        dag = profile["synthesis"]["dag"]
        assert "nodes" in dag
        assert len(dag["nodes"]) == 3
        # Check dependency chain
        extract = next(n for n in dag["nodes"] if n["id"] == "extract_entities")
        assert extract["depends_on"] == []
        build = next(n for n in dag["nodes"] if n["id"] == "build_relationships")
        assert "extract_entities" in build["depends_on"]

    def test_parse_extracts_templates(self, sample_profile_yaml):
        """Should parse synthesis templates."""
        from contextledger.skill.parser import ProfileParser
        parser = ProfileParser()
        profile = parser.parse(sample_profile_yaml)
        templates = profile["synthesis"]["templates"]
        assert len(templates) >= 1
        assert templates[0]["id"] == "find_patterns"
        assert "prompt" in templates[0]

    def test_parse_extracts_memory_schema(self, sample_profile_yaml):
        """Should parse graph nodes and edges in memory schema."""
        from contextledger.skill.parser import ProfileParser
        parser = ProfileParser()
        profile = parser.parse(sample_profile_yaml)
        schema = profile["memory_schema"]
        assert "Entity" in schema["graph_nodes"]
        assert len(schema["graph_edges"]) == 2

    def test_parse_extracts_session_context(self, sample_profile_yaml):
        """Should parse session context settings."""
        from contextledger.skill.parser import ProfileParser
        parser = ProfileParser()
        profile = parser.parse(sample_profile_yaml)
        ctx = profile["session_context"]
        assert ctx["mode"] == "skill_versioning"
        assert ctx["cmv_enabled"] is True
        assert ctx["trim_threshold"] == 0.3
        assert ctx["memory_tiers"]["immediate_turns"] == 10

    def test_parse_fork_profile(self, sample_fork_yaml):
        """Should parse a fork profile with parent reference."""
        from contextledger.skill.parser import ProfileParser
        parser = ProfileParser()
        profile = parser.parse(sample_fork_yaml)
        assert profile["parent"] == "supervised-db-research"
        assert profile["name"] == "filesystem-research"

    def test_parse_base_profile_parent_null(self, sample_profile_yaml):
        """Base profiles should have parent=None."""
        from contextledger.skill.parser import ProfileParser
        parser = ProfileParser()
        profile = parser.parse(sample_profile_yaml)
        assert profile["parent"] is None


class TestProfileValidation:
    """Test validation of profile YAML against schema rules."""

    def test_reject_missing_name(self):
        """Profile without name should be rejected."""
        from contextledger.skill.parser import ProfileParser
        parser = ProfileParser()
        bad_yaml = "version: 1.0.0\nparent: null\n"
        with pytest.raises((ValueError, KeyError)):
            parser.validate(parser.parse(bad_yaml))

    def test_reject_missing_version(self):
        """Profile without version should be rejected."""
        from contextledger.skill.parser import ProfileParser
        parser = ProfileParser()
        bad_yaml = "name: test\nparent: null\n"
        with pytest.raises((ValueError, KeyError)):
            parser.validate(parser.parse(bad_yaml))

    def test_reject_cyclic_dag(self):
        """DAG with cycles should be rejected."""
        from contextledger.skill.parser import ProfileParser
        parser = ProfileParser()
        cyclic_yaml = """name: test
version: 1.0.0
parent: null
synthesis:
  dag:
    nodes:
      - id: a
        type: extraction
        depends_on: [b]
      - id: b
        type: reasoning
        depends_on: [a]
"""
        profile = parser.parse(cyclic_yaml)
        with pytest.raises(ValueError, match="[Cc]ycl"):
            parser.validate(profile)

    def test_reject_invalid_node_type(self):
        """DAG nodes with invalid type should be rejected."""
        from contextledger.skill.parser import ProfileParser
        parser = ProfileParser()
        bad_yaml = """name: test
version: 1.0.0
parent: null
synthesis:
  dag:
    nodes:
      - id: a
        type: invalid_type
        depends_on: []
"""
        profile = parser.parse(bad_yaml)
        with pytest.raises(ValueError):
            parser.validate(profile)

    def test_reject_missing_dependency(self):
        """DAG nodes referencing non-existent dependencies should be rejected."""
        from contextledger.skill.parser import ProfileParser
        parser = ProfileParser()
        bad_yaml = """name: test
version: 1.0.0
parent: null
synthesis:
  dag:
    nodes:
      - id: a
        type: extraction
        depends_on: [nonexistent_node]
"""
        profile = parser.parse(bad_yaml)
        with pytest.raises(ValueError):
            parser.validate(profile)

    def test_valid_profile_passes(self, sample_profile_yaml):
        """A well-formed profile should pass validation."""
        from contextledger.skill.parser import ProfileParser
        parser = ProfileParser()
        profile = parser.parse(sample_profile_yaml)
        # Should not raise
        parser.validate(profile)

    def test_validate_extraction_rules(self, sample_profile_yaml):
        """Extraction rules should have match pattern and extract field."""
        from contextledger.skill.parser import ProfileParser
        parser = ProfileParser()
        profile = parser.parse(sample_profile_yaml)
        for rule in profile["extraction"]["rules"]:
            assert "match" in rule
            assert "extract" in rule

    def test_validate_confidence_threshold_range(self):
        """confidence_threshold must be between 0 and 1."""
        from contextledger.skill.parser import ProfileParser
        parser = ProfileParser()
        bad_yaml = """name: test
version: 1.0.0
parent: null
extraction:
  entities: [finding]
  sources: [test]
  rules:
    - match: "test"
      extract: finding
      confidence_threshold: 1.5
"""
        profile = parser.parse(bad_yaml)
        with pytest.raises(ValueError):
            parser.validate(profile)
