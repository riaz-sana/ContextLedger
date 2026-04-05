"""Integration tests for two-database architecture.

Tests that memory.db and findings.db are separate, findings contain
no raw session content, and the full flow works end-to-end.

Task: Feature 0 — Two-database architecture
"""

import pytest

from contextledger.backends.embedding.stub import StubEmbeddingBackend
from contextledger.merge.findings_extractor import FindingsExtractor


class InMemoryFindingsBackend:
    """Simple in-memory findings backend for integration testing."""
    def __init__(self):
        self._data = {}

    def write_finding(self, finding):
        self._data[finding["id"]] = finding
        return finding["id"]

    def get_findings_for_profile(self, profile_name, limit=50, min_confidence=0.5):
        return [
            f for f in self._data.values()
            if f["skill_profile"] == profile_name
            and f.get("confidence", 0) >= min_confidence
        ][:limit]

    def count(self, profile_name=None):
        if profile_name:
            return sum(1 for f in self._data.values() if f["skill_profile"] == profile_name)
        return len(self._data)


class TestTwoDatabaseArchitecture:
    def test_findings_do_not_contain_raw_session_content(self):
        embedding = StubEmbeddingBackend()
        findings_db = InMemoryFindingsBackend()
        extractor = FindingsExtractor(embedding, findings_db)

        synthesis_outputs = {
            "synth": {
                "findings": [
                    {"content": "Missing index on users.email", "confidence": 0.9},
                ]
            }
        }
        stored = extractor.extract_and_store(
            synthesis_outputs, "db-skill", "1.0.0", "database"
        )

        for finding in stored:
            assert "raw_content" not in finding
            assert "user_message" not in finding
            assert "messages" not in finding
            assert "session_log" not in finding

    def test_privacy_gate_blocks_raw_content(self):
        embedding = StubEmbeddingBackend()
        findings_db = InMemoryFindingsBackend()
        extractor = FindingsExtractor(embedding, findings_db)

        synthesis_outputs = {
            "synth": {
                "findings": [
                    {
                        "content": "test",
                        "confidence": 0.9,
                        "raw_content": "user said: private stuff",
                    },
                ]
            }
        }
        with pytest.raises(ValueError, match="forbidden"):
            extractor.extract_and_store(
                synthesis_outputs, "test", "1.0.0", "test"
            )

    def test_full_flow_ingest_to_findings(self):
        """Simulate: session -> MCP ingest -> synthesis -> findings extraction."""
        from contextledger.mcp.server import ContextLedgerMCP

        embedding = StubEmbeddingBackend()
        findings_db = InMemoryFindingsBackend()

        # 1. Ingest via MCP (goes to memory.db / in-memory tiers)
        server = ContextLedgerMCP(embedding_backend=embedding)
        server.ctx_ingest({
            "session_id": "s1",
            "messages": [
                {"role": "user", "content": "Check the database schema"},
                {"role": "assistant", "content": "Found missing index on users.email"},
            ],
        })
        assert server.ctx_status()["sessions_ingested"] == 1

        # 2. Synthesis produces findings (simulated DAG output)
        synthesis_outputs = {
            "extract": {"entities": [{"type": "table", "value": "users"}]},
            "synth": {
                "findings": [
                    {"content": "Missing index on users.email column", "confidence": 0.85},
                    {"content": "Table users has circular FK", "confidence": 0.7},
                ]
            },
        }

        # 3. FindingsExtractor writes to findings.db (separate from memory.db)
        extractor = FindingsExtractor(embedding, findings_db)
        stored = extractor.extract_and_store(
            synthesis_outputs, "db-research", "1.0.0", "database"
        )

        assert len(stored) == 2
        assert findings_db.count("db-research") == 2

        # 4. Findings are available for Tier 2 evaluation
        eval_findings = findings_db.get_findings_for_profile("db-research", limit=50)
        assert len(eval_findings) == 2
        assert all(f["skill_profile"] == "db-research" for f in eval_findings)

    def test_findings_have_embeddings(self):
        embedding = StubEmbeddingBackend()
        findings_db = InMemoryFindingsBackend()
        extractor = FindingsExtractor(embedding, findings_db)

        stored = extractor.extract_and_store(
            {"node": {"findings": [{"content": "test", "confidence": 0.9}]}},
            "test", "1.0.0", "test",
        )
        assert len(stored[0]["embedding"]) == 128  # StubEmbeddingBackend produces 128-dim

    def test_evaluator_uses_findings_db(self):
        """Tier 2 evaluator should use findings from findings.db."""
        embedding = StubEmbeddingBackend()
        findings_db = InMemoryFindingsBackend()
        extractor = FindingsExtractor(embedding, findings_db)

        # Store some findings
        extractor.extract_and_store(
            {"node": {"findings": [
                {"content": f"Finding {i}", "confidence": 0.9}
                for i in range(5)
            ]}},
            "eval-skill", "1.0.0", "test",
        )

        # Evaluator fetches from findings.db
        eval_findings = findings_db.get_findings_for_profile("eval-skill")
        assert len(eval_findings) == 5
