"""SQLite StorageBackend implementation.

Default storage backend with semantic index support.
"""

import json
import math
import sqlite3
from typing import List, Optional


class SQLiteStorageBackend:
    """SQLite-backed implementation of the StorageBackend protocol."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS memory_units (
                id TEXT PRIMARY KEY,
                content TEXT,
                unit_type TEXT,
                profile_name TEXT,
                embedding TEXT,
                tags TEXT,
                timestamp TEXT,
                parent_id TEXT,
                metadata TEXT
            )
        """)
        self._conn.commit()

    def write(self, unit) -> str:
        uid = unit["id"]
        self._conn.execute(
            "INSERT OR REPLACE INTO memory_units VALUES (?,?,?,?,?,?,?,?,?)",
            (
                uid,
                unit.get("content"),
                unit.get("unit_type"),
                unit.get("profile_name"),
                json.dumps(unit.get("embedding", [])),
                json.dumps(unit.get("tags", [])),
                str(unit.get("timestamp", "")),
                unit.get("parent_id"),
                json.dumps(unit.get("metadata", {})),
            ),
        )
        self._conn.commit()
        return uid

    def read(self, id: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM memory_units WHERE id=?", (id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def search(self, query_embedding: List[float], limit: int) -> List[dict]:
        rows = self._conn.execute("SELECT * FROM memory_units").fetchall()
        scored = []
        for row in rows:
            d = self._row_to_dict(row)
            emb = d.get("embedding", [])
            sim = self._cosine_similarity(query_embedding, emb) if emb else 0.0
            scored.append((sim, d))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [d for _, d in scored[:limit]]

    def traverse(self, node_id: str, depth: int) -> List[dict]:
        results = []
        current_ids = [node_id]
        for _ in range(depth):
            if not current_ids:
                break
            placeholders = ",".join("?" * len(current_ids))
            rows = self._conn.execute(
                f"SELECT * FROM memory_units WHERE parent_id IN ({placeholders})",
                current_ids,
            ).fetchall()
            next_ids = []
            for row in rows:
                d = self._row_to_dict(row)
                results.append(d)
                next_ids.append(d["id"])
            current_ids = next_ids
        return results

    def delete(self, id: str) -> bool:
        cursor = self._conn.execute(
            "DELETE FROM memory_units WHERE id=?", (id,)
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def list_by_profile(self, profile_name: str) -> List[dict]:
        rows = self._conn.execute(
            "SELECT * FROM memory_units WHERE profile_name=?", (profile_name,)
        ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def _row_to_dict(self, row) -> dict:
        return {
            "id": row["id"],
            "content": row["content"],
            "unit_type": row["unit_type"],
            "profile_name": row["profile_name"],
            "embedding": json.loads(row["embedding"]) if row["embedding"] else [],
            "tags": json.loads(row["tags"]) if row["tags"] else [],
            "timestamp": row["timestamp"],
            "parent_id": row["parent_id"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
        }

    @staticmethod
    def _cosine_similarity(a, b):
        if len(a) != len(b) or not a:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
