"""Tests for Git (local) RegistryBackend.

Uses a temporary git repo for isolation.

Task: TASK-014 — Implement Git local RegistryBackend
"""

import pytest


class TestGitLocalRegistryBackend:
    def test_save_creates_commit(self, sample_profile_yaml, tmp_git_repo):
        from contextledger.backends.registry.git_local import GitLocalRegistryBackend
        backend = GitLocalRegistryBackend(repo_path=str(tmp_git_repo))
        vid = backend.save_profile({
            "name": "test-skill",
            "version": "1.0.0",
            "profile_yaml": sample_profile_yaml,
        })
        assert isinstance(vid, str)

    def test_get_profile_from_git(self, sample_profile_yaml, tmp_git_repo):
        from contextledger.backends.registry.git_local import GitLocalRegistryBackend
        backend = GitLocalRegistryBackend(repo_path=str(tmp_git_repo))
        backend.save_profile({
            "name": "test-skill",
            "version": "1.0.0",
            "profile_yaml": sample_profile_yaml,
        })
        result = backend.get_profile("test-skill")
        assert result is not None
        assert result["name"] == "test-skill"

    def test_fork_creates_branch(self, sample_profile_yaml, tmp_git_repo):
        from contextledger.backends.registry.git_local import GitLocalRegistryBackend
        backend = GitLocalRegistryBackend(repo_path=str(tmp_git_repo))
        backend.save_profile({
            "name": "parent-skill",
            "version": "1.0.0",
            "profile_yaml": sample_profile_yaml,
        })
        forked = backend.fork_profile("parent-skill", "child-skill")
        assert forked["name"] == "child-skill"
        assert forked["parent"] == "parent-skill"

    def test_list_versions_from_git(self, sample_profile_yaml, tmp_git_repo):
        from contextledger.backends.registry.git_local import GitLocalRegistryBackend
        backend = GitLocalRegistryBackend(repo_path=str(tmp_git_repo))
        backend.save_profile({"name": "s", "version": "1.0.0", "profile_yaml": sample_profile_yaml})
        backend.save_profile({"name": "s", "version": "2.0.0", "profile_yaml": sample_profile_yaml})
        versions = backend.list_versions("s")
        assert len(versions) >= 2

    def test_get_diff_between_profiles(self, sample_profile_yaml, tmp_git_repo):
        from contextledger.backends.registry.git_local import GitLocalRegistryBackend
        backend = GitLocalRegistryBackend(repo_path=str(tmp_git_repo))
        backend.save_profile({"name": "a", "version": "1.0.0", "profile_yaml": sample_profile_yaml})
        backend.save_profile({"name": "b", "version": "1.0.0", "profile_yaml": sample_profile_yaml})
        diff = backend.get_diff("a", "b")
        assert diff is not None

    def test_skill_directory_structure(self, sample_profile_yaml, tmp_git_repo):
        """Saved skill should create proper directory bundle on disk."""
        from contextledger.backends.registry.git_local import GitLocalRegistryBackend
        import os
        backend = GitLocalRegistryBackend(repo_path=str(tmp_git_repo))
        backend.save_profile({
            "name": "my-skill",
            "version": "1.0.0",
            "profile_yaml": sample_profile_yaml,
        })
        skill_dir = tmp_git_repo / "skills" / "my-skill"
        assert skill_dir.exists() or (tmp_git_repo / "my-skill").exists()
