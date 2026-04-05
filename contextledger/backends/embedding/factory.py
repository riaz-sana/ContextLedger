"""Embedding backend factory.

Tries to load a real embedding backend in priority order:
  1. Jina (local, free, no API key needed)
  2. OpenAI (cloud, requires OPENAI_API_KEY)

Never falls back to stub silently. If neither is available,
raises EmbeddingBackendNotAvailable with clear installation instructions.
"""

import os


class EmbeddingBackendNotAvailable(RuntimeError):
    """Raised when no real embedding backend can be loaded."""
    pass


def get_embedding_backend():
    """Load the best available embedding backend.

    Priority:
    1. Jina (jinaai/jina-embeddings-v3 via sentence-transformers)
    2. OpenAI text-embedding-3-small

    Raises:
        EmbeddingBackendNotAvailable: If no backend is available.
    """
    # Try Jina first
    try:
        from sentence_transformers import SentenceTransformer  # noqa: F401
        from contextledger.backends.embedding.jina import JinaEmbeddingBackend
        return JinaEmbeddingBackend()
    except ImportError:
        pass
    except Exception as e:
        raise EmbeddingBackendNotAvailable(
            f"Jina embeddings failed to load: {e}\n"
            "Try: pip install sentence-transformers"
        ) from e

    # Try OpenAI second
    if os.environ.get("OPENAI_API_KEY"):
        try:
            import openai  # noqa: F401
            from contextledger.backends.embedding.openai import OpenAIEmbeddingBackend
            return OpenAIEmbeddingBackend()
        except ImportError:
            pass
        except Exception as e:
            raise EmbeddingBackendNotAvailable(
                f"OpenAI embeddings failed to load: {e}\n"
                "Try: pip install openai"
            ) from e

    raise EmbeddingBackendNotAvailable(
        "\n"
        "ContextLedger requires an embedding backend to function.\n"
        "No embedding backend is currently available.\n\n"
        "Option 1 — Jina (recommended, free, runs locally):\n"
        "  pip install sentence-transformers\n\n"
        "Option 2 — OpenAI (requires API key):\n"
        "  pip install openai\n"
        "  export OPENAI_API_KEY=sk-...\n\n"
        "After installing, re-run your command."
    )
