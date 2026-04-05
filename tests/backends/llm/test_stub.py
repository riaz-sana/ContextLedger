"""Tests for StubLLMClient.

Task: TASK-027 — Implement LLMClient protocol and stub backend
"""

import json
import pytest

from contextledger.backends.llm.stub import StubLLMClient
from contextledger.core.protocols import LLMClient


class TestStubLLMClient:
    def test_implements_protocol(self):
        client = StubLLMClient()
        assert isinstance(client, LLMClient)

    def test_complete_returns_string(self):
        client = StubLLMClient()
        result = client.complete("any prompt")
        assert isinstance(result, str)

    def test_complete_returns_valid_json(self):
        client = StubLLMClient()
        result = client.complete("extract entities from text")
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_extraction_prompt_returns_entities(self):
        client = StubLLMClient()
        result = json.loads(client.complete("Extract entities from content"))
        assert "entities" in result
        assert len(result["entities"]) > 0

    def test_reasoning_prompt_returns_relationships(self):
        client = StubLLMClient()
        result = json.loads(client.complete("Identify relationships between items"))
        assert "relationships" in result

    def test_synthesis_prompt_returns_findings(self):
        client = StubLLMClient()
        result = json.loads(client.complete("Synthesise findings from data"))
        assert "findings" in result

    def test_evaluation_prompt_returns_scores(self):
        client = StubLLMClient()
        result = json.loads(client.complete("Evaluate precision and recall, who is the winner"))
        assert "winner" in result
        assert "precision_a" in result
        assert "precision_b" in result

    def test_unknown_prompt_returns_generic(self):
        client = StubLLMClient()
        result = json.loads(client.complete("hello world"))
        assert "result" in result

    def test_respects_max_tokens(self):
        """Should accept max_tokens parameter without error."""
        client = StubLLMClient()
        result = client.complete("test", max_tokens=50)
        assert isinstance(result, str)
