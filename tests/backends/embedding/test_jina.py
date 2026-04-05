"""Tests for Jina EmbeddingBackend.

Task: TASK-013 — Implement Jina EmbeddingBackend
"""

import pytest

try:
    import jina_embeddings  # noqa: F401
    _has_jina = True
except ImportError:
    _has_jina = False


@pytest.mark.skipif(not _has_jina, reason="jina-embeddings not installed — pip install jina-embeddings")
class TestJinaEmbeddingBackend:
    def test_encode_returns_vector(self):
        from contextledger.backends.embedding.jina import JinaEmbeddingBackend
        backend = JinaEmbeddingBackend()
        result = backend.encode("test text")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_encode_batch(self):
        from contextledger.backends.embedding.jina import JinaEmbeddingBackend
        backend = JinaEmbeddingBackend()
        results = backend.encode_batch(["a", "b", "c"])
        assert len(results) == 3

    def test_similarity_range(self):
        from contextledger.backends.embedding.jina import JinaEmbeddingBackend
        backend = JinaEmbeddingBackend()
        a = backend.encode("cat")
        b = backend.encode("dog")
        sim = backend.similarity(a, b)
        assert -1.0 <= sim <= 1.0

    def test_semantic_similarity(self):
        """Similar texts should have higher similarity than unrelated texts."""
        from contextledger.backends.embedding.jina import JinaEmbeddingBackend
        backend = JinaEmbeddingBackend()
        cat = backend.encode("the cat sat on the mat")
        kitten = backend.encode("the kitten rested on the rug")
        car = backend.encode("the car drove on the highway")
        assert backend.similarity(cat, kitten) > backend.similarity(cat, car)
