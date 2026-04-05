"""LangChain callback handler for ContextLedger.

Captures LLM interactions during LangChain chain execution and ingests
them into ContextLedger as session logs via ContextLedgerMCP.

LangChain is an optional dependency. If not installed, the handler can
still be imported but will raise on instantiation.
"""

from __future__ import annotations

import uuid
from typing import Any, List, Optional

try:
    from langchain_core.callbacks import BaseCallbackHandler

    _LANGCHAIN_AVAILABLE = True
except ImportError:
    _LANGCHAIN_AVAILABLE = False

    class BaseCallbackHandler:  # type: ignore[no-redef]
        """Minimal stand-in so the class definition succeeds without langchain."""
        pass


from contextledger.core.protocols import EmbeddingBackend
from contextledger.mcp.server import ContextLedgerMCP


class ContextLedgerCallbackHandler(BaseCallbackHandler):
    """LangChain callback handler that feeds interactions into ContextLedger.

    Usage::

        from contextledger.integrations.langchain_handler import ContextLedgerCallbackHandler

        handler = ContextLedgerCallbackHandler(embedding_backend=my_backend)
        chain.invoke(input, config={"callbacks": [handler]})

    The handler accumulates user/assistant messages during a chain run
    and ingests them as a session when ``on_chain_end`` fires.
    """

    def __init__(
        self,
        embedding_backend: EmbeddingBackend,
        profile: Optional[str] = None,
    ) -> None:
        if not _LANGCHAIN_AVAILABLE:
            raise ImportError(
                "langchain is required to instantiate ContextLedgerCallbackHandler. "
                "Install it with: pip install langchain-core"
            )
        super().__init__()
        self.server = ContextLedgerMCP(embedding_backend=embedding_backend)
        if profile is not None:
            self.server.skill_checkout(profile)
        self._current_session: List[dict] = []
        self._ingested_session_ids: List[str] = []

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        **kwargs: Any,
    ) -> None:
        """Capture the first prompt as a user message."""
        if prompts:
            self._current_session.append({
                "role": "user",
                "content": prompts[0],
            })

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        """Capture the LLM response text as an assistant message."""
        text = ""
        # Handle both LLMResult objects and plain objects with a .text attr
        if hasattr(response, "generations") and response.generations:
            first_gen = response.generations[0]
            if isinstance(first_gen, list) and first_gen:
                text = first_gen[0].text if hasattr(first_gen[0], "text") else str(first_gen[0])
            elif hasattr(first_gen, "text"):
                text = first_gen.text
        elif hasattr(response, "text"):
            text = response.text

        if text:
            self._current_session.append({
                "role": "assistant",
                "content": text,
            })

    def on_chain_end(self, outputs: dict[str, Any], **kwargs: Any) -> None:
        """Ingest accumulated session into ContextLedger and reset buffer."""
        if not self._current_session:
            return

        session_id = str(uuid.uuid4())
        session_log = {
            "session_id": session_id,
            "messages": list(self._current_session),
        }
        self.server.ctx_ingest(session_log)
        self._ingested_session_ids.append(session_id)
        self._current_session.clear()
