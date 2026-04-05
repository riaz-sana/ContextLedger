"""Tests for stub RegistryBackend.

Task: TASK-002 — Define Protocol classes and stub backends
"""

import pytest


class TestStubRegistryBackend:
    def test_save_and_get(self, sample_profile_yaml):
        from contextledger.backends.registry.stub import StubRegistryBackend
        backend = StubRegistryBackend()
        bundle = {"name": "test", "version": "1.0.0", "profile_yaml": sample_profile_yaml}
        vid = backend.save_profile(bundle)
        assert isinstance(vid, str)
        result = backend.get_profile("test")
        assert result["name"] == "test"

    def test_list_profiles(self, sample_profile_yaml):
        from contextledger.backends.registry.stub import StubRegistryBackend
        backend = StubRegistryBackend()
        backend.save_profile({"name": "a", "version": "1.0.0", "profile_yaml": sample_profile_yaml})
        backend.save_profile({"name": "b", "version": "1.0.0", "profile_yaml": sample_profile_yaml})
        profiles = backend.list_profiles()
        assert len(profiles) == 2

    def test_fork(self, sample_profile_yaml):
        from contextledger.backends.registry.stub import StubRegistryBackend
        backend = StubRegistryBackend()
        backend.save_profile({"name": "parent", "version": "1.0.0", "profile_yaml": sample_profile_yaml})
        forked = backend.fork_profile("parent", "child")
        assert forked["parent"] == "parent"
        assert forked["name"] == "child"

    def test_list_versions(self, sample_profile_yaml):
        from contextledger.backends.registry.stub import StubRegistryBackend
        backend = StubRegistryBackend()
        for v in ["1.0.0", "1.1.0"]:
            backend.save_profile({"name": "s", "version": v, "profile_yaml": sample_profile_yaml})
        versions = backend.list_versions("s")
        assert "1.0.0" in versions
        assert "1.1.0" in versions

    def test_get_diff(self, sample_profile_yaml):
        from contextledger.backends.registry.stub import StubRegistryBackend
        backend = StubRegistryBackend()
        backend.save_profile({"name": "a", "version": "1.0.0", "profile_yaml": sample_profile_yaml})
        backend.save_profile({"name": "b", "version": "1.0.0", "profile_yaml": sample_profile_yaml})
        diff = backend.get_diff("a", "b")
        assert diff is not None
