"""Stub EmbeddingBackend for testing.

Returns mock embeddings. Implements EmbeddingBackend protocol.
"""

import hashlib
import math
from typing import List


class StubEmbeddingBackend:
    """Deterministic hash-based embedding backend for testing."""

    DIMS = 128

    def encode(self, text: str) -> List[float]:
        """Hash-based deterministic encoding. Same input always produces same output."""
        h = hashlib.sha512(text.encode("utf-8")).digest()
        # Extend hash bytes to cover 128 floats (need 128 * 4 = 512 bytes minimum)
        raw = h
        while len(raw) < self.DIMS * 4:
            raw += hashlib.sha512(raw).digest()
        # Convert bytes to floats in [-1, 1]
        vector = []
        for i in range(self.DIMS):
            # Take 4 bytes per float
            chunk = raw[i * 4 : (i + 1) * 4]
            val = int.from_bytes(chunk, "little", signed=True)
            vector.append(val / (2**31))
        # Normalize to unit length
        norm = math.sqrt(sum(x * x for x in vector))
        if norm > 0:
            vector = [x / norm for x in vector]
        return vector

    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.encode(t) for t in texts]

    def similarity(self, a: List[float], b: List[float]) -> float:
        """Cosine similarity between two vectors."""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)
