"""Jina EmbeddingBackend implementation.

Uses jina-embeddings-v3 for local embedding generation.
"""

import math
from typing import List


class JinaEmbeddingBackend:
    """EmbeddingBackend using Jina embeddings v3.

    Requires jina-embeddings package: pip install jina-embeddings
    """

    def __init__(self, model_name: str = "jina-embeddings-v3"):
        self._model_name = model_name
        try:
            from jina_embeddings import JinaEmbeddings
            self._model = JinaEmbeddings(model_name)
        except ImportError:
            self._model = None

    def encode(self, text: str) -> List[float]:
        if self._model is None:
            raise RuntimeError("jina-embeddings not installed. Run: pip install jina-embeddings")
        return self._model.encode(text).tolist()

    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        if self._model is None:
            raise RuntimeError("jina-embeddings not installed")
        return [self._model.encode(t).tolist() for t in texts]

    def similarity(self, a: List[float], b: List[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(x * x for x in b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)
