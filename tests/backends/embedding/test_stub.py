"""Tests for stub EmbeddingBackend.

Task: TASK-002 — Define Protocol classes and stub backends
"""

import pytest


class TestStubEmbeddingBackend:
    def test_encode(self):
        from contextledger.backends.embedding.stub import StubEmbeddingBackend
        backend = StubEmbeddingBackend()
        result = backend.encode("test")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_encode_batch(self):
        from contextledger.backends.embedding.stub import StubEmbeddingBackend
        backend = StubEmbeddingBackend()
        results = backend.encode_batch(["a", "b"])
        assert len(results) == 2

    def test_similarity_self(self):
        from contextledger.backends.embedding.stub import StubEmbeddingBackend
        backend = StubEmbeddingBackend()
        v = backend.encode("test")
        assert backend.similarity(v, v) == pytest.approx(1.0, abs=0.01)

    def test_deterministic_encode(self):
        """Same input should produce same embedding."""
        from contextledger.backends.embedding.stub import StubEmbeddingBackend
        backend = StubEmbeddingBackend()
        a = backend.encode("hello world")
        b = backend.encode("hello world")
        assert a == b
