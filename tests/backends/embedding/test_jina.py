"""Tests for Jina EmbeddingBackend (local and API modes).

Local tests use a small model (all-MiniLM-L6-v2) for speed.
API tests only run if JINA_API_KEY is set.

Task: TASK-010 — Implement Jina EmbeddingBackend
"""

import os
import pytest

from contextledger.core.protocols import EmbeddingBackend


# --- Local backend tests (sentence-transformers) ---

_has_sentence_transformers = False
try:
    import sentence_transformers  # noqa: F401
    _has_sentence_transformers = True
except ImportError:
    pass


@pytest.fixture(scope="module")
def local_backend():
    if not _has_sentence_transformers:
        pytest.skip("sentence-transformers not installed")
    from contextledger.backends.embedding.jina import JinaEmbeddingBackend
    return JinaEmbeddingBackend(model_name="all-MiniLM-L6-v2")


class TestJinaLocalBackend:
    def test_implements_protocol(self, local_backend):
        assert isinstance(local_backend, EmbeddingBackend)

    def test_encode_returns_vector(self, local_backend):
        result = local_backend.encode("test text")
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(x, float) for x in result)

    def test_encode_batch(self, local_backend):
        results = local_backend.encode_batch(["a", "b", "c"])
        assert len(results) == 3

    def test_similarity_identical(self, local_backend):
        a = local_backend.encode("identical text")
        assert local_backend.similarity(a, a) == pytest.approx(1.0, abs=0.01)

    def test_semantic_similarity(self, local_backend):
        cat = local_backend.encode("the cat sat on the mat")
        kitten = local_backend.encode("the kitten rested on the rug")
        car = local_backend.encode("the car drove on the highway")
        assert local_backend.similarity(cat, kitten) > local_backend.similarity(cat, car)


# --- API backend tests (only if JINA_API_KEY is set) ---

_has_jina_api_key = bool(os.environ.get("JINA_API_KEY"))


@pytest.fixture(scope="module")
def api_backend():
    if not _has_jina_api_key:
        pytest.skip("JINA_API_KEY not set")
    from contextledger.backends.embedding.jina import JinaAPIEmbeddingBackend
    return JinaAPIEmbeddingBackend()


class TestJinaAPIBackend:
    def test_implements_protocol(self, api_backend):
        assert isinstance(api_backend, EmbeddingBackend)

    def test_encode_returns_vector(self, api_backend):
        result = api_backend.encode("test text")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_encode_batch(self, api_backend):
        results = api_backend.encode_batch(["a", "b"])
        assert len(results) == 2

    def test_similarity_identical(self, api_backend):
        a = api_backend.encode("identical text")
        assert api_backend.similarity(a, a) == pytest.approx(1.0, abs=0.01)

    def test_semantic_similarity(self, api_backend):
        cat = api_backend.encode("the cat sat on the mat")
        kitten = api_backend.encode("the kitten rested on the rug")
        car = api_backend.encode("the car drove on the highway")
        assert api_backend.similarity(cat, kitten) > api_backend.similarity(cat, car)


# --- API requires key ---

class TestJinaAPIRequiresKey:
    def test_raises_without_key(self, monkeypatch):
        monkeypatch.delenv("JINA_API_KEY", raising=False)
        from contextledger.backends.embedding.jina import JinaAPIEmbeddingBackend
        with pytest.raises(RuntimeError, match="JINA_API_KEY"):
            JinaAPIEmbeddingBackend()
