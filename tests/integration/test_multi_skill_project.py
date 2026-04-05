"""End-to-end tests for multi-skill project mode.

Task: TASK-034 — Integration test: multi-skill project
"""

import os
import pytest

from contextledger.project.manager import ProjectManager
from contextledger.project.manifest import ManifestParser
from contextledger.project.router import SkillRouter
from contextledger.project.fusion import ContextFuser
from contextledger.core.types import ProjectManifest, SkillRoute


GENOPT_MANIFEST = """
name: genopt
version: 1.0.0
skills:
  - sdk-skill
  - analyzer-skill
  - api-skill
default_skill: analyzer-skill
fusion_enabled: true
routes:
  - skill: sdk-skill
    directories: [sdk/]
    keywords: [instrumentation, tracker, buffer, sdk]
  - skill: analyzer-skill
    directories: [analyzer/]
    keywords: [detector, detection, analysis, quality]
  - skill: api-skill
    directories: [api/]
    keywords: [endpoint, route, fastapi, api]
"""


class TestMultiSkillProject:
    def _setup_genopt(self, tmp_path):
        # Create project structure
        (tmp_path / ".contextledger").mkdir()
        (tmp_path / ".contextledger" / "project.yaml").write_text(GENOPT_MANIFEST)
        (tmp_path / "sdk" / "src").mkdir(parents=True)
        (tmp_path / "analyzer" / "src").mkdir(parents=True)
        (tmp_path / "api" / "src").mkdir(parents=True)
        return str(tmp_path)

    def test_full_project_setup(self, tmp_path):
        root = self._setup_genopt(tmp_path)
        parser = ManifestParser()
        manifest = parser.parse(GENOPT_MANIFEST)
        assert manifest.name == "genopt"
        assert len(manifest.skills) == 3
        assert len(manifest.routes) == 3

    def test_routing_to_sdk_by_directory(self, tmp_path):
        root = self._setup_genopt(tmp_path)
        mgr = ProjectManager()
        mgr.load(project_root=root)
        skill, reason = mgr.route(current_dir=str(tmp_path / "sdk" / "src"))
        assert skill == "sdk-skill"

    def test_routing_to_analyzer_by_directory(self, tmp_path):
        root = self._setup_genopt(tmp_path)
        mgr = ProjectManager()
        mgr.load(project_root=root)
        skill, _ = mgr.route(current_dir=str(tmp_path / "analyzer" / "src"))
        assert skill == "analyzer-skill"

    def test_routing_by_keywords_at_root(self, tmp_path):
        root = self._setup_genopt(tmp_path)
        mgr = ProjectManager()
        mgr.load(project_root=root)
        skill, _ = mgr.route(query="how does the detector work")
        assert skill == "analyzer-skill"

    def test_routing_falls_back_to_default(self, tmp_path):
        root = self._setup_genopt(tmp_path)
        mgr = ProjectManager()
        mgr.load(project_root=root)
        skill, reason = mgr.route(query="something unrelated")
        assert skill == "analyzer-skill"
        assert "default" in reason

    def test_cross_skill_query(self, tmp_path):
        root = self._setup_genopt(tmp_path)
        mgr = ProjectManager()
        mgr.load(project_root=root)
        result = mgr.query_all("how does the sdk pass data to the analyzer")
        assert "sdk-skill" in result.results_by_skill
        assert "analyzer-skill" in result.results_by_skill
        assert "api-skill" in result.results_by_skill

    def test_fusion_dedup(self):
        fuser = ContextFuser()
        results_by_skill = {
            "sdk-skill": [{"id": "1", "content": "shared finding about data flow", "metadata": {}}],
            "analyzer-skill": [{"id": "2", "content": "shared finding about data flow", "metadata": {}}],
        }
        result = fuser.fuse("data flow", results_by_skill)
        assert len(result.fused_results) == 1
        meta = result.fused_results[0]["metadata"]
        assert meta["cross_skill"] is True
        assert "sdk-skill" in meta["source_skills"]
        assert "analyzer-skill" in meta["source_skills"]

    def test_explicit_profile_override(self, tmp_path):
        root = self._setup_genopt(tmp_path)
        mgr = ProjectManager()
        mgr.load(project_root=root)
        result = mgr.query_routed(
            "anything", explicit_profile="api-skill",
            current_dir=str(tmp_path / "sdk"),
        )
        assert result.active_skill == "api-skill"
