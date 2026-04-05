"""Tests for ManifestParser and ManifestLocator.

Task: TASK-030 — Implement project manifest parser
"""

import os
import pytest

from contextledger.project.manifest import ManifestParser, ManifestLocator


VALID_MANIFEST = """
name: test-project
version: 1.0.0
skills:
  - skill-a
  - skill-b
default_skill: skill-a
fusion_enabled: true
routes:
  - skill: skill-a
    directories: [src/a/]
    keywords: [alpha, analysis]
  - skill: skill-b
    keywords: [beta, build]
    file_patterns: ["*.beta.py"]
"""


class TestManifestParser:
    def test_parse_valid_manifest(self):
        parser = ManifestParser()
        manifest = parser.parse(VALID_MANIFEST)
        assert manifest.name == "test-project"
        assert manifest.version == "1.0.0"
        assert manifest.skills == ["skill-a", "skill-b"]
        assert manifest.default_skill == "skill-a"
        assert manifest.fusion_enabled is True
        assert len(manifest.routes) == 2

    def test_parse_missing_name_raises(self):
        parser = ManifestParser()
        with pytest.raises(ValueError, match="name"):
            parser.parse("skills: [a]")

    def test_parse_missing_skills_raises(self):
        parser = ManifestParser()
        with pytest.raises(ValueError, match="skill"):
            parser.parse("name: test")

    def test_parse_empty_skills_raises(self):
        parser = ManifestParser()
        with pytest.raises(ValueError, match="skill"):
            parser.parse("name: test\nskills: []")

    def test_parse_route_missing_skill_raises(self):
        parser = ManifestParser()
        yaml = "name: test\nskills: [a]\nroutes:\n  - directories: [src/]"
        with pytest.raises(ValueError, match="skill"):
            parser.parse(yaml)

    def test_parse_route_missing_condition_raises(self):
        parser = ManifestParser()
        yaml = "name: test\nskills: [a]\nroutes:\n  - skill: a"
        with pytest.raises(ValueError, match="condition"):
            parser.parse(yaml)

    def test_parse_routes_with_priority(self):
        parser = ManifestParser()
        yaml = """
name: test
skills: [a]
routes:
  - skill: a
    keywords: [test]
    priority: 5
"""
        manifest = parser.parse(yaml)
        assert manifest.routes[0].priority == 5

    def test_parse_defaults(self):
        parser = ManifestParser()
        yaml = "name: test\nskills: [a]"
        manifest = parser.parse(yaml)
        assert manifest.version == "1.0.0"
        assert manifest.fusion_enabled is True
        assert manifest.default_skill is None
        assert manifest.routes == []

    def test_to_yaml_roundtrip(self):
        parser = ManifestParser()
        original = parser.parse(VALID_MANIFEST)
        yaml_str = parser.to_yaml(original)
        reparsed = parser.parse(yaml_str)
        assert reparsed.name == original.name
        assert reparsed.skills == original.skills
        assert len(reparsed.routes) == len(original.routes)


class TestManifestLocator:
    def test_finds_manifest_in_current_dir(self, tmp_path):
        manifest_dir = tmp_path / ".contextledger"
        manifest_dir.mkdir()
        (manifest_dir / "project.yaml").write_text("name: test\nskills: [a]")
        locator = ManifestLocator()
        result = locator.find(str(tmp_path))
        assert result is not None
        assert "project.yaml" in result

    def test_finds_manifest_in_parent_dir(self, tmp_path):
        manifest_dir = tmp_path / ".contextledger"
        manifest_dir.mkdir()
        (manifest_dir / "project.yaml").write_text("name: test\nskills: [a]")
        child = tmp_path / "src" / "deep"
        child.mkdir(parents=True)
        locator = ManifestLocator()
        result = locator.find(str(child))
        assert result is not None

    def test_returns_none_when_not_found(self, tmp_path):
        locator = ManifestLocator()
        result = locator.find(str(tmp_path))
        assert result is None

    def test_parse_file(self, tmp_path):
        manifest_dir = tmp_path / ".contextledger"
        manifest_dir.mkdir()
        manifest_path = manifest_dir / "project.yaml"
        manifest_path.write_text("name: test\nskills: [a]")
        parser = ManifestParser()
        manifest = parser.parse_file(str(manifest_path))
        assert manifest.name == "test"
        assert manifest.project_root == str(tmp_path)
