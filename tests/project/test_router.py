"""Tests for SkillRouter.

Task: TASK-031 — Implement skill router
"""

import pytest

from contextledger.core.types import ProjectManifest, SkillRoute
from contextledger.project.router import SkillRouter


def _make_manifest(routes=None, default_skill=None, skills=None, project_root="/project"):
    return ProjectManifest(
        name="test",
        skills=["skill-a", "skill-b", "skill-c"] if skills is None else skills,
        routes=routes or [],
        default_skill=default_skill,
        project_root=project_root,
    )


class TestRouteByDirectory:
    def test_exact_match(self, tmp_path):
        src_a = tmp_path / "src" / "a"
        src_a.mkdir(parents=True)
        manifest = _make_manifest(
            routes=[SkillRoute(skill_name="skill-a", directories=["src/a/"])],
            project_root=str(tmp_path),
        )
        router = SkillRouter()
        skill, reason = router.route_by_directory(manifest, str(src_a))
        assert skill == "skill-a"
        assert "directory" in reason

    def test_subdirectory_match(self, tmp_path):
        deep = tmp_path / "src" / "a" / "deep" / "nested"
        deep.mkdir(parents=True)
        manifest = _make_manifest(
            routes=[SkillRoute(skill_name="skill-a", directories=["src/a/"])],
            project_root=str(tmp_path),
        )
        router = SkillRouter()
        skill, _ = router.route_by_directory(manifest, str(deep))
        assert skill == "skill-a"

    def test_most_specific_wins(self, tmp_path):
        deep = tmp_path / "src" / "a" / "sub"
        deep.mkdir(parents=True)
        manifest = _make_manifest(
            routes=[
                SkillRoute(skill_name="broad", directories=["src/"]),
                SkillRoute(skill_name="specific", directories=["src/a/"]),
            ],
            project_root=str(tmp_path),
        )
        router = SkillRouter()
        skill, _ = router.route_by_directory(manifest, str(deep))
        assert skill == "specific"

    def test_no_match_returns_none(self, tmp_path):
        manifest = _make_manifest(
            routes=[SkillRoute(skill_name="skill-a", directories=["src/a/"])],
            project_root=str(tmp_path),
        )
        router = SkillRouter()
        skill, _ = router.route_by_directory(manifest, str(tmp_path / "other"))
        assert skill is None


class TestRouteByKeywords:
    def test_single_match(self):
        manifest = _make_manifest(
            routes=[SkillRoute(skill_name="skill-a", keywords=["alpha", "analysis"])]
        )
        router = SkillRouter()
        skill, reason = router.route_by_keywords(manifest, "run alpha analysis")
        assert skill == "skill-a"
        assert "keyword" in reason

    def test_multiple_matches_most_keywords_wins(self):
        manifest = _make_manifest(
            routes=[
                SkillRoute(skill_name="few", keywords=["test"]),
                SkillRoute(skill_name="many", keywords=["test", "analysis", "data"]),
            ]
        )
        router = SkillRouter()
        skill, _ = router.route_by_keywords(manifest, "test analysis data pipeline")
        assert skill == "many"

    def test_no_match_returns_none(self):
        manifest = _make_manifest(
            routes=[SkillRoute(skill_name="skill-a", keywords=["alpha"])]
        )
        router = SkillRouter()
        skill, _ = router.route_by_keywords(manifest, "something unrelated")
        assert skill is None


class TestRouteByFilePattern:
    def test_match(self):
        manifest = _make_manifest(
            routes=[SkillRoute(skill_name="skill-a", file_patterns=["*.detector.py"])]
        )
        router = SkillRouter()
        skill, reason = router.route_by_file_pattern(manifest, "retry.detector.py")
        assert skill == "skill-a"
        assert "file pattern" in reason

    def test_no_match(self):
        manifest = _make_manifest(
            routes=[SkillRoute(skill_name="skill-a", file_patterns=["*.detector.py"])]
        )
        router = SkillRouter()
        skill, _ = router.route_by_file_pattern(manifest, "main.py")
        assert skill is None


class TestRouteFullChain:
    def test_directory_first(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        manifest = _make_manifest(
            routes=[
                SkillRoute(skill_name="dir-skill", directories=["src/"]),
                SkillRoute(skill_name="kw-skill", keywords=["test"]),
            ],
            project_root=str(tmp_path),
        )
        router = SkillRouter()
        skill, _ = router.route(manifest, query="test", current_dir=str(src))
        assert skill == "dir-skill"

    def test_falls_back_to_keywords(self):
        manifest = _make_manifest(
            routes=[SkillRoute(skill_name="kw-skill", keywords=["detector"])],
        )
        router = SkillRouter()
        skill, _ = router.route(manifest, query="retry detector issue")
        assert skill == "kw-skill"

    def test_falls_back_to_default(self):
        manifest = _make_manifest(default_skill="fallback")
        router = SkillRouter()
        skill, reason = router.route(manifest, query="nothing matches")
        assert skill == "fallback"
        assert "default" in reason

    def test_falls_back_to_first_skill(self):
        manifest = _make_manifest(skills=["first", "second"])
        router = SkillRouter()
        skill, reason = router.route(manifest, query="nothing")
        assert skill == "first"
        assert "first declared" in reason

    def test_route_all_returns_all_skills(self):
        manifest = _make_manifest(skills=["a", "b", "c"])
        router = SkillRouter()
        assert router.route_all(manifest) == ["a", "b", "c"]

    def test_no_skills_no_default_raises(self):
        """Manifest with no skills and no default should raise ValueError."""
        manifest = _make_manifest(skills=[], default_skill=None)
        router = SkillRouter()
        with pytest.raises(ValueError, match="no skills"):
            router.route(manifest, query="test")
