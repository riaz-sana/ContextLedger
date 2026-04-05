"""Tests for three-tier memory routing.

The router decides which memory tier(s) to query based on
the intent of the incoming query.

Task: TASK-004 — Implement three-tier memory router
"""

import pytest


class TestTierRouter:
    """Test query routing to appropriate memory tiers."""

    def test_recent_query_routes_to_immediate(self):
        """Queries about current conversation should hit the immediate tier."""
        from contextledger.memory.tiers import TierRouter
        router = TierRouter()
        tiers = router.route("What were we just discussing?")
        assert "immediate" in tiers

    def test_temporal_query_routes_to_synthesis(self):
        """Queries about recent findings should hit the synthesis tier."""
        from contextledger.memory.tiers import TierRouter
        router = TierRouter()
        tiers = router.route("What did I find yesterday?")
        assert "synthesis" in tiers

    def test_historical_query_routes_to_archival(self):
        """Queries about old context should hit the archival tier."""
        from contextledger.memory.tiers import TierRouter
        router = TierRouter()
        tiers = router.route("What was my original hypothesis about X?")
        assert "archival" in tiers

    def test_broad_query_routes_to_multiple_tiers(self):
        """Broad queries should hit synthesis + archival."""
        from contextledger.memory.tiers import TierRouter
        router = TierRouter()
        tiers = router.route("Show me all findings related to Y across my work")
        assert len(tiers) >= 2
        assert "synthesis" in tiers or "archival" in tiers

    def test_route_returns_list(self):
        """route() should always return a list of tier names."""
        from contextledger.memory.tiers import TierRouter
        router = TierRouter()
        result = router.route("any query")
        assert isinstance(result, list)
        assert all(t in ("immediate", "synthesis", "archival") for t in result)


class TestImmediateTier:
    """Test the immediate memory tier (verbatim last N turns)."""

    def test_store_and_retrieve_turns(self):
        """Should store verbatim turns and retrieve them in order."""
        from contextledger.memory.tiers import ImmediateTier
        tier = ImmediateTier(max_turns=10)
        tier.add_turn({"role": "user", "content": "Hello"})
        tier.add_turn({"role": "assistant", "content": "Hi there"})
        turns = tier.get_turns()
        assert len(turns) == 2
        assert turns[0]["content"] == "Hello"
        assert turns[1]["content"] == "Hi there"

    def test_respects_max_turns(self):
        """Should evict oldest turns when max_turns is exceeded."""
        from contextledger.memory.tiers import ImmediateTier
        tier = ImmediateTier(max_turns=3)
        for i in range(5):
            tier.add_turn({"role": "user", "content": f"Message {i}"})
        turns = tier.get_turns()
        assert len(turns) == 3
        assert turns[0]["content"] == "Message 2"  # oldest kept

    def test_query_searches_recent(self):
        """query() should search within immediate turns."""
        from contextledger.memory.tiers import ImmediateTier
        tier = ImmediateTier(max_turns=10)
        tier.add_turn({"role": "user", "content": "The schema has 5 tables"})
        tier.add_turn({"role": "assistant", "content": "Interesting finding about tables"})
        results = tier.query("tables")
        assert len(results) > 0

    def test_clear(self):
        """clear() should empty the immediate tier."""
        from contextledger.memory.tiers import ImmediateTier
        tier = ImmediateTier(max_turns=10)
        tier.add_turn({"role": "user", "content": "test"})
        tier.clear()
        assert len(tier.get_turns()) == 0


class TestSynthesisTier:
    """Test the synthesis memory tier (compressed recent findings)."""

    def test_store_finding(self):
        """Should store a compressed finding."""
        from contextledger.memory.tiers import SynthesisTier
        tier = SynthesisTier(window_days=7)
        tier.add_finding({
            "content": "Database has circular foreign key references",
            "source_session": "session-001",
            "confidence": 0.85,
        })
        findings = tier.get_findings()
        assert len(findings) == 1

    def test_query_findings(self):
        """query() should return relevant findings by semantic match."""
        from contextledger.memory.tiers import SynthesisTier
        tier = SynthesisTier(window_days=7)
        tier.add_finding({"content": "Table users has no index on email column"})
        tier.add_finding({"content": "API response times spike at 3pm daily"})
        results = tier.query("database index")
        assert len(results) >= 1

    def test_window_expiry(self):
        """Findings older than window_days should not appear in query results."""
        from contextledger.memory.tiers import SynthesisTier
        from datetime import datetime, timezone, timedelta
        tier = SynthesisTier(window_days=7)
        old_finding = {
            "content": "Old finding",
            "timestamp": datetime.now(timezone.utc) - timedelta(days=10),
        }
        new_finding = {
            "content": "Recent finding",
            "timestamp": datetime.now(timezone.utc),
        }
        tier.add_finding(old_finding)
        tier.add_finding(new_finding)
        findings = tier.get_findings()
        contents = [f["content"] for f in findings]
        assert "Recent finding" in contents
        # Old finding should be expired
        assert "Old finding" not in contents


class TestArchivalTier:
    """Test the archival memory tier (full semantic history)."""

    def test_store_and_search(self):
        """Should store units and retrieve by semantic search."""
        from contextledger.memory.tiers import ArchivalTier
        tier = ArchivalTier()
        tier.store({"id": "a-001", "content": "Schema anomaly in users table", "embedding": [0.1] * 128})
        tier.store({"id": "a-002", "content": "API latency regression detected", "embedding": [0.9] * 128})
        results = tier.search(query_embedding=[0.1] * 128, limit=1)
        assert len(results) == 1

    def test_search_respects_limit(self):
        """search() should not return more than limit results."""
        from contextledger.memory.tiers import ArchivalTier
        tier = ArchivalTier()
        for i in range(20):
            tier.store({"id": f"a-{i}", "content": f"Finding {i}", "embedding": [0.1 * i] * 128})
        results = tier.search(query_embedding=[0.5] * 128, limit=5)
        assert len(results) <= 5

    def test_full_history_available(self):
        """Archival tier should never expire — full history is always searchable."""
        from contextledger.memory.tiers import ArchivalTier
        tier = ArchivalTier()
        for i in range(100):
            tier.store({"id": f"a-{i}", "content": f"Finding {i}", "embedding": [0.01 * i] * 128})
        assert tier.count() == 100
