"""Stub StorageBackend for testing.

Returns mock data. Implements StorageBackend protocol.
"""

from typing import Any, List, Optional


class StubStorageBackend:
    """In-memory dict-backed storage backend for testing."""

    def __init__(self) -> None:
        self._store: dict[str, dict] = {}

    def write(self, unit: Any) -> str:
        uid = unit["id"]
        self._store[uid] = dict(unit)
        return uid

    def read(self, id: str) -> Optional[dict]:
        return self._store.get(id)

    def search(self, query_embedding: List[float], limit: int) -> List[dict]:
        return list(self._store.values())[:limit]

    def traverse(self, node_id: str, depth: int) -> List[dict]:
        result: List[dict] = []
        current = self._store.get(node_id)
        d = 0
        while current and d < depth:
            result.append(current)
            parent_id = current.get("parent_id")
            current = self._store.get(parent_id) if parent_id else None
            d += 1
        return result

    def delete(self, id: str) -> bool:
        if id in self._store:
            del self._store[id]
            return True
        return False

    def list_by_profile(self, profile_name: str) -> List[dict]:
        return [u for u in self._store.values() if u.get("profile_name") == profile_name]
