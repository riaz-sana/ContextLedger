"""Embedding backend factory.

Priority: local first, API as explicit opt-in only.

  1. Jina local (sentence-transformers) — private, offline, Python <3.14
  2. Jina API (httpx + JINA_API_KEY) — only if key is set (explicit opt-in)
  3. OpenAI (httpx + OPENAI_API_KEY) — only if key is set

Local is always preferred. API backends only activate when their API key
is present in the environment — never silently.
"""

import os


class EmbeddingBackendNotAvailable(RuntimeError):
    """Raised when no real embedding backend can be loaded."""
    pass


def get_embedding_backend():
    """Load the best available embedding backend.

    Local-first. API only when explicitly opted in via API key.

    Raises:
        EmbeddingBackendNotAvailable: If no backend is available.
    """
    # 1. Try local Jina (private, no data leaves machine)
    try:
        from contextledger.backends.embedding.jina import JinaEmbeddingBackend
        return JinaEmbeddingBackend()
    except ImportError:
        pass
    except RuntimeError:
        pass  # sentence-transformers not installed

    # 2. Try Jina API (only if JINA_API_KEY is explicitly set)
    if os.environ.get("JINA_API_KEY"):
        try:
            from contextledger.backends.embedding.jina import JinaAPIEmbeddingBackend
            return JinaAPIEmbeddingBackend()
        except Exception as e:
            raise EmbeddingBackendNotAvailable(
                f"Jina API failed: {e}"
            ) from e

    # 3. Try OpenAI / OpenRouter (if any relevant key is set)
    if os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY"):
        try:
            from contextledger.backends.embedding.openai import OpenAIEmbeddingBackend
            return OpenAIEmbeddingBackend.from_env()
        except ImportError:
            pass
        except Exception as e:
            raise EmbeddingBackendNotAvailable(
                f"OpenAI/OpenRouter embeddings failed: {e}"
            ) from e

    # Nothing available
    raise EmbeddingBackendNotAvailable(
        "\n"
        "No embedding backend available.\n\n"
        "Option 1 — Local embeddings (PRIVATE, recommended):\n"
        "  pip install sentence-transformers\n"
        "  Requires Python 3.11-3.13. All data stays on your machine.\n\n"
        "Option 2 — Jina API (sends text to Jina's servers):\n"
        "  pip install httpx\n"
        "  export JINA_API_KEY=jina_...  (free at https://jina.ai)\n\n"
        "Option 3 — OpenAI (sends text to OpenAI):\n"
        "  pip install openai\n"
        "  export OPENAI_API_KEY=sk-...\n\n"
        "Option 4 — OpenRouter (routes to any model):\n"
        "  pip install openai\n"
        "  export OPENROUTER_API_KEY=sk-or-...\n"
    )
