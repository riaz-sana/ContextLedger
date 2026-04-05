"""Tests for ProjectManager.

Task: TASK-033 — Implement project manager
"""

import os
import pytest

from contextledger.project.manager import ProjectManager


MANIFEST_YAML = """
name: test-project
version: 1.0.0
skills:
  - skill-a
  - skill-b
default_skill: skill-a
fusion_enabled: true
routes:
  - skill: skill-a
    keywords: [alpha]
  - skill: skill-b
    keywords: [beta]
"""


def _setup_project(tmp_path, yaml_content=MANIFEST_YAML):
    manifest_dir = tmp_path / ".contextledger"
    manifest_dir.mkdir()
    (manifest_dir / "project.yaml").write_text(yaml_content)
    return str(tmp_path)


class TestProjectManager:
    def test_load_from_explicit_path(self, tmp_path):
        root = _setup_project(tmp_path)
        mgr = ProjectManager()
        manifest = mgr.load(project_root=root)
        assert manifest.name == "test-project"
        assert mgr.is_loaded()

    def test_load_raises_when_no_manifest(self, tmp_path):
        mgr = ProjectManager()
        with pytest.raises(FileNotFoundError):
            mgr.load(project_root=str(tmp_path))

    def test_active_manifest_raises_before_load(self):
        mgr = ProjectManager()
        with pytest.raises(RuntimeError):
            mgr.active_manifest()

    def test_route_explicit_profile_overrides_all(self, tmp_path):
        root = _setup_project(tmp_path)
        mgr = ProjectManager()
        mgr.load(project_root=root)
        skill, reason = mgr.route(explicit_profile="skill-b")
        assert skill == "skill-b"
        assert "explicit" in reason

    def test_route_explicit_profile_not_in_manifest_raises(self, tmp_path):
        root = _setup_project(tmp_path)
        mgr = ProjectManager()
        mgr.load(project_root=root)
        with pytest.raises(ValueError, match="nonexistent"):
            mgr.route(explicit_profile="nonexistent")

    def test_route_auto_uses_router(self, tmp_path):
        root = _setup_project(tmp_path)
        mgr = ProjectManager()
        mgr.load(project_root=root)
        skill, reason = mgr.route(query="alpha test")
        assert skill == "skill-a"
        assert "keyword" in reason

    def test_query_all_queries_each_skill(self, tmp_path):
        root = _setup_project(tmp_path)
        mgr = ProjectManager()
        mgr.load(project_root=root)
        result = mgr.query_all("test query")
        assert "skill-a" in result.results_by_skill
        assert "skill-b" in result.results_by_skill

    def test_query_all_handles_no_memory(self, tmp_path):
        """Without memory system, should return empty results gracefully."""
        root = _setup_project(tmp_path)
        mgr = ProjectManager()
        mgr.load(project_root=root)
        result = mgr.query_all("test")
        for skill, results in result.results_by_skill.items():
            assert results == []

    def test_query_routed_uses_routing_result(self, tmp_path):
        root = _setup_project(tmp_path)
        mgr = ProjectManager()
        mgr.load(project_root=root)
        result = mgr.query_routed("beta feature", explicit_profile="skill-b")
        assert result.active_skill == "skill-b"
        assert "explicit" in result.routing_reason
