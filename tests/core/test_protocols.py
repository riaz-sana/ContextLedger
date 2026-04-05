"""Tests for backend protocol contracts.

Validates that any implementation of StorageBackend, EmbeddingBackend,
or RegistryBackend satisfies the interface contract.

These tests run against stub backends first, then parameterize
to run against real implementations as they're built.

Task: TASK-002 — Define Protocol classes and stub backends
"""

import pytest
from typing import Protocol, runtime_checkable


class TestStorageBackendProtocol:
    """Verify StorageBackend protocol contract."""

    def test_protocol_is_runtime_checkable(self):
        """StorageBackend must be decorated with @runtime_checkable."""
        from contextledger.core.protocols import StorageBackend
        assert isinstance(StorageBackend, type)
        # Protocol should be usable with isinstance checks
        assert hasattr(StorageBackend, '__protocol_attrs__') or issubclass(StorageBackend, Protocol)

    def test_stub_implements_protocol(self):
        """Stub backend must satisfy StorageBackend protocol."""
        from contextledger.core.protocols import StorageBackend
        from contextledger.backends.storage.stub import StubStorageBackend
        backend = StubStorageBackend()
        assert isinstance(backend, StorageBackend)

    def test_write_returns_id(self, sample_memory_unit):
        """write() must return a string ID."""
        from contextledger.backends.storage.stub import StubStorageBackend
        backend = StubStorageBackend()
        result = backend.write(sample_memory_unit)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_read_returns_unit_or_none(self, sample_memory_unit):
        """read() must return MemoryUnit or None."""
        from contextledger.backends.storage.stub import StubStorageBackend
        backend = StubStorageBackend()
        unit_id = backend.write(sample_memory_unit)
        result = backend.read(unit_id)
        assert result is not None
        # Non-existent ID should return None
        assert backend.read("nonexistent-id") is None

    def test_search_returns_list(self):
        """search() must return a list of MemoryUnits, limited by limit param."""
        from contextledger.backends.storage.stub import StubStorageBackend
        backend = StubStorageBackend()
        results = backend.search(query_embedding=[0.1] * 128, limit=5)
        assert isinstance(results, list)
        assert len(results) <= 5

    def test_traverse_returns_list(self):
        """traverse() must return a list of related MemoryUnits."""
        from contextledger.backends.storage.stub import StubStorageBackend
        backend = StubStorageBackend()
        results = backend.traverse(node_id="mem-001", depth=2)
        assert isinstance(results, list)

    def test_delete_returns_bool(self, sample_memory_unit):
        """delete() must return True on success, False on not found."""
        from contextledger.backends.storage.stub import StubStorageBackend
        backend = StubStorageBackend()
        unit_id = backend.write(sample_memory_unit)
        assert backend.delete(unit_id) is True
        assert backend.delete("nonexistent") is False

    def test_list_by_profile_returns_list(self, sample_memory_unit):
        """list_by_profile() must return all units for a given profile."""
        from contextledger.backends.storage.stub import StubStorageBackend
        backend = StubStorageBackend()
        backend.write(sample_memory_unit)
        results = backend.list_by_profile(sample_memory_unit["profile_name"])
        assert isinstance(results, list)

    def test_write_read_roundtrip(self, sample_memory_unit):
        """Writing and reading a unit should preserve content."""
        from contextledger.backends.storage.stub import StubStorageBackend
        backend = StubStorageBackend()
        unit_id = backend.write(sample_memory_unit)
        result = backend.read(unit_id)
        assert result["content"] == sample_memory_unit["content"]
        assert result["unit_type"] == sample_memory_unit["unit_type"]

    def test_delete_then_read_returns_none(self, sample_memory_unit):
        """Deleted units must not be readable."""
        from contextledger.backends.storage.stub import StubStorageBackend
        backend = StubStorageBackend()
        unit_id = backend.write(sample_memory_unit)
        backend.delete(unit_id)
        assert backend.read(unit_id) is None


class TestEmbeddingBackendProtocol:
    """Verify EmbeddingBackend protocol contract."""

    def test_stub_implements_protocol(self):
        """Stub backend must satisfy EmbeddingBackend protocol."""
        from contextledger.core.protocols import EmbeddingBackend
        from contextledger.backends.embedding.stub import StubEmbeddingBackend
        backend = StubEmbeddingBackend()
        assert isinstance(backend, EmbeddingBackend)

    def test_encode_returns_float_list(self):
        """encode() must return a list of floats."""
        from contextledger.backends.embedding.stub import StubEmbeddingBackend
        backend = StubEmbeddingBackend()
        result = backend.encode("test text")
        assert isinstance(result, list)
        assert all(isinstance(x, float) for x in result)
        assert len(result) > 0

    def test_encode_batch_returns_list_of_lists(self):
        """encode_batch() must return a list of embedding vectors."""
        from contextledger.backends.embedding.stub import StubEmbeddingBackend
        backend = StubEmbeddingBackend()
        texts = ["text one", "text two", "text three"]
        results = backend.encode_batch(texts)
        assert isinstance(results, list)
        assert len(results) == 3
        assert all(isinstance(r, list) for r in results)

    def test_encode_batch_dimensions_consistent(self):
        """All embeddings from encode_batch must have the same dimensionality."""
        from contextledger.backends.embedding.stub import StubEmbeddingBackend
        backend = StubEmbeddingBackend()
        results = backend.encode_batch(["a", "b", "c"])
        dimensions = [len(r) for r in results]
        assert len(set(dimensions)) == 1  # all same length

    def test_encode_and_encode_batch_same_dimensions(self):
        """Single encode and batch encode must produce same-dimensional vectors."""
        from contextledger.backends.embedding.stub import StubEmbeddingBackend
        backend = StubEmbeddingBackend()
        single = backend.encode("test")
        batch = backend.encode_batch(["test"])
        assert len(single) == len(batch[0])

    def test_similarity_returns_float(self):
        """similarity() must return a float between -1 and 1."""
        from contextledger.backends.embedding.stub import StubEmbeddingBackend
        backend = StubEmbeddingBackend()
        a = backend.encode("hello")
        b = backend.encode("world")
        sim = backend.similarity(a, b)
        assert isinstance(sim, float)
        assert -1.0 <= sim <= 1.0

    def test_similarity_identical_vectors(self):
        """Identical vectors should have similarity of 1.0 (or very close)."""
        from contextledger.backends.embedding.stub import StubEmbeddingBackend
        backend = StubEmbeddingBackend()
        a = backend.encode("identical text")
        sim = backend.similarity(a, a)
        assert sim == pytest.approx(1.0, abs=0.01)

    def test_encode_empty_string(self):
        """encode() should handle empty string without error."""
        from contextledger.backends.embedding.stub import StubEmbeddingBackend
        backend = StubEmbeddingBackend()
        result = backend.encode("")
        assert isinstance(result, list)
        assert len(result) > 0


class TestRegistryBackendProtocol:
    """Verify RegistryBackend protocol contract."""

    def test_stub_implements_protocol(self):
        """Stub backend must satisfy RegistryBackend protocol."""
        from contextledger.core.protocols import RegistryBackend
        from contextledger.backends.registry.stub import StubRegistryBackend
        backend = StubRegistryBackend()
        assert isinstance(backend, RegistryBackend)

    def test_list_profiles_returns_list(self):
        """list_profiles() must return a list of ProfileMetadata."""
        from contextledger.backends.registry.stub import StubRegistryBackend
        backend = StubRegistryBackend()
        results = backend.list_profiles()
        assert isinstance(results, list)

    def test_list_profiles_with_filter(self):
        """list_profiles() should accept an optional filter dict."""
        from contextledger.backends.registry.stub import StubRegistryBackend
        backend = StubRegistryBackend()
        results = backend.list_profiles(filter={"parent": "base-research-skill"})
        assert isinstance(results, list)

    def test_save_and_get_profile(self, sample_profile_yaml):
        """save_profile() then get_profile() should roundtrip."""
        from contextledger.backends.registry.stub import StubRegistryBackend
        backend = StubRegistryBackend()
        bundle = {
            "name": "test-skill",
            "version": "1.0.0",
            "profile_yaml": sample_profile_yaml,
            "parent": None,
        }
        version_id = backend.save_profile(bundle)
        assert isinstance(version_id, str)
        retrieved = backend.get_profile("test-skill")
        assert retrieved is not None
        assert retrieved["name"] == "test-skill"

    def test_get_profile_specific_version(self, sample_profile_yaml):
        """get_profile() with version should return that specific version."""
        from contextledger.backends.registry.stub import StubRegistryBackend
        backend = StubRegistryBackend()
        bundle = {
            "name": "test-skill",
            "version": "1.0.0",
            "profile_yaml": sample_profile_yaml,
        }
        backend.save_profile(bundle)
        result = backend.get_profile("test-skill", version="1.0.0")
        assert result is not None

    def test_get_nonexistent_profile(self):
        """get_profile() for missing name should return None or raise."""
        from contextledger.backends.registry.stub import StubRegistryBackend
        backend = StubRegistryBackend()
        result = backend.get_profile("nonexistent")
        assert result is None

    def test_fork_profile(self, sample_profile_yaml):
        """fork_profile() should create a child profile inheriting from parent."""
        from contextledger.backends.registry.stub import StubRegistryBackend
        backend = StubRegistryBackend()
        parent = {
            "name": "parent-skill",
            "version": "1.0.0",
            "profile_yaml": sample_profile_yaml,
        }
        backend.save_profile(parent)
        forked = backend.fork_profile("parent-skill", "child-skill")
        assert forked is not None
        assert forked["name"] == "child-skill"
        assert forked["parent"] == "parent-skill"

    def test_list_versions(self, sample_profile_yaml):
        """list_versions() should return all version strings for a profile."""
        from contextledger.backends.registry.stub import StubRegistryBackend
        backend = StubRegistryBackend()
        for v in ["1.0.0", "1.1.0", "2.0.0"]:
            backend.save_profile({
                "name": "versioned-skill",
                "version": v,
                "profile_yaml": sample_profile_yaml,
            })
        versions = backend.list_versions("versioned-skill")
        assert isinstance(versions, list)
        assert len(versions) == 3

    def test_get_diff(self, sample_profile_yaml):
        """get_diff() should return a ProfileDiff between two profiles."""
        from contextledger.backends.registry.stub import StubRegistryBackend
        backend = StubRegistryBackend()
        backend.save_profile({"name": "a", "version": "1.0.0", "profile_yaml": sample_profile_yaml})
        backend.save_profile({"name": "b", "version": "1.0.0", "profile_yaml": sample_profile_yaml})
        diff = backend.get_diff("a", "b")
        assert diff is not None
        assert hasattr(diff, "changed_sections") or "changed_sections" in diff
