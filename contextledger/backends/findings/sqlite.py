"""SQLite implementation of FindingsBackend."""

import json
import math
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import List, Optional


_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS findings (
    id TEXT PRIMARY KEY,
    skill_profile TEXT NOT NULL,
    skill_version TEXT NOT NULL DEFAULT '',
    finding_type TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 0.5,
    domain TEXT NOT NULL DEFAULT '',
    timestamp TEXT NOT NULL,
    evaluation_eligible INTEGER NOT NULL DEFAULT 1,
    embedding TEXT NOT NULL DEFAULT '[]',
    tags TEXT NOT NULL DEFAULT '[]',
    metadata TEXT NOT NULL DEFAULT '{}'
)
"""


class SQLiteFindingsBackend:
    """SQLite-backed FindingsBackend for local persistent storage."""

    def __init__(self, db_path: str = "findings.db") -> None:
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(_CREATE_TABLE)
        self._conn.commit()

    def write_finding(self, finding: dict) -> str:
        """Write a structured finding. Returns finding ID."""
        finding_id = finding.get("id") or str(uuid.uuid4())
        ts = finding.get("timestamp", datetime.now(timezone.utc))
        if isinstance(ts, datetime):
            ts = ts.isoformat()

        self._conn.execute(
            """INSERT OR REPLACE INTO findings
               (id, skill_profile, skill_version, finding_type, summary,
                confidence, domain, timestamp, evaluation_eligible,
                embedding, tags, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                finding_id,
                finding["skill_profile"],
                finding.get("skill_version", ""),
                finding.get("finding_type", ""),
                finding.get("summary", ""),
                finding.get("confidence", 0.5),
                finding.get("domain", ""),
                ts,
                1 if finding.get("evaluation_eligible", True) else 0,
                json.dumps(finding.get("embedding", [])),
                json.dumps(finding.get("tags", [])),
                json.dumps(finding.get("metadata", {})),
            ),
        )
        self._conn.commit()
        return finding_id

    def get_findings_for_profile(
        self, profile_name: str, limit: int = 50, min_confidence: float = 0.5
    ) -> List[dict]:
        """Get findings for a skill profile, ordered by recency."""
        cursor = self._conn.execute(
            """SELECT * FROM findings
               WHERE skill_profile = ?
                 AND evaluation_eligible = 1
                 AND confidence >= ?
               ORDER BY timestamp DESC
               LIMIT ?""",
            (profile_name, min_confidence, limit),
        )
        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def search_findings(
        self, query_embedding: List[float], profile_name: Optional[str] = None, limit: int = 10
    ) -> List[dict]:
        """Semantic search across findings using Python-side cosine similarity."""
        if profile_name is not None:
            cursor = self._conn.execute(
                "SELECT * FROM findings WHERE skill_profile = ?", (profile_name,)
            )
        else:
            cursor = self._conn.execute("SELECT * FROM findings")

        rows = cursor.fetchall()
        scored = []
        for row in rows:
            embedding = json.loads(row["embedding"])
            if embedding:
                sim = self._cosine_similarity(query_embedding, embedding)
                scored.append((sim, row))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [self._row_to_dict(row) for _, row in scored[:limit]]

    def list_domains(self, profile_name: str) -> List[str]:
        """List all unique domains that have findings for this profile."""
        cursor = self._conn.execute(
            """SELECT DISTINCT domain FROM findings
               WHERE skill_profile = ? AND domain != ''
               ORDER BY domain""",
            (profile_name,),
        )
        return [row["domain"] for row in cursor.fetchall()]

    def count(self, profile_name: Optional[str] = None) -> int:
        """Count total findings, optionally filtered by profile."""
        if profile_name is None:
            cursor = self._conn.execute("SELECT COUNT(*) as cnt FROM findings")
        else:
            cursor = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM findings WHERE skill_profile = ?",
                (profile_name,),
            )
        return cursor.fetchone()["cnt"]

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        if len(a) != len(b) or not a:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(x * x for x in b))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "skill_profile": row["skill_profile"],
            "skill_version": row["skill_version"],
            "finding_type": row["finding_type"],
            "summary": row["summary"],
            "confidence": row["confidence"],
            "domain": row["domain"],
            "timestamp": row["timestamp"],
            "evaluation_eligible": bool(row["evaluation_eligible"]),
            "embedding": json.loads(row["embedding"]),
            "tags": json.loads(row["tags"]),
            "metadata": json.loads(row["metadata"]),
        }
