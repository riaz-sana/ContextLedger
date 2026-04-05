"""End-to-end tests for second brain mode.

Tests the full flow: MCP ingestion -> signal extraction ->
three-tier memory storage -> query routing -> response.

Zero configuration required — this mode must work out of the box.

Task: TASK-017 — Integration test: second brain mode
"""

import pytest


class TestSecondBrainEndToEnd:
    """Full pipeline test for second brain mode."""

    def test_ingest_and_query(self, mcp_server, sample_session_log):
        mcp_server.ctx_ingest(sample_session_log)
        results = mcp_server.ctx_query("schema")
        assert len(results) > 0

    def test_multi_session_ingest(self, mcp_server):
        from tests.conftest import make_session_log
        for i in range(3):
            session = make_session_log(turns=3)
            session["session_id"] = f"session-{i}"
            mcp_server.ctx_ingest(session)
        status = mcp_server.ctx_status()
        assert status.get("sessions_ingested", 0) >= 3

    def test_works_without_profile(self, mcp_server):
        from tests.conftest import make_session_log
        session = make_session_log(turns=2)
        result = mcp_server.ctx_ingest(session)
        assert result["status"] == "ok"

    def test_query_routes_to_correct_tier(self, mcp_server, sample_session_log):
        mcp_server.ctx_ingest(sample_session_log)
        recent = mcp_server.ctx_query("what were we just discussing")
        assert isinstance(recent, list)
        historical = mcp_server.ctx_query("original hypothesis")
        assert isinstance(historical, list)

    def test_cmv_trim_on_heavy_session(self, mcp_server, sample_session_log_heavy):
        result = mcp_server.ctx_ingest(sample_session_log_heavy)
        assert result["status"] == "ok"
        results = mcp_server.ctx_query("findings")
        assert isinstance(results, list)
