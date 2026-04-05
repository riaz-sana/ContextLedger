"""Tests for SQLite StorageBackend.

Runs the same protocol tests against the real SQLite implementation.

Task: TASK-012 — Implement SQLite StorageBackend
"""

import pytest


class TestSQLiteStorageBackend:
    """SQLite implementation must satisfy the same contract as the stub."""

    def test_write_and_read(self, sample_memory_unit, tmp_db_path):
        from contextledger.backends.storage.sqlite import SQLiteStorageBackend
        backend = SQLiteStorageBackend(db_path=str(tmp_db_path))
        uid = backend.write(sample_memory_unit)
        result = backend.read(uid)
        assert result is not None
        assert result["content"] == sample_memory_unit["content"]

    def test_search_semantic(self, sample_memory_units, tmp_db_path):
        from contextledger.backends.storage.sqlite import SQLiteStorageBackend
        backend = SQLiteStorageBackend(db_path=str(tmp_db_path))
        for u in sample_memory_units:
            backend.write(u)
        results = backend.search([0.1] * 128, limit=3)
        assert len(results) <= 3

    def test_delete_and_verify(self, sample_memory_unit, tmp_db_path):
        from contextledger.backends.storage.sqlite import SQLiteStorageBackend
        backend = SQLiteStorageBackend(db_path=str(tmp_db_path))
        uid = backend.write(sample_memory_unit)
        assert backend.delete(uid) is True
        assert backend.read(uid) is None
        assert backend.delete(uid) is False

    def test_list_by_profile(self, sample_memory_units, tmp_db_path):
        from contextledger.backends.storage.sqlite import SQLiteStorageBackend
        backend = SQLiteStorageBackend(db_path=str(tmp_db_path))
        for u in sample_memory_units:
            backend.write(u)
        results = backend.list_by_profile("supervised-db-research")
        assert len(results) == len(sample_memory_units)

    def test_persistence_across_instances(self, sample_memory_unit, tmp_db_path):
        """Data should persist when creating a new backend instance with same DB."""
        from contextledger.backends.storage.sqlite import SQLiteStorageBackend
        backend1 = SQLiteStorageBackend(db_path=str(tmp_db_path))
        uid = backend1.write(sample_memory_unit)
        backend2 = SQLiteStorageBackend(db_path=str(tmp_db_path))
        result = backend2.read(uid)
        assert result is not None

    def test_traverse_returns_related(self, tmp_db_path):
        """traverse() should return related units by graph relationship."""
        from contextledger.backends.storage.sqlite import SQLiteStorageBackend
        backend = SQLiteStorageBackend(db_path=str(tmp_db_path))
        parent = {"id": "p-1", "content": "parent", "unit_type": "finding",
                  "profile_name": "test", "embedding": [0.1] * 128, "tags": [],
                  "timestamp": None, "parent_id": None, "metadata": {}}
        child = {"id": "c-1", "content": "child", "unit_type": "finding",
                 "profile_name": "test", "embedding": [0.1] * 128, "tags": [],
                 "timestamp": None, "parent_id": "p-1", "metadata": {}}
        backend.write(parent)
        backend.write(child)
        results = backend.traverse("p-1", depth=1)
        assert any(r["id"] == "c-1" for r in results)
