"""Tests for the LangChain callback handler.

All tests run WITHOUT langchain installed by mocking the base class
and LLM response objects.
"""

from __future__ import annotations

import unittest.mock as mock
from types import SimpleNamespace

import pytest

# Patch langchain import so the handler can be instantiated without langchain
# We need to make the module think langchain IS available by patching the flag
# after import.
from contextledger.integrations import langchain_handler as handler_module
from contextledger.backends.embedding.stub import StubEmbeddingBackend


@pytest.fixture(autouse=True)
def _enable_langchain_flag(monkeypatch):
    """Allow instantiation even when langchain is not installed."""
    monkeypatch.setattr(handler_module, "_LANGCHAIN_AVAILABLE", True)


@pytest.fixture
def handler():
    backend = StubEmbeddingBackend()
    return handler_module.ContextLedgerCallbackHandler(embedding_backend=backend)


def _make_llm_response(text: str):
    """Build a mock LLMResult-like object with .generations."""
    generation = SimpleNamespace(text=text)
    return SimpleNamespace(generations=[[generation]])


# ---- Tests ----

def test_handler_captures_llm_start(handler):
    """on_llm_start should capture the first prompt as a user message."""
    handler.on_llm_start(serialized={}, prompts=["Hello, world!"])

    assert len(handler._current_session) == 1
    msg = handler._current_session[0]
    assert msg["role"] == "user"
    assert msg["content"] == "Hello, world!"


def test_handler_captures_llm_end(handler):
    """on_llm_end should capture the response text as an assistant message."""
    response = _make_llm_response("Here is my answer.")
    handler.on_llm_end(response)

    assert len(handler._current_session) == 1
    msg = handler._current_session[0]
    assert msg["role"] == "assistant"
    assert msg["content"] == "Here is my answer."


def test_handler_ingests_on_chain_end(handler):
    """on_chain_end should ingest the accumulated session into ContextLedger."""
    handler.on_llm_start(serialized={}, prompts=["What is 2+2?"])
    handler.on_llm_end(_make_llm_response("4"))
    handler.on_chain_end(outputs={"result": "4"})

    # The server should have ingested one session
    status = handler.server.ctx_status()
    assert status["sessions_ingested"] == 1
    # The ingested session id should be recorded
    assert len(handler._ingested_session_ids) == 1


def test_handler_clears_session_after_ingest(handler):
    """After on_chain_end, the internal session buffer should be empty."""
    handler.on_llm_start(serialized={}, prompts=["Tell me a joke."])
    handler.on_llm_end(_make_llm_response("Why did the chicken cross the road?"))
    handler.on_chain_end(outputs={})

    assert handler._current_session == []


def test_handler_generates_unique_session_ids(handler):
    """Each chain_end invocation should produce a unique session_id."""
    for i in range(5):
        handler.on_llm_start(serialized={}, prompts=[f"Prompt {i}"])
        handler.on_llm_end(_make_llm_response(f"Response {i}"))
        handler.on_chain_end(outputs={})

    ids = handler._ingested_session_ids
    assert len(ids) == 5
    assert len(set(ids)) == 5, "All session IDs should be unique"
