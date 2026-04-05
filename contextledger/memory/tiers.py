"""Three-tier memory router.

Routes queries to the appropriate tier:
- Immediate: verbatim last N turns
- Synthesis: compressed recent findings
- Archival: full semantic history
"""

import math
from datetime import datetime, timedelta, timezone


class TierRouter:
    """Routes queries to appropriate memory tiers based on intent keywords."""

    def route(self, query: str) -> list[str]:
        """Route query to appropriate tiers based on intent keywords."""
        query_lower = query.lower()
        tiers: list[str] = []

        # Immediate: recent/current conversation indicators
        immediate_keywords = ["just", "discussing", "currently", "right now", "we were", "you said"]
        if any(kw in query_lower for kw in immediate_keywords):
            tiers.append("immediate")

        # Synthesis: recent findings, temporal references
        synthesis_keywords = ["yesterday", "last week", "recently", "find", "found", "findings"]
        if any(kw in query_lower for kw in synthesis_keywords):
            tiers.append("synthesis")

        # Archival: historical, original, full history
        archival_keywords = ["original", "first", "history", "all", "across", "everything", "hypothesis"]
        if any(kw in query_lower for kw in archival_keywords):
            tiers.append("archival")

        # Default: if no specific tier matched, query synthesis + archival
        if not tiers:
            tiers = ["synthesis", "archival"]

        return tiers


class ImmediateTier:
    """Verbatim last N turns of conversation."""

    def __init__(self, max_turns: int = 10) -> None:
        self._max_turns = max_turns
        self._turns: list[dict] = []

    def add_turn(self, turn: dict) -> None:
        """Append turn, evict oldest if over max_turns."""
        self._turns.append(turn)
        if len(self._turns) > self._max_turns:
            self._turns = self._turns[-self._max_turns:]

    def get_turns(self) -> list[dict]:
        """Return all turns in order."""
        return list(self._turns)

    def query(self, text: str) -> list[dict]:
        """Return turns whose content contains any word of the query text (case-insensitive)."""
        text_lower = text.lower()
        words = text_lower.split()
        results = []
        for turn in self._turns:
            content = turn.get("content", "").lower()
            if any(w in content for w in words):
                results.append(turn)
        return results

    def clear(self) -> None:
        """Empty the turns list."""
        self._turns.clear()


class SynthesisTier:
    """Compressed recent findings within a time window."""

    def __init__(self, window_days: int = 7) -> None:
        self._window_days = window_days
        self._findings: list[dict] = []

    def add_finding(self, finding: dict) -> None:
        """Append finding. If no 'timestamp' key, add datetime.now(UTC)."""
        if "timestamp" not in finding:
            finding["timestamp"] = datetime.now(timezone.utc)
        self._findings.append(finding)

    def _is_within_window(self, finding: dict) -> bool:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self._window_days)
        return finding.get("timestamp", datetime.now(timezone.utc)) >= cutoff

    def get_findings(self) -> list[dict]:
        """Return findings within window_days."""
        return [f for f in self._findings if self._is_within_window(f)]

    def query(self, text: str) -> list[dict]:
        """Return non-expired findings whose content contains any query word (case-insensitive)."""
        text_lower = text.lower()
        words = text_lower.split()
        results = []
        for finding in self._findings:
            if not self._is_within_window(finding):
                continue
            content = finding.get("content", "").lower()
            if any(w in content for w in words):
                results.append(finding)
        return results


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors using math module."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class ArchivalTier:
    """Full semantic history with embedding-based search."""

    def __init__(self) -> None:
        self._units: list[dict] = []

    def store(self, unit: dict) -> None:
        """Append unit to archival storage."""
        self._units.append(unit)

    def search(self, query_embedding: list[float], limit: int) -> list[dict]:
        """Return top `limit` units by cosine similarity to query_embedding."""
        scored = []
        for unit in self._units:
            embedding = unit.get("embedding")
            if embedding is not None:
                sim = _cosine_similarity(query_embedding, embedding)
                scored.append((sim, unit))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [unit for _, unit in scored[:limit]]

    def count(self) -> int:
        """Return total number of stored units."""
        return len(self._units)
