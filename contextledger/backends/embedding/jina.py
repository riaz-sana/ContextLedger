"""Jina EmbeddingBackend implementation.

Uses sentence-transformers to load the jinaai/jina-embeddings-v3 model locally.
Requires: pip install sentence-transformers  (core dependency)
"""

import math
from typing import List

from sentence_transformers import SentenceTransformer


class JinaEmbeddingBackend:
    """EmbeddingBackend using Jina embeddings v3 via sentence-transformers.

    The model is downloaded on first use and cached locally.
    """

    def __init__(self, model_name: str = "jinaai/jina-embeddings-v3"):
        self._model = SentenceTransformer(model_name, trust_remote_code=True)

    def encode(self, text: str) -> List[float]:
        return self._model.encode(text).tolist()

    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        embeddings = self._model.encode(texts)
        return [e.tolist() for e in embeddings]

    def similarity(self, a: List[float], b: List[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(x * x for x in b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)
