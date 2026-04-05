"""Lossless three-pass trimming algorithm.

Strips mechanical bloat (raw tool outputs, base64, metadata)
while preserving all user/assistant messages verbatim.
"""

import re
from copy import deepcopy


class Trimmer:
    """Three-pass lossless session trimmer.

    Pass 1: Strip raw tool outputs ([TOOL_OUTPUT] blocks)
    Pass 2: Strip base64-encoded content (images, files)
    Pass 3: Strip metadata markers and normalize whitespace
    """

    def __init__(self, threshold: float = 0.3) -> None:
        """Initialize trimmer with overhead threshold.

        Args:
            threshold: Minimum overhead ratio (0-1) before trimming activates.
                       If the estimated reduction is below this, messages are
                       returned unchanged.
        """
        self.threshold = threshold

    def strip_tool_output(self, message: str) -> str:
        """Pass 1: Remove [TOOL_OUTPUT] ... blocks.

        Removes everything from [TOOL_OUTPUT] to the end of that line,
        preserving surrounding text.
        """
        return re.sub(r"\[TOOL_OUTPUT\][^\n]*", "", message)

    def strip_base64(self, message: str) -> str:
        """Pass 2: Remove base64-encoded content.

        Handles both bare data URIs and [IMAGE] prefixed patterns.
        Replaces with [image removed] placeholder.
        """
        # [IMAGE] data:image/...;base64,... (to end of line)
        result = re.sub(
            r"\[IMAGE\]\s*data:[^\s]+;base64,[A-Za-z0-9+/=]+",
            "[image removed]",
            message,
        )
        # Bare data URIs without [IMAGE] prefix
        result = re.sub(
            r"data:image/[^\s]+;base64,[A-Za-z0-9+/=]+",
            "[image removed]",
            result,
        )
        return result

    def strip_metadata(self, message: str) -> str:
        """Pass 3: Remove [META:...] markers and normalize whitespace.

        Collapses runs of 3+ newlines down to 2.
        """
        result = re.sub(r"\[META:[^\]]*\]", "", message)
        # Collapse 3+ consecutive newlines to 2
        result = re.sub(r"\n{3,}", "\n\n", result)
        return result

    def _apply_passes(self, message: str) -> str:
        """Run all three passes on a single message string."""
        message = self.strip_tool_output(message)
        message = self.strip_base64(message)
        message = self.strip_metadata(message)
        return message

    def trim_session(self, session_log: dict) -> dict:
        """Run the full three-pass pipeline on a session log.

        - Preserves user messages verbatim.
        - Trims assistant messages through all three passes.
        - Preserves message count and order.
        - Returns a new dict with a ``reduction_pct`` key.
        - If overhead is below *threshold*, messages are returned unchanged
          (but the dict structure with ``reduction_pct`` is still returned).

        Args:
            session_log: Dict with at least a ``messages`` list of
                         ``{"role": str, "content": str, ...}`` dicts.

        Returns:
            New dict with ``messages`` (list) and ``reduction_pct`` (float).
        """
        messages = session_log["messages"]

        original_size = sum(len(m["content"]) for m in messages)

        # Build trimmed messages (deep copy to avoid mutating input)
        trimmed_messages = []
        for m in messages:
            new_m = dict(m)
            if m["role"] != "user":
                new_m["content"] = self._apply_passes(m["content"])
            trimmed_messages.append(new_m)

        trimmed_size = sum(len(m["content"]) for m in trimmed_messages)

        if original_size == 0:
            reduction_pct = 0.0
        else:
            reduction_pct = (original_size - trimmed_size) / original_size

        # If overhead is below threshold, return original messages unchanged
        if reduction_pct < self.threshold:
            return {
                **{k: v for k, v in session_log.items() if k != "messages"},
                "messages": list(messages),
                "reduction_pct": reduction_pct,
            }

        return {
            **{k: v for k, v in session_log.items() if k != "messages"},
            "messages": trimmed_messages,
            "reduction_pct": reduction_pct,
        }
