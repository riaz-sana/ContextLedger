"""Turso (libSQL) implementation of FindingsBackend."""

import json
import math
import os
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


class TursoFindingsBackend:
    """Turso/libSQL-backed FindingsBackend for edge-distributed storage."""

    def __init__(self, url: Optional[str] = None, token: Optional[str] = None) -> None:
        url = url or os.environ.get("TURSO_DATABASE_URL")
        token = token or os.environ.get("TURSO_AUTH_TOKEN")
        if not url or not token:
            raise ValueError(
                "Turso credentials required. Provide url/token arguments or set "
                "TURSO_DATABASE_URL and TURSO_AUTH_TOKEN environment variables."
            )
        import libsql_client

        self._client = libsql_client.create_client_sync(url=url, auth_token=token)
        self._client.execute(_CREATE_TABLE)

    def write_finding(self, finding: dict) -> str:
        """Write a structured finding. Returns finding ID."""
        finding_id = finding.get("id") or str(uuid.uuid4())
        ts = finding.get("timestamp", datetime.now(timezone.utc))
        if isinstance(ts, datetime):
            ts = ts.isoformat()

        self._client.execute(
            """INSERT OR REPLACE INTO findings
               (id, skill_profile, skill_version, finding_type, summary,
                confidence, domain, timestamp, evaluation_eligible,
                embedding, tags, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
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
            ],
        )
        return finding_id

    def get_findings_for_profile(
        self, profile_name: str, limit: int = 50, min_confidence: float = 0.5
    ) -> List[dict]:
        """Get findings for a skill profile, ordered by recency."""
        result = self._client.execute(
            """SELECT * FROM findings
               WHERE skill_profile = ?
                 AND evaluation_eligible = 1
                 AND confidence >= ?
               ORDER BY timestamp DESC
               LIMIT ?""",
            [profile_name, min_confidence, limit],
        )
        return [self._row_to_dict(row, result.columns) for row in result.rows]

    def search_findings(
        self, query_embedding: List[float], profile_name: Optional[str] = None, limit: int = 10
    ) -> List[dict]:
        """Semantic search using Python-side cosine similarity."""
        if profile_name is not None:
            result = self._client.execute(
                "SELECT * FROM findings WHERE skill_profile = ?", [profile_name]
            )
        else:
            result = self._client.execute("SELECT * FROM findings")

        scored = []
        for row in result.rows:
            row_dict = self._row_to_dict(row, result.columns)
            embedding = row_dict.get("embedding", [])
            if embedding:
                sim = self._cosine_similarity(query_embedding, embedding)
                scored.append((sim, row_dict))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [row_dict for _, row_dict in scored[:limit]]

    def list_domains(self, profile_name: str) -> List[str]:
        """List all unique domains that have findings for this profile."""
        result = self._client.execute(
            """SELECT DISTINCT domain FROM findings
               WHERE skill_profile = ? AND domain != ''
               ORDER BY domain""",
            [profile_name],
        )
        col_idx = result.columns.index("domain") if "domain" in result.columns else 0
        return [row[col_idx] for row in result.rows]

    def count(self, profile_name: Optional[str] = None) -> int:
        """Count total findings, optionally filtered by profile."""
        if profile_name is None:
            result = self._client.execute("SELECT COUNT(*) as cnt FROM findings")
        else:
            result = self._client.execute(
                "SELECT COUNT(*) as cnt FROM findings WHERE skill_profile = ?",
                [profile_name],
            )
        return result.rows[0][0]

    @staticmethod
    def _row_to_dict(row, columns: List[str]) -> dict:
        """Convert a libsql row (tuple) + columns list into a dict."""
        d = dict(zip(columns, row))
        # Deserialize JSON text fields
        for key in ("embedding", "tags", "metadata"):
            if key in d and isinstance(d[key], str):
                d[key] = json.loads(d[key])
        if "evaluation_eligible" in d:
            d["evaluation_eligible"] = bool(d["evaluation_eligible"])
        return d

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
