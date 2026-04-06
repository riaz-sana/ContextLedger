"""OpenAI-compatible embedding backend.

Works with:
- OpenAI directly (OPENAI_API_KEY)
- OpenRouter (OPENROUTER_API_KEY) — routes to any embedding model
- Any OpenAI-compatible API (custom base_url)

Uses the openai Python SDK which supports custom base URLs natively.
"""

import math
import os
from typing import List, Optional


class OpenAIEmbeddingBackend:
    """EmbeddingBackend using OpenAI-compatible embedding APIs.

    Supports OpenAI, OpenRouter, and any OpenAI-compatible endpoint.

    Requires: pip install openai

    Usage:
        # Direct OpenAI
        backend = OpenAIEmbeddingBackend()  # uses OPENAI_API_KEY

        # OpenRouter
        backend = OpenAIEmbeddingBackend(
            api_key=os.environ["OPENROUTER_API_KEY"],
            base_url="https://openrouter.ai/api/v1",
            model="openai/text-embedding-3-small",
        )

        # Auto-detect from environment (recommended)
        backend = OpenAIEmbeddingBackend.from_env()
    """

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self._model = model

        # Resolve API key
        self._api_key = api_key
        if not self._api_key:
            self._api_key = os.environ.get("OPENAI_API_KEY")
        if not self._api_key:
            raise ValueError(
                "No API key provided.\n"
                "Set OPENAI_API_KEY or OPENROUTER_API_KEY in your environment."
            )

        try:
            import openai
        except ImportError:
            raise RuntimeError("openai not installed. Run: pip install openai")

        kwargs = {"api_key": self._api_key}
        if base_url:
            kwargs["base_url"] = base_url

        self._client = openai.OpenAI(**kwargs)

    @classmethod
    def from_env(cls) -> "OpenAIEmbeddingBackend":
        """Auto-detect provider from environment variables.

        Priority:
        1. OPENAI_API_KEY + OPENAI_BASE_URL (custom endpoint)
        2. OPENROUTER_API_KEY (OpenRouter)
        3. OPENAI_API_KEY (direct OpenAI)

        Raises ValueError if no key is found.
        """
        openai_key = os.environ.get("OPENAI_API_KEY")
        openai_base = os.environ.get("OPENAI_BASE_URL")
        openrouter_key = os.environ.get("OPENROUTER_API_KEY")

        # Custom OpenAI-compatible endpoint
        if openai_key and openai_base:
            return cls(api_key=openai_key, base_url=openai_base)

        # OpenRouter
        if openrouter_key:
            return cls(
                api_key=openrouter_key,
                base_url="https://openrouter.ai/api/v1",
                model=os.environ.get("OPENROUTER_EMBEDDING_MODEL", "openai/text-embedding-3-small"),
            )

        # Direct OpenAI
        if openai_key:
            return cls(api_key=openai_key)

        raise ValueError(
            "No embedding API key found.\n"
            "Set one of:\n"
            "  OPENAI_API_KEY          — for OpenAI directly\n"
            "  OPENROUTER_API_KEY      — for OpenRouter\n"
            "  OPENAI_API_KEY + OPENAI_BASE_URL — for custom endpoint"
        )

    def encode(self, text: str) -> List[float]:
        response = self._client.embeddings.create(input=text, model=self._model)
        return response.data[0].embedding

    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        response = self._client.embeddings.create(input=texts, model=self._model)
        return [d.embedding for d in sorted(response.data, key=lambda d: d.index)]

    def similarity(self, a: List[float], b: List[float]) -> float:
        if len(a) != len(b) or not a:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
