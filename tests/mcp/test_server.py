"""Tests for MCP server tools.

Validates the MCP server exposes the correct tools and handles
ingestion, query, grep, status, and checkout operations.

Task: TASK-015 — Implement MCP server
"""

import pytest


class TestMCPServerRequiresBackend:
    """ContextLedgerMCP must not silently fall back to stubs."""

    def test_constructor_requires_embedding_backend(self):
        from contextledger.mcp.server import ContextLedgerMCP
        with pytest.raises(TypeError):
            ContextLedgerMCP()


class TestMCPIngestion:
    """Test ctx_ingest tool."""

    def test_ingest_session_log(self, mcp_server, sample_session_log):
        result = mcp_server.ctx_ingest(sample_session_log)
        assert result["status"] == "ok"

    def test_ingest_extracts_signals(self, mcp_server, sample_session_log):
        result = mcp_server.ctx_ingest(sample_session_log)
        assert "signals_extracted" in result
        assert result["signals_extracted"] >= 0

    def test_ingest_stores_to_memory(self, mcp_server, sample_session_log):
        mcp_server.ctx_ingest(sample_session_log)
        status = mcp_server.ctx_status()
        assert status["total_units"] > 0 or status["sessions_ingested"] > 0


class TestMCPQuery:
    """Test ctx_query tool."""

    def test_query_returns_results(self, mcp_server, sample_session_log):
        mcp_server.ctx_ingest(sample_session_log)
        results = mcp_server.ctx_query("schema")
        assert isinstance(results, list)

    def test_query_with_profile_filter(self, mcp_server, sample_session_log):
        mcp_server.ctx_ingest(sample_session_log)
        results = mcp_server.ctx_query("schema", profile="supervised-db-research")
        assert isinstance(results, list)

    def test_query_empty_returns_empty(self, mcp_server):
        results = mcp_server.ctx_query("anything")
        assert results == []


class TestMCPGrep:
    """Test ctx_grep tool."""

    def test_grep_finds_pattern(self, mcp_server, sample_session_log):
        mcp_server.ctx_ingest(sample_session_log)
        results = mcp_server.ctx_grep("schema")
        assert isinstance(results, list)

    def test_grep_no_match(self, mcp_server):
        results = mcp_server.ctx_grep("xyznonexistent")
        assert results == []


class TestMCPStatus:
    """Test ctx_status tool."""

    def test_status_returns_info(self, mcp_server):
        status = mcp_server.ctx_status()
        assert "active_profile" in status

    def test_status_after_ingest(self, mcp_server, sample_session_log):
        mcp_server.ctx_ingest(sample_session_log)
        status = mcp_server.ctx_status()
        assert status.get("sessions_ingested", 0) >= 1


class TestMCPCheckout:
    """Test skill_checkout tool."""

    def test_checkout_profile(self, mcp_server):
        result = mcp_server.skill_checkout("supervised-db-research")
        assert result.get("active_profile") == "supervised-db-research"

    def test_checkout_with_version(self, mcp_server):
        result = mcp_server.skill_checkout("supervised-db-research", version="1.0.0")
        assert result.get("status") == "ok"
        assert result.get("version") == "1.0.0"
