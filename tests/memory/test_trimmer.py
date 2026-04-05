"""Tests for lossless three-pass trimming algorithm.

The trimmer strips mechanical bloat from session logs while
preserving semantic content. Three passes:
1. Strip raw tool outputs (JSON blobs, stderr, stdout)
2. Strip base64-encoded content (images, files)
3. Strip metadata/formatting overhead

Task: TASK-005 — Implement lossless three-pass trimmer
"""

import pytest


class TestPass1ToolOutputStripping:
    """Pass 1: Remove raw tool outputs."""

    def test_strips_tool_output_blocks(self):
        """Should remove [TOOL_OUTPUT] blocks from messages."""
        from contextledger.memory.trimmer import Trimmer
        trimmer = Trimmer()
        message = "Here are the results.\n[TOOL_OUTPUT] {\"rows\": 500, \"columns\": [\"id\"]}\nAs you can see..."
        result = trimmer.strip_tool_output(message)
        assert "[TOOL_OUTPUT]" not in result
        assert "Here are the results." in result
        assert "As you can see..." in result

    def test_preserves_non_tool_content(self):
        """Messages without tool output should pass through unchanged."""
        from contextledger.memory.trimmer import Trimmer
        trimmer = Trimmer()
        message = "This is a normal response with no tool output."
        result = trimmer.strip_tool_output(message)
        assert result == message

    def test_handles_multiple_tool_blocks(self):
        """Should strip all tool output blocks in a single message."""
        from contextledger.memory.trimmer import Trimmer
        trimmer = Trimmer()
        message = "First result:\n[TOOL_OUTPUT] {}\nSecond:\n[TOOL_OUTPUT] {\"data\": []}\nDone."
        result = trimmer.strip_tool_output(message)
        assert result.count("[TOOL_OUTPUT]") == 0
        assert "First result:" in result
        assert "Done." in result


class TestPass2Base64Stripping:
    """Pass 2: Remove base64-encoded content."""

    def test_strips_base64_images(self):
        """Should remove data:image/png;base64,... content."""
        from contextledger.memory.trimmer import Trimmer
        trimmer = Trimmer()
        message = f"Here's the chart:\n[IMAGE] data:image/png;base64,{'A' * 1000}\nThe chart shows..."
        result = trimmer.strip_base64(message)
        assert "base64," not in result
        assert "Here's the chart:" in result
        assert "The chart shows..." in result

    def test_preserves_text_without_base64(self):
        """Messages without base64 should pass through unchanged."""
        from contextledger.memory.trimmer import Trimmer
        trimmer = Trimmer()
        message = "No images here, just text."
        result = trimmer.strip_base64(message)
        assert result == message

    def test_replaces_with_placeholder(self):
        """Stripped base64 should leave a placeholder indicating content was removed."""
        from contextledger.memory.trimmer import Trimmer
        trimmer = Trimmer()
        message = f"[IMAGE] data:image/png;base64,{'A' * 500}"
        result = trimmer.strip_base64(message)
        assert "[image removed]" in result.lower() or "[trimmed]" in result.lower() or len(result) < 50


class TestPass3MetadataStripping:
    """Pass 3: Remove formatting overhead and metadata."""

    def test_strips_excessive_whitespace(self):
        """Should normalize excessive whitespace."""
        from contextledger.memory.trimmer import Trimmer
        trimmer = Trimmer()
        message = "Line one.\n\n\n\n\n\nLine two."
        result = trimmer.strip_metadata(message)
        assert result.count("\n") < 5

    def test_strips_timestamp_metadata(self):
        """Should remove inline timestamps and metadata markers."""
        from contextledger.memory.trimmer import Trimmer
        trimmer = Trimmer()
        message = "[2026-01-01T00:00:00Z] User asked about the schema.\n[META: tokens=150]"
        result = trimmer.strip_metadata(message)
        assert "[META:" not in result


class TestFullTrimPipeline:
    """Test the complete three-pass trim pipeline."""

    def test_trim_session_reduces_size(self, sample_session_log_heavy):
        """Full trim pipeline should reduce total content size."""
        from contextledger.memory.trimmer import Trimmer
        trimmer = Trimmer()
        original_size = sum(len(m["content"]) for m in sample_session_log_heavy["messages"])
        trimmed = trimmer.trim_session(sample_session_log_heavy)
        trimmed_size = sum(len(m["content"]) for m in trimmed["messages"])
        assert trimmed_size < original_size

    def test_trim_preserves_message_count(self, sample_session_log_heavy):
        """Trimming should not remove messages, only compress their content."""
        from contextledger.memory.trimmer import Trimmer
        trimmer = Trimmer()
        original_count = len(sample_session_log_heavy["messages"])
        trimmed = trimmer.trim_session(sample_session_log_heavy)
        assert len(trimmed["messages"]) == original_count

    def test_trim_preserves_user_messages_verbatim(self, sample_session_log):
        """User messages must never be modified by trimming."""
        from contextledger.memory.trimmer import Trimmer
        trimmer = Trimmer()
        trimmed = trimmer.trim_session(sample_session_log)
        original_user = [m for m in sample_session_log["messages"] if m["role"] == "user"]
        trimmed_user = [m for m in trimmed["messages"] if m["role"] == "user"]
        for orig, trim in zip(original_user, trimmed_user):
            assert orig["content"] == trim["content"]

    def test_trim_preserves_message_order(self, sample_session_log_heavy):
        """Message order must be preserved after trimming."""
        from contextledger.memory.trimmer import Trimmer
        trimmer = Trimmer()
        trimmed = trimmer.trim_session(sample_session_log_heavy)
        roles = [m["role"] for m in trimmed["messages"]]
        expected = [m["role"] for m in sample_session_log_heavy["messages"]]
        assert roles == expected

    def test_trim_threshold(self):
        """Trim should only activate when overhead exceeds threshold."""
        from contextledger.memory.trimmer import Trimmer
        trimmer = Trimmer(threshold=0.3)
        # Light session with minimal overhead should not be trimmed
        light_session = {
            "session_id": "light",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"},
            ]
        }
        trimmed = trimmer.trim_session(light_session)
        assert trimmed["messages"] == light_session["messages"]

    def test_trim_reports_reduction(self, sample_session_log_heavy):
        """Trimmer should report the reduction percentage."""
        from contextledger.memory.trimmer import Trimmer
        trimmer = Trimmer()
        trimmed = trimmer.trim_session(sample_session_log_heavy)
        assert "reduction_pct" in trimmed or hasattr(trimmed, "reduction_pct")
