"""Supabase implementation of FindingsBackend."""

import json
import math
import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional


TABLE_NAME = "contextledger_findings"


class SupabaseFindingsBackend:
    """Supabase-backed FindingsBackend for cloud persistent storage."""

    def __init__(self, url: Optional[str] = None, key: Optional[str] = None) -> None:
        url = url or os.environ.get("SUPABASE_URL")
        key = key or os.environ.get("SUPABASE_ANON_KEY")
        if not url or not key:
            raise ValueError(
                "Supabase credentials required. Provide url/key arguments or set "
                "SUPABASE_URL and SUPABASE_ANON_KEY environment variables."
            )
        from supabase import create_client

        self._client = create_client(url, key)

    def write_finding(self, finding: dict) -> str:
        """Write a structured finding via upsert. Returns finding ID."""
        finding_id = finding.get("id") or str(uuid.uuid4())
        ts = finding.get("timestamp", datetime.now(timezone.utc))
        if isinstance(ts, datetime):
            ts = ts.isoformat()

        row = {
            "id": finding_id,
            "skill_profile": finding["skill_profile"],
            "skill_version": finding.get("skill_version", ""),
            "finding_type": finding.get("finding_type", ""),
            "summary": finding.get("summary", ""),
            "confidence": finding.get("confidence", 0.5),
            "domain": finding.get("domain", ""),
            "timestamp": ts,
            "evaluation_eligible": finding.get("evaluation_eligible", True),
            "embedding": finding.get("embedding", []),
            "tags": finding.get("tags", []),
            "metadata": finding.get("metadata", {}),
        }
        self._client.table(TABLE_NAME).upsert(row).execute()
        return finding_id

    def get_findings_for_profile(
        self, profile_name: str, limit: int = 50, min_confidence: float = 0.5
    ) -> List[dict]:
        """Get findings for a skill profile, ordered by recency."""
        response = (
            self._client.table(TABLE_NAME)
            .select("*")
            .eq("skill_profile", profile_name)
            .eq("evaluation_eligible", True)
            .gte("confidence", min_confidence)
            .order("timestamp", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data

    def search_findings(
        self, query_embedding: List[float], profile_name: Optional[str] = None, limit: int = 10
    ) -> List[dict]:
        """Semantic search. Tries server-side RPC first, falls back to Python-side cosine."""
        try:
            params = {
                "query_embedding": query_embedding,
                "match_count": limit,
            }
            if profile_name is not None:
                params["filter_profile"] = profile_name
            response = self._client.rpc("match_findings", params).execute()
            return response.data
        except Exception:
            return self._python_side_search(query_embedding, profile_name, limit)

    def _python_side_search(
        self, query_embedding: List[float], profile_name: Optional[str], limit: int
    ) -> List[dict]:
        """Fallback: fetch all rows and compute cosine similarity in Python."""
        query = self._client.table(TABLE_NAME).select("*")
        if profile_name is not None:
            query = query.eq("skill_profile", profile_name)
        response = query.execute()

        scored = []
        for row in response.data:
            embedding = row.get("embedding", [])
            if embedding:
                sim = self._cosine_similarity(query_embedding, embedding)
                scored.append((sim, row))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [row for _, row in scored[:limit]]

    def list_domains(self, profile_name: str) -> List[str]:
        """List all unique domains that have findings for this profile."""
        response = (
            self._client.table(TABLE_NAME)
            .select("domain")
            .eq("skill_profile", profile_name)
            .neq("domain", "")
            .execute()
        )
        domains = sorted({row["domain"] for row in response.data})
        return domains

    def count(self, profile_name: Optional[str] = None) -> int:
        """Count total findings, optionally filtered by profile."""
        query = self._client.table(TABLE_NAME).select("id", count="exact")
        if profile_name is not None:
            query = query.eq("skill_profile", profile_name)
        response = query.execute()
        return response.count

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
