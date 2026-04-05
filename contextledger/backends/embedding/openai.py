"""OpenAI text-embedding-3 backend."""

import math
import os
from typing import List


class OpenAIEmbeddingBackend:
    """EmbeddingBackend using OpenAI text-embedding-3 models.

    Requires openai package: pip install openai
    Uses OPENAI_API_KEY environment variable for authentication.
    """

    def __init__(self, model: str = "text-embedding-3-small", api_key: str = None):
        self._model = model
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self._api_key:
            raise ValueError("OPENAI_API_KEY not set")
        try:
            import openai

            self._client = openai.OpenAI(api_key=self._api_key)
        except ImportError:
            raise RuntimeError("openai not installed. Run: pip install openai")

    def encode(self, text: str) -> List[float]:
        """Encode a single text string into an embedding vector."""
        response = self._client.embeddings.create(input=text, model=self._model)
        return response.data[0].embedding

    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        """Encode a batch of text strings into embedding vectors."""
        response = self._client.embeddings.create(input=texts, model=self._model)
        # OpenAI returns embeddings in the same order as inputs
        return [d.embedding for d in sorted(response.data, key=lambda d: d.index)]

    def similarity(self, a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two embedding vectors."""
        if len(a) != len(b) or not a:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
