"""Postgres + pgvector StorageBackend."""

import json
import math
import os
from typing import List, Optional


class PostgresStorageBackend:
    """PostgreSQL-backed implementation of the StorageBackend protocol.

    Requires psycopg2: pip install psycopg2-binary
    Uses DATABASE_URL environment variable for connection string.
    """

    def __init__(self, db_url: str = None):
        self._db_url = db_url or os.environ.get("DATABASE_URL")
        if not self._db_url:
            raise ValueError("DATABASE_URL not set")
        try:
            import psycopg2

            self._psycopg2 = psycopg2
            self._conn = psycopg2.connect(self._db_url)
            self._create_tables()
        except ImportError:
            raise RuntimeError(
                "psycopg2 not installed. Run: pip install psycopg2-binary"
            )

    def _create_tables(self):
        with self._conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS memory_units (
                    id TEXT PRIMARY KEY,
                    content TEXT,
                    unit_type TEXT,
                    profile_name TEXT,
                    embedding JSONB,
                    tags JSONB,
                    timestamp TEXT,
                    parent_id TEXT,
                    metadata JSONB
                )
            """)
            self._conn.commit()

    def write(self, unit) -> str:
        """Write a memory unit dict, return its ID."""
        uid = unit["id"]
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO memory_units (id, content, unit_type, profile_name,
                    embedding, tags, timestamp, parent_id, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    content = EXCLUDED.content,
                    unit_type = EXCLUDED.unit_type,
                    profile_name = EXCLUDED.profile_name,
                    embedding = EXCLUDED.embedding,
                    tags = EXCLUDED.tags,
                    timestamp = EXCLUDED.timestamp,
                    parent_id = EXCLUDED.parent_id,
                    metadata = EXCLUDED.metadata
                """,
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
        """Read a memory unit by ID. Returns dict or None if not found."""
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM memory_units WHERE id = %s", (id,))
            row = cur.fetchone()
            if row is None:
                return None
            return self._row_to_dict(row, cur.description)

    def search(self, query_embedding: List[float], limit: int) -> List[dict]:
        """Semantic search over stored units by embedding similarity."""
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM memory_units")
            rows = cur.fetchall()
            desc = cur.description
        scored = []
        for row in rows:
            d = self._row_to_dict(row, desc)
            emb = d.get("embedding", [])
            sim = self._cosine_similarity(query_embedding, emb) if emb else 0.0
            scored.append((sim, d))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [d for _, d in scored[:limit]]

    def traverse(self, node_id: str, depth: int) -> List[dict]:
        """Graph traversal from a node, returning units up to given depth."""
        results = []
        current_ids = [node_id]
        for _ in range(depth):
            if not current_ids:
                break
            placeholders = ",".join(["%s"] * len(current_ids))
            with self._conn.cursor() as cur:
                cur.execute(
                    f"SELECT * FROM memory_units WHERE parent_id IN ({placeholders})",
                    current_ids,
                )
                rows = cur.fetchall()
                desc = cur.description
            next_ids = []
            for row in rows:
                d = self._row_to_dict(row, desc)
                results.append(d)
                next_ids.append(d["id"])
            current_ids = next_ids
        return results

    def delete(self, id: str) -> bool:
        """Delete a memory unit by ID. Returns True if deleted, False otherwise."""
        with self._conn.cursor() as cur:
            cur.execute("DELETE FROM memory_units WHERE id = %s", (id,))
            deleted = cur.rowcount > 0
            self._conn.commit()
        return deleted

    def list_by_profile(self, profile_name: str) -> List[dict]:
        """List all memory units belonging to a given profile."""
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM memory_units WHERE profile_name = %s",
                (profile_name,),
            )
            rows = cur.fetchall()
            desc = cur.description
        return [self._row_to_dict(row, desc) for row in rows]

    @staticmethod
    def _row_to_dict(row, description) -> dict:
        """Convert a psycopg2 row tuple + cursor.description to a dict."""
        columns = [col.name for col in description]
        d = dict(zip(columns, row))
        # JSONB columns are auto-parsed by psycopg2, but handle string fallback
        for key in ("embedding", "tags", "metadata"):
            val = d.get(key)
            if isinstance(val, str):
                d[key] = json.loads(val)
            elif val is None:
                d[key] = [] if key != "metadata" else {}
        return d

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
