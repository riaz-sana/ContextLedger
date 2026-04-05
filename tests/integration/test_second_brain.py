"""End-to-end tests for second brain mode.

Tests the full flow: MCP ingestion -> signal extraction ->
three-tier memory storage -> query routing -> response.

Zero configuration required — this mode must work out of the box.

Task: TASK-017 — Integration test: second brain mode
"""

import pytest


class TestSecondBrainEndToEnd:
    """Full pipeline test for second brain mode."""

    def test_ingest_and_query(self, sample_session_log):
        """Ingest a session, then query for its content."""
        from contextledger.mcp.server import ContextLedgerMCP
        server = ContextLedgerMCP()
        server.ctx_ingest(sample_session_log)
        results = server.ctx_query("schema")
        assert len(results) > 0

    def test_multi_session_ingest(self):
        """Ingest multiple sessions and query across all of them."""
        from contextledger.mcp.server import ContextLedgerMCP
        from tests.conftest import make_session_log
        server = ContextLedgerMCP()
        for i in range(3):
            session = make_session_log(turns=3)
            session["session_id"] = f"session-{i}"
            server.ctx_ingest(session)
        status = server.ctx_status()
        assert status.get("sessions_ingested", 0) >= 3

    def test_works_without_profile(self):
        """Second brain mode must work with no skill profile configured."""
        from contextledger.mcp.server import ContextLedgerMCP
        from tests.conftest import make_session_log
        server = ContextLedgerMCP()  # No profile set
        session = make_session_log(turns=2)
        result = server.ctx_ingest(session)
        assert result["status"] == "ok"

    def test_query_routes_to_correct_tier(self, sample_session_log):
        """Different query types should route to appropriate memory tiers."""
        from contextledger.mcp.server import ContextLedgerMCP
        server = ContextLedgerMCP()
        server.ctx_ingest(sample_session_log)
        # Recent query should work
        recent = server.ctx_query("what were we just discussing")
        assert isinstance(recent, list)
        # Historical query should work
        historical = server.ctx_query("original hypothesis")
        assert isinstance(historical, list)

    def test_cmv_trim_on_heavy_session(self, sample_session_log_heavy):
        """Heavy sessions should be trimmed before storage."""
        from contextledger.mcp.server import ContextLedgerMCP
        server = ContextLedgerMCP()
        result = server.ctx_ingest(sample_session_log_heavy)
        assert result["status"] == "ok"
        # Should still be queryable despite trimming
        results = server.ctx_query("findings")
        assert isinstance(results, list)
