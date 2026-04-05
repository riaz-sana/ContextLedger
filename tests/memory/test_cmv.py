"""Tests for CMV DAG engine (snapshot, branch, trim).

Based on arXiv:2602.22402. The CMV engine manages session history
as a directed acyclic graph with three core primitives.

Task: TASK-003 — Implement CMV DAG engine
"""

import pytest


class TestSnapshot:
    """Snapshot captures the current session state as a versioned node."""

    def test_create_snapshot_from_session(self, sample_session_log):
        """Should create a snapshot node from a session log."""
        from contextledger.memory.cmv import CMVEngine
        engine = CMVEngine()
        snapshot_id = engine.snapshot(sample_session_log)
        assert isinstance(snapshot_id, str)
        assert len(snapshot_id) > 0

    def test_snapshot_preserves_all_messages(self, sample_session_log):
        """Snapshot must preserve every user and assistant message."""
        from contextledger.memory.cmv import CMVEngine
        engine = CMVEngine()
        snapshot_id = engine.snapshot(sample_session_log)
        node = engine.get_node(snapshot_id)
        original_count = len(sample_session_log["messages"])
        assert len(node["messages"]) == original_count

    def test_snapshot_has_timestamp(self, sample_session_log):
        """Each snapshot node must have a creation timestamp."""
        from contextledger.memory.cmv import CMVEngine
        engine = CMVEngine()
        snapshot_id = engine.snapshot(sample_session_log)
        node = engine.get_node(snapshot_id)
        assert "timestamp" in node
        assert node["timestamp"] is not None

    def test_snapshot_has_parent_reference(self, sample_session_log):
        """First snapshot has no parent. Subsequent snapshots reference previous."""
        from contextledger.memory.cmv import CMVEngine
        engine = CMVEngine()
        first = engine.snapshot(sample_session_log)
        second = engine.snapshot(sample_session_log)
        first_node = engine.get_node(first)
        second_node = engine.get_node(second)
        assert first_node.get("parent_id") is None
        assert second_node["parent_id"] == first

    def test_multiple_snapshots_form_chain(self, sample_session_log):
        """Multiple snapshots should form a linear chain (before branching)."""
        from contextledger.memory.cmv import CMVEngine
        engine = CMVEngine()
        ids = [engine.snapshot(sample_session_log) for _ in range(5)]
        for i in range(1, len(ids)):
            node = engine.get_node(ids[i])
            assert node["parent_id"] == ids[i - 1]

    def test_get_nonexistent_node(self):
        """get_node() on missing ID should return None."""
        from contextledger.memory.cmv import CMVEngine
        engine = CMVEngine()
        assert engine.get_node("nonexistent") is None


class TestBranch:
    """Branch creates a new session line from a snapshot."""

    def test_branch_from_snapshot(self, sample_session_log):
        """Should create a new branch from an existing snapshot."""
        from contextledger.memory.cmv import CMVEngine
        engine = CMVEngine()
        snapshot_id = engine.snapshot(sample_session_log)
        branch_id = engine.branch(snapshot_id, orientation="Exploring hypothesis A")
        assert isinstance(branch_id, str)
        assert branch_id != snapshot_id

    def test_branch_references_parent(self, sample_session_log):
        """Branch node must reference the snapshot it branched from."""
        from contextledger.memory.cmv import CMVEngine
        engine = CMVEngine()
        snapshot_id = engine.snapshot(sample_session_log)
        branch_id = engine.branch(snapshot_id)
        branch_node = engine.get_node(branch_id)
        assert branch_node["parent_id"] == snapshot_id

    def test_branch_carries_orientation(self, sample_session_log):
        """Branch should store an optional orientation message."""
        from contextledger.memory.cmv import CMVEngine
        engine = CMVEngine()
        snapshot_id = engine.snapshot(sample_session_log)
        branch_id = engine.branch(snapshot_id, orientation="Testing alternative query")
        branch_node = engine.get_node(branch_id)
        assert branch_node.get("orientation") == "Testing alternative query"

    def test_branch_does_not_modify_parent(self, sample_session_log):
        """Branching must not alter the parent snapshot."""
        from contextledger.memory.cmv import CMVEngine
        engine = CMVEngine()
        snapshot_id = engine.snapshot(sample_session_log)
        parent_before = engine.get_node(snapshot_id).copy()
        engine.branch(snapshot_id)
        parent_after = engine.get_node(snapshot_id)
        assert parent_before["messages"] == parent_after["messages"]

    def test_multiple_branches_from_same_snapshot(self, sample_session_log):
        """Multiple branches from the same snapshot should create a DAG."""
        from contextledger.memory.cmv import CMVEngine
        engine = CMVEngine()
        snapshot_id = engine.snapshot(sample_session_log)
        b1 = engine.branch(snapshot_id, orientation="Path A")
        b2 = engine.branch(snapshot_id, orientation="Path B")
        assert b1 != b2
        assert engine.get_node(b1)["parent_id"] == snapshot_id
        assert engine.get_node(b2)["parent_id"] == snapshot_id

    def test_branch_from_nonexistent_raises(self):
        """Branching from nonexistent snapshot should raise ValueError."""
        from contextledger.memory.cmv import CMVEngine
        engine = CMVEngine()
        with pytest.raises((ValueError, KeyError)):
            engine.branch("nonexistent-id")


class TestTrim:
    """Trim performs lossless compression on session history."""

    def test_trim_reduces_token_count(self, sample_session_log_heavy):
        """Trimming should reduce the total content size."""
        from contextledger.memory.cmv import CMVEngine
        engine = CMVEngine()
        snapshot_id = engine.snapshot(sample_session_log_heavy)
        original_size = engine.get_size(snapshot_id)
        trimmed_id = engine.trim(snapshot_id)
        trimmed_size = engine.get_size(trimmed_id)
        assert trimmed_size < original_size

    def test_trim_preserves_user_messages(self, sample_session_log_heavy):
        """Trimming must preserve all user messages verbatim."""
        from contextledger.memory.cmv import CMVEngine
        engine = CMVEngine()
        snapshot_id = engine.snapshot(sample_session_log_heavy)
        trimmed_id = engine.trim(snapshot_id)
        trimmed_node = engine.get_node(trimmed_id)
        original_user = [m for m in sample_session_log_heavy["messages"] if m["role"] == "user"]
        trimmed_user = [m for m in trimmed_node["messages"] if m["role"] == "user"]
        for orig, trimmed in zip(original_user, trimmed_user):
            assert orig["content"] == trimmed["content"]

    def test_trim_preserves_assistant_text(self, sample_session_log_heavy):
        """Trimming should preserve assistant response text but may strip tool outputs."""
        from contextledger.memory.cmv import CMVEngine
        engine = CMVEngine()
        snapshot_id = engine.snapshot(sample_session_log_heavy)
        trimmed_id = engine.trim(snapshot_id)
        trimmed_node = engine.get_node(trimmed_id)
        trimmed_assistant = [m for m in trimmed_node["messages"] if m["role"] == "assistant"]
        # Each assistant message should still contain the response text
        for msg in trimmed_assistant:
            assert "findings" in msg["content"].lower() or "response" in msg["content"].lower()

    def test_trim_strips_tool_output(self, sample_session_log_heavy):
        """Trimming should remove or compress [TOOL_OUTPUT] blocks."""
        from contextledger.memory.cmv import CMVEngine
        engine = CMVEngine()
        snapshot_id = engine.snapshot(sample_session_log_heavy)
        trimmed_id = engine.trim(snapshot_id)
        trimmed_node = engine.get_node(trimmed_id)
        full_content = " ".join(m["content"] for m in trimmed_node["messages"])
        # Tool output should be stripped or significantly reduced
        assert full_content.count("[TOOL_OUTPUT]") == 0 or \
            len(full_content) < len(" ".join(m["content"] for m in sample_session_log_heavy["messages"]))

    def test_trim_strips_base64(self, sample_session_log_heavy):
        """Trimming should remove base64-encoded image data."""
        from contextledger.memory.cmv import CMVEngine
        engine = CMVEngine()
        snapshot_id = engine.snapshot(sample_session_log_heavy)
        trimmed_id = engine.trim(snapshot_id)
        trimmed_node = engine.get_node(trimmed_id)
        full_content = " ".join(m["content"] for m in trimmed_node["messages"])
        assert "base64," not in full_content

    def test_trim_idempotent(self, sample_session_log_heavy):
        """Trimming an already-trimmed session should not change it further."""
        from contextledger.memory.cmv import CMVEngine
        engine = CMVEngine()
        snapshot_id = engine.snapshot(sample_session_log_heavy)
        trimmed_once = engine.trim(snapshot_id)
        size_once = engine.get_size(trimmed_once)
        trimmed_twice = engine.trim(trimmed_once)
        size_twice = engine.get_size(trimmed_twice)
        assert size_once == size_twice


class TestDAGOperations:
    """Test DAG-level queries across the session graph."""

    def test_list_all_nodes(self, sample_session_log):
        """Should list all nodes in the DAG."""
        from contextledger.memory.cmv import CMVEngine
        engine = CMVEngine()
        engine.snapshot(sample_session_log)
        engine.snapshot(sample_session_log)
        nodes = engine.list_nodes()
        assert len(nodes) == 2

    def test_get_history_linear(self, sample_session_log):
        """get_history() should return the chain of ancestors for a node."""
        from contextledger.memory.cmv import CMVEngine
        engine = CMVEngine()
        s1 = engine.snapshot(sample_session_log)
        s2 = engine.snapshot(sample_session_log)
        s3 = engine.snapshot(sample_session_log)
        history = engine.get_history(s3)
        assert [n["id"] for n in history] == [s1, s2, s3]

    def test_get_children(self, sample_session_log):
        """get_children() should return immediate child nodes."""
        from contextledger.memory.cmv import CMVEngine
        engine = CMVEngine()
        root = engine.snapshot(sample_session_log)
        b1 = engine.branch(root)
        b2 = engine.branch(root)
        children = engine.get_children(root)
        child_ids = [c["id"] for c in children]
        assert b1 in child_ids
        assert b2 in child_ids
