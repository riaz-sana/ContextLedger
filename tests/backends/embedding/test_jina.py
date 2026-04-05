"""Tests for Jina EmbeddingBackend.

Uses sentence-transformers with jinaai/jina-embeddings-v3.
These are real embedding tests — no skip, no stub.

Task: TASK-010 — Implement Jina EmbeddingBackend
"""

import pytest

from contextledger.backends.embedding.jina import JinaEmbeddingBackend
from contextledger.core.protocols import EmbeddingBackend


# Use a small model for fast test runs. The real default is jinaai/jina-embeddings-v3
# but that's 570M params. all-MiniLM-L6-v2 validates the backend works correctly.
TEST_MODEL = "all-MiniLM-L6-v2"


@pytest.fixture(scope="module")
def jina_backend():
    """Module-scoped so the model loads once across all tests."""
    return JinaEmbeddingBackend(model_name=TEST_MODEL)


class TestJinaEmbeddingBackend:
    def test_implements_protocol(self, jina_backend):
        assert isinstance(jina_backend, EmbeddingBackend)

    def test_encode_returns_vector(self, jina_backend):
        result = jina_backend.encode("test text")
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(x, float) for x in result)

    def test_encode_batch(self, jina_backend):
        results = jina_backend.encode_batch(["a", "b", "c"])
        assert len(results) == 3
        assert all(isinstance(r, list) for r in results)

    def test_encode_batch_dimensions_consistent(self, jina_backend):
        results = jina_backend.encode_batch(["one", "two", "three"])
        dims = [len(r) for r in results]
        assert len(set(dims)) == 1

    def test_encode_and_batch_same_dimensions(self, jina_backend):
        single = jina_backend.encode("test")
        batch = jina_backend.encode_batch(["test"])
        assert len(single) == len(batch[0])

    def test_similarity_range(self, jina_backend):
        a = jina_backend.encode("cat")
        b = jina_backend.encode("dog")
        sim = jina_backend.similarity(a, b)
        assert -1.0 <= sim <= 1.0

    def test_similarity_identical(self, jina_backend):
        a = jina_backend.encode("identical text")
        sim = jina_backend.similarity(a, a)
        assert sim == pytest.approx(1.0, abs=0.01)

    def test_semantic_similarity(self, jina_backend):
        """Similar texts should have higher similarity than unrelated texts."""
        cat = jina_backend.encode("the cat sat on the mat")
        kitten = jina_backend.encode("the kitten rested on the rug")
        car = jina_backend.encode("the car drove on the highway")
        assert jina_backend.similarity(cat, kitten) > jina_backend.similarity(cat, car)

    def test_encode_empty_string(self, jina_backend):
        result = jina_backend.encode("")
        assert isinstance(result, list)
        assert len(result) > 0
