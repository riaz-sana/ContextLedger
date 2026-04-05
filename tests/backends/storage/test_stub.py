"""Tests for stub StorageBackend.

The stub backend is the first implementation — returns mock data,
validates the protocol contract works end-to-end.

Task: TASK-002 — Define Protocol classes and stub backends
"""

import pytest


class TestStubStorageBackend:
    """Validate StubStorageBackend implements the full protocol."""

    def test_write_and_read(self, sample_memory_unit):
        from contextledger.backends.storage.stub import StubStorageBackend
        backend = StubStorageBackend()
        uid = backend.write(sample_memory_unit)
        result = backend.read(uid)
        assert result is not None
        assert result["content"] == sample_memory_unit["content"]

    def test_write_multiple(self, sample_memory_units):
        from contextledger.backends.storage.stub import StubStorageBackend
        backend = StubStorageBackend()
        ids = [backend.write(u) for u in sample_memory_units]
        assert len(set(ids)) == len(ids)  # all unique

    def test_search(self, sample_memory_units):
        from contextledger.backends.storage.stub import StubStorageBackend
        backend = StubStorageBackend()
        for u in sample_memory_units:
            backend.write(u)
        results = backend.search([0.1] * 128, limit=3)
        assert len(results) <= 3

    def test_traverse(self, sample_memory_unit):
        from contextledger.backends.storage.stub import StubStorageBackend
        backend = StubStorageBackend()
        backend.write(sample_memory_unit)
        results = backend.traverse(sample_memory_unit["id"], depth=1)
        assert isinstance(results, list)

    def test_delete(self, sample_memory_unit):
        from contextledger.backends.storage.stub import StubStorageBackend
        backend = StubStorageBackend()
        uid = backend.write(sample_memory_unit)
        assert backend.delete(uid) is True
        assert backend.read(uid) is None

    def test_list_by_profile(self, sample_memory_units):
        from contextledger.backends.storage.stub import StubStorageBackend
        backend = StubStorageBackend()
        for u in sample_memory_units:
            backend.write(u)
        results = backend.list_by_profile("supervised-db-research")
        assert isinstance(results, list)
