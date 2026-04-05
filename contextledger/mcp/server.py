"""MCP server for ContextLedger.

Exposes tools:
- ctx_ingest(session_log)
- ctx_query(query, profile)
- ctx_grep(pattern)
- ctx_status()
- skill_checkout(name, version)
"""

from contextledger.core.protocols import EmbeddingBackend, StorageBackend
from contextledger.memory.cmv import CMVEngine
from contextledger.memory.tiers import TierRouter, ImmediateTier, SynthesisTier, ArchivalTier


class ContextLedgerMCP:
    """MCP server implementing second brain mode.

    Requires an EmbeddingBackend and optional StorageBackend.
    No silent fallback to stubs — if a backend isn't provided, it errors.
    """

    def __init__(
        self,
        embedding_backend: EmbeddingBackend,
        storage_backend: StorageBackend | None = None,
        findings_backend=None,
    ) -> None:
        self._embedding = embedding_backend
        self._storage = storage_backend
        self._findings_backend = findings_backend
        self._cmv = CMVEngine()
        self._router = TierRouter()
        self._immediate = ImmediateTier(max_turns=10)
        self._synthesis = SynthesisTier(window_days=7)
        self._archival = ArchivalTier()
        self._active_profile: str | None = None
        self._active_version: str | None = None
        self._sessions_ingested: int = 0
        self._findings: list[dict] = []

    def ctx_ingest(self, session_log: dict) -> dict:
        """Ingest a session log. Extract signals, store to memory."""
        snapshot_id = self._cmv.snapshot(session_log)
        self._cmv.trim(snapshot_id)

        signals: list[dict] = []
        for msg in session_log.get("messages", []):
            content = msg.get("content", "")
            self._immediate.add_turn(msg)

            if msg.get("role") == "assistant":
                finding = {
                    "content": content,
                    "source_session": session_log.get("session_id", "unknown"),
                }
                self._synthesis.add_finding(finding)
                emb = self._embedding.encode(content)
                unit = {
                    "id": f"unit-{len(self._findings)}",
                    "content": content,
                    "embedding": emb,
                }
                self._archival.store(unit)
                if self._storage:
                    self._storage.write(unit)
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

    def ctx_project_query(
        self,
        query: str,
        mode: str = "routed",
        current_dir: str | None = None,
        file_path: str | None = None,
        profile: str | None = None,
        limit: int = 10,
    ) -> dict:
        """Query context in a multi-skill project."""
        from contextledger.project.manager import ProjectManager
        mgr = ProjectManager()
        try:
            mgr.load()
        except FileNotFoundError:
            return {"status": "error", "message": "No project manifest found"}

        if mode == "all":
            result = mgr.query_all(query, limit=limit)
        else:
            result = mgr.query_routed(
                query, current_dir=current_dir,
                file_path=file_path, explicit_profile=profile, limit=limit,
            )

        return {
            "status": "ok",
            "active_skill": result.active_skill,
            "routing_reason": result.routing_reason,
            "results": result.fused_results,
            "results_by_skill": {
                k: len(v) for k, v in result.results_by_skill.items()
            },
        }

    def ctx_project_status(self) -> dict:
        """Returns project manifest info."""
        from contextledger.project.manager import ProjectManager
        mgr = ProjectManager()
        try:
            manifest = mgr.load()
        except FileNotFoundError:
            return {"status": "error", "message": "No project manifest found"}

        return {
            "status": "ok",
            "name": manifest.name,
            "version": manifest.version,
            "skills": manifest.skills,
            "default_skill": manifest.default_skill,
            "fusion_enabled": manifest.fusion_enabled,
        }
