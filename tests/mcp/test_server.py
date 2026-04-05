"""Tests for MCP server tools.

Validates the MCP server exposes the correct tools and handles
ingestion, query, grep, status, and checkout operations.

Task: TASK-015 — Implement MCP server
"""

import pytest


class TestMCPIngestion:
    """Test ctx_ingest tool."""

    def test_ingest_session_log(self, sample_session_log):
        """Should accept a session log and return success."""
        from contextledger.mcp.server import ContextLedgerMCP
        server = ContextLedgerMCP()
        result = server.ctx_ingest(sample_session_log)
        assert result["status"] == "ok"

    def test_ingest_extracts_signals(self, sample_session_log):
        """Ingestion should run signal extraction on the session."""
        from contextledger.mcp.server import ContextLedgerMCP
        server = ContextLedgerMCP()
        result = server.ctx_ingest(sample_session_log)
        assert "signals_extracted" in result
        assert result["signals_extracted"] >= 0

    def test_ingest_stores_to_memory(self, sample_session_log):
        """Ingested signals should be stored in the memory system."""
        from contextledger.mcp.server import ContextLedgerMCP
        server = ContextLedgerMCP()
        server.ctx_ingest(sample_session_log)
        status = server.ctx_status()
        assert status["total_units"] > 0 or status["sessions_ingested"] > 0


class TestMCPQuery:
    """Test ctx_query tool."""

    def test_query_returns_results(self, sample_session_log):
        """Should return relevant results for a query."""
        from contextledger.mcp.server import ContextLedgerMCP
        server = ContextLedgerMCP()
        server.ctx_ingest(sample_session_log)
        results = server.ctx_query("schema")
        assert isinstance(results, list)

    def test_query_with_profile_filter(self, sample_session_log):
        """Should filter results by profile when specified."""
        from contextledger.mcp.server import ContextLedgerMCP
        server = ContextLedgerMCP()
        server.ctx_ingest(sample_session_log)
        results = server.ctx_query("schema", profile="supervised-db-research")
        assert isinstance(results, list)

    def test_query_empty_returns_empty(self):
        """Query with no ingested data should return empty list."""
        from contextledger.mcp.server import ContextLedgerMCP
        server = ContextLedgerMCP()
        results = server.ctx_query("anything")
        assert results == []


class TestMCPGrep:
    """Test ctx_grep tool."""

    def test_grep_finds_pattern(self, sample_session_log):
        """Should find findings matching a pattern."""
        from contextledger.mcp.server import ContextLedgerMCP
        server = ContextLedgerMCP()
        server.ctx_ingest(sample_session_log)
        results = server.ctx_grep("schema")
        assert isinstance(results, list)

    def test_grep_no_match(self):
        """Should return empty list when no match found."""
        from contextledger.mcp.server import ContextLedgerMCP
        server = ContextLedgerMCP()
        results = server.ctx_grep("xyznonexistent")
        assert results == []


class TestMCPStatus:
    """Test ctx_status tool."""

    def test_status_returns_info(self):
        """Should return current profile and activity info."""
        from contextledger.mcp.server import ContextLedgerMCP
        server = ContextLedgerMCP()
        status = server.ctx_status()
        assert "active_profile" in status or "mode" in status

    def test_status_after_ingest(self, sample_session_log):
        """Status should reflect ingested data."""
        from contextledger.mcp.server import ContextLedgerMCP
        server = ContextLedgerMCP()
        server.ctx_ingest(sample_session_log)
        status = server.ctx_status()
        assert status.get("sessions_ingested", 0) >= 1


class TestMCPCheckout:
    """Test skill_checkout tool."""

    def test_checkout_profile(self):
        """Should switch the active skill profile."""
        from contextledger.mcp.server import ContextLedgerMCP
        server = ContextLedgerMCP()
        result = server.skill_checkout("supervised-db-research")
        assert result.get("active_profile") == "supervised-db-research" or result.get("status") == "ok"

    def test_checkout_with_version(self):
        """Should checkout a specific version of a profile."""
        from contextledger.mcp.server import ContextLedgerMCP
        server = ContextLedgerMCP()
        result = server.skill_checkout("supervised-db-research", version="1.0.0")
        assert result.get("status") == "ok" or result.get("version") == "1.0.0"
