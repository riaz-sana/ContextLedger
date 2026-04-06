"""Jina EmbeddingBackend implementation.

Two modes:
- Local (default): sentence-transformers, offline, private — nothing leaves your machine
- API: Jina AI's REST API, lightweight, works on Python 3.14 — sends text to Jina's servers

Local mode is always preferred. API mode is explicit opt-in only.
"""

import math
import os
from typing import List


class JinaEmbeddingBackend:
    """Local Jina embeddings via sentence-transformers.

    All data stays on your machine. Requires:
        pip install sentence-transformers

    Does NOT work on Python 3.14 (no wheel yet). Use JinaAPIEmbeddingBackend
    or downgrade to Python 3.12 for local embeddings.
    """

    def __init__(self, model_name: str = "jinaai/jina-embeddings-v3"):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise RuntimeError(
                "sentence-transformers not installed.\n"
                "For local (private) embeddings: pip install sentence-transformers\n"
                "Requires Python <3.14. On 3.14, use JinaAPIEmbeddingBackend instead."
            )
        self._model = SentenceTransformer(model_name, trust_remote_code=True)

    def encode(self, text: str) -> List[float]:
        return self._model.encode(text).tolist()

    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        return [e.tolist() for e in self._model.encode(texts)]

    def similarity(self, a: List[float], b: List[float]) -> float:
        return _cosine_similarity(a, b)


class JinaAPIEmbeddingBackend:
    """Jina embeddings via REST API.

    WARNING: Sends your text to Jina's servers. Use only if you accept that.
    Free tier: 1M tokens/month. Requires JINA_API_KEY.

    For private/offline embeddings, use JinaEmbeddingBackend (local) instead.
    """

    def __init__(self, model_name: str = "jina-embeddings-v3", api_key: str = None):
        try:
            import httpx  # noqa: F401
        except ImportError:
            raise RuntimeError("httpx not installed. Run: pip install httpx")

        self._model_name = model_name
        self._api_key = api_key or os.environ.get("JINA_API_KEY", "")
        if not self._api_key:
            raise RuntimeError(
                "JINA_API_KEY not set.\n"
                "Get a free key at https://jina.ai/api-dashboard/key-manager\n"
                "Then: export JINA_API_KEY=jina_...\n\n"
                "Or use local embeddings instead (private, no API key):\n"
                "  pip install sentence-transformers  (requires Python <3.14)"
            )

    def encode(self, text: str) -> List[float]:
        return self._api_encode([text])[0]

    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        return self._api_encode(texts)

    def similarity(self, a: List[float], b: List[float]) -> float:
        return _cosine_similarity(a, b)

    def _api_encode(self, texts: List[str]) -> List[List[float]]:
        import httpx
        response = httpx.post(
            "https://api.jina.ai/v1/embeddings",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            json={"model": self._model_name, "input": texts},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        embeddings = sorted(data["data"], key=lambda x: x["index"])
        return [e["embedding"] for e in embeddings]


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
