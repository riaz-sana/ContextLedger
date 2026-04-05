"""MCP server for ContextLedger.

Exposes tools:
- ctx_ingest(session_log)
- ctx_query(query, profile)
- ctx_grep(pattern)
- ctx_status()
- skill_checkout(name, version)
"""

from contextledger.memory.cmv import CMVEngine
from contextledger.memory.tiers import TierRouter, ImmediateTier, SynthesisTier, ArchivalTier
from contextledger.backends.embedding.stub import StubEmbeddingBackend


class ContextLedgerMCP:
    """MCP server implementing second brain mode (no profile needed).

    Wires together CMV, three-tier memory, and embedding backend to provide
    a zero-config context layer for AI sessions.
    """

    def __init__(self) -> None:
        self._cmv = CMVEngine()
        self._router = TierRouter()
        self._immediate = ImmediateTier(max_turns=10)
        self._synthesis = SynthesisTier(window_days=7)
        self._archival = ArchivalTier()
        self._embedding = StubEmbeddingBackend()
        self._active_profile: str | None = None
        self._sessions_ingested: int = 0
        self._findings: list[dict] = []

    def ctx_ingest(self, session_log: dict) -> dict:
        """Ingest a session log. Extract signals, store to memory."""
        # Snapshot the session in CMV
        snapshot_id = self._cmv.snapshot(session_log)

        # Extract signals from messages
        signals: list[dict] = []
        for msg in session_log.get("messages", []):
            content = msg.get("content", "")
            # Add every message to immediate tier
            self._immediate.add_turn(msg)

            # Extract findings from assistant messages
            if msg.get("role") == "assistant":
                finding = {
                    "content": content,
                    "source_session": session_log.get("session_id", "unknown"),
                }
                self._synthesis.add_finding(finding)
                # Store in archival with embedding
                emb = self._embedding.encode(content)
                unit = {
                    "id": f"unit-{len(self._findings)}",
                    "content": content,
                    "embedding": emb,
                }
                self._archival.store(unit)
                self._findings.append(finding)
                signals.append(finding)

        self._sessions_ingested += 1
        return {"status": "ok", "signals_extracted": len(signals)}

    def ctx_query(self, query: str, profile: str | None = None) -> list:
        """Query across memory tiers."""
        tiers = self._router.route(query)
        results: list = []

        if "immediate" in tiers:
            results.extend(self._immediate.query(query))
        if "synthesis" in tiers:
            results.extend(self._synthesis.query(query))
        if "archival" in tiers:
            emb = self._embedding.encode(query)
            results.extend(self._archival.search(emb, limit=10))

        return results

    def ctx_grep(self, pattern: str) -> list:
        """Search findings by pattern (case-insensitive substring match)."""
        return [
            f for f in self._findings
            if pattern.lower() in f.get("content", "").lower()
        ]

    def ctx_status(self) -> dict:
        """Return current status."""
        return {
            "active_profile": self._active_profile,
            "sessions_ingested": self._sessions_ingested,
            "total_units": self._archival.count(),
            "immediate_turns": len(self._immediate.get_turns()),
        }

    def skill_checkout(self, name: str, version: str | None = None) -> dict:
        """Switch active skill profile."""
        self._active_profile = name
        result = {"status": "ok", "active_profile": name}
        if version:
            result["version"] = version
        return result
