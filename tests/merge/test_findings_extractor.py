"""Tests for FindingsExtractor privacy gate.

Task: Feature 0 — Two-database architecture
"""

import pytest

from contextledger.merge.findings_extractor import FindingsExtractor
from contextledger.backends.embedding.stub import StubEmbeddingBackend


class MockFindingsBackend:
    """Minimal in-memory findings store for testing."""
    def __init__(self):
        self.stored = []

    def write_finding(self, finding):
        self.stored.append(finding)
        return finding["id"]


@pytest.fixture
def extractor():
    return FindingsExtractor(
        embedding_backend=StubEmbeddingBackend(),
        findings_backend=MockFindingsBackend(),
    )


class TestFindingsExtractor:
    def test_extracts_findings_from_synthesis_output(self, extractor):
        outputs = {
            "synth_node": {
                "findings": [
                    {"content": "Missing index on users.email", "confidence": 0.9},
                    {"content": "API latency spike at 3pm", "confidence": 0.8},
                ]
            }
        }
        stored = extractor.extract_and_store(
            outputs, "db-research", "1.0.0", "database"
        )
        assert len(stored) == 2
        assert stored[0]["summary"] == "Missing index on users.email"
        assert stored[0]["skill_profile"] == "db-research"
        assert stored[0]["domain"] == "database"

    def test_skips_findings_below_min_confidence(self, extractor):
        outputs = {
            "node": {
                "findings": [
                    {"content": "High confidence", "confidence": 0.9},
                    {"content": "Low confidence", "confidence": 0.2},
                ]
            }
        }
        stored = extractor.extract_and_store(
            outputs, "test", "1.0.0", "test", min_confidence=0.5
        )
        assert len(stored) == 1
        assert stored[0]["summary"] == "High confidence"

    def test_raises_on_forbidden_fields(self, extractor):
        outputs = {
            "node": {
                "findings": [
                    {"content": "test", "confidence": 0.9, "raw_content": "PRIVATE DATA"},
                ]
            }
        }
        with pytest.raises(ValueError, match="forbidden"):
            extractor.extract_and_store(outputs, "test", "1.0.0", "test")

    def test_raises_on_user_message_field(self, extractor):
        outputs = {
            "node": {
                "findings": [
                    {"content": "test", "confidence": 0.9, "user_message": "hi"},
                ]
            }
        }
        with pytest.raises(ValueError, match="forbidden"):
            extractor.extract_and_store(outputs, "test", "1.0.0", "test")

    def test_generates_embedding_for_summary(self, extractor):
        outputs = {
            "node": {"findings": [{"content": "test finding", "confidence": 0.9}]}
        }
        stored = extractor.extract_and_store(outputs, "test", "1.0.0", "test")
        assert len(stored[0]["embedding"]) > 0

    def test_stores_to_findings_backend(self, extractor):
        outputs = {
            "node": {"findings": [{"content": "stored", "confidence": 0.9}]}
        }
        extractor.extract_and_store(outputs, "test", "1.0.0", "test")
        assert len(extractor._findings.stored) == 1

    def test_empty_synthesis_output_returns_empty(self, extractor):
        stored = extractor.extract_and_store({}, "test", "1.0.0", "test")
        assert stored == []

    def test_collects_from_filtered_findings(self, extractor):
        outputs = {
            "filter_node": {
                "filtered_findings": [
                    {"content": "passed filter", "confidence": 0.85},
                ]
            }
        }
        stored = extractor.extract_and_store(outputs, "test", "1.0.0", "test")
        assert len(stored) == 1

    def test_skips_empty_summary(self, extractor):
        outputs = {
            "node": {"findings": [{"content": "", "confidence": 0.9}]}
        }
        stored = extractor.extract_and_store(outputs, "test", "1.0.0", "test")
        assert len(stored) == 0
