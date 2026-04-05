"""In-memory stub implementation of FindingsBackend for testing."""

import math
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from contextledger.core.types import Finding


class StubFindingsBackend:
    """In-memory FindingsBackend for unit tests and development."""

    def __init__(self) -> None:
        self._findings: Dict[str, Finding] = {}

    def write_finding(self, finding: dict) -> str:
        """Write a structured finding. Returns finding ID."""
        finding_id = finding.get("id") or str(uuid.uuid4())
        f = Finding(
            id=finding_id,
            skill_profile=finding["skill_profile"],
            skill_version=finding.get("skill_version", ""),
            finding_type=finding.get("finding_type", ""),
            summary=finding.get("summary", ""),
            confidence=finding.get("confidence", 0.5),
            domain=finding.get("domain", ""),
            timestamp=finding.get("timestamp", datetime.now(timezone.utc)),
            evaluation_eligible=finding.get("evaluation_eligible", True),
            embedding=finding.get("embedding", []),
            tags=finding.get("tags", []),
            metadata=finding.get("metadata", {}),
        )
        self._findings[finding_id] = f
        return finding_id

    def get_findings_for_profile(
        self, profile_name: str, limit: int = 50, min_confidence: float = 0.5
    ) -> List[dict]:
        """Get findings for a skill profile, ordered by recency."""
        results = [
            f
            for f in self._findings.values()
            if f.skill_profile == profile_name
            and f.evaluation_eligible
            and f.confidence >= min_confidence
        ]
        results.sort(key=lambda f: f.timestamp, reverse=True)
        return [self._finding_to_dict(f) for f in results[:limit]]

    def search_findings(
        self, query_embedding: List[float], profile_name: Optional[str] = None, limit: int = 10
    ) -> List[dict]:
        """Semantic search across findings using cosine similarity."""
        candidates = list(self._findings.values())
        if profile_name is not None:
            candidates = [f for f in candidates if f.skill_profile == profile_name]

        scored = []
        for f in candidates:
            if f.embedding:
                sim = self._cosine_similarity(query_embedding, f.embedding)
                scored.append((sim, f))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [self._finding_to_dict(f) for _, f in scored[:limit]]

    def list_domains(self, profile_name: str) -> List[str]:
        """List all unique domains that have findings for this profile."""
        domains = set()
        for f in self._findings.values():
            if f.skill_profile == profile_name and f.domain:
                domains.add(f.domain)
        return sorted(domains)

    def count(self, profile_name: Optional[str] = None) -> int:
        """Count total findings, optionally filtered by profile."""
        if profile_name is None:
            return len(self._findings)
        return sum(1 for f in self._findings.values() if f.skill_profile == profile_name)

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
    def _finding_to_dict(f: Finding) -> dict:
        return {
            "id": f.id,
            "skill_profile": f.skill_profile,
            "skill_version": f.skill_version,
            "finding_type": f.finding_type,
            "summary": f.summary,
            "confidence": f.confidence,
            "domain": f.domain,
            "timestamp": f.timestamp,
            "evaluation_eligible": f.evaluation_eligible,
            "embedding": f.embedding,
            "tags": f.tags,
            "metadata": f.metadata,
        }
