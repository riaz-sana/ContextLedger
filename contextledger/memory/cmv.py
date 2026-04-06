"""CMV (Contextual Memory Virtualisation) DAG engine.

Implements snapshot, branch, and trim primitives
based on arXiv:2602.22402.
"""

from copy import deepcopy
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from contextledger.memory.trimmer import Trimmer


class CMVEngine:
    """DAG-based session history engine with snapshot/branch/trim primitives."""

    def __init__(self) -> None:
        self._nodes: dict[str, dict] = {}
        self._head: Optional[str] = None

    def snapshot(self, session_log: dict) -> str:
        """Create a versioned node from a session log.

        Stores the messages, sets parent_id to current head, then advances head.
        """
        node_id = str(uuid4())
        messages = deepcopy(session_log["messages"])
        node = {
            "id": node_id,
            "type": "snapshot",
            "messages": messages,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "parent_id": self._head,
            "token_count": sum(len(m.get("content", "")) for m in messages),
        }
        self._nodes[node_id] = node
        self._head = node_id
        return node_id

    def branch(self, snapshot_id: str, orientation: str = None) -> str:
        """Create a new node referencing a parent snapshot.

        Does NOT update _head.
        """
        if snapshot_id not in self._nodes:
            raise ValueError(f"Snapshot {snapshot_id} does not exist")

        parent = self._nodes[snapshot_id]
        messages = deepcopy(parent["messages"])
        node_id = str(uuid4())
        node = {
            "id": node_id,
            "type": "branch",
            "messages": messages,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "parent_id": snapshot_id,
            "orientation": orientation,
            "token_count": sum(len(m.get("content", "")) for m in messages),
        }
        self._nodes[node_id] = node
        return node_id

    def trim(self, snapshot_id: str) -> str:
        """Create a trimmed copy of the snapshot using the Trimmer."""
        node = self._nodes[snapshot_id]
        trimmer = Trimmer()
        trimmed = trimmer.trim_session({"messages": node["messages"]})
        messages = trimmed["messages"]

        node_id = str(uuid4())
        new_node = {
            "id": node_id,
            "type": "trim",
            "messages": messages,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "parent_id": snapshot_id,
            "token_count": sum(len(m.get("content", "")) for m in messages),
            "reduction_pct": trimmed.get("reduction_pct", 0.0),
        }
        self._nodes[node_id] = new_node
        return node_id

    def get_node(self, id: str) -> Optional[dict]:
        """Return node by ID, or None if not found."""
        return self._nodes.get(id)

    def list_nodes(self) -> list:
        """Return all nodes in the DAG."""
        return list(self._nodes.values())

    def get_history(self, id: str) -> list:
        """Walk parent_id chain to root, return in chronological order (root first)."""
        chain = []
        visited: set[str] = set()
        current_id = id
        while current_id is not None:
            if current_id in visited:
                break  # cycle detected, stop traversal
            visited.add(current_id)
            node = self._nodes.get(current_id)
            if node is None:
                break
            chain.append(node)
            current_id = node.get("parent_id")
        chain.reverse()
        return chain

    def get_children(self, id: str) -> list:
        """Return all nodes whose parent_id equals id."""
        return [n for n in self._nodes.values() if n.get("parent_id") == id]

    def get_size(self, id: str) -> int:
        """Return total content size (sum of len(content) for all messages)."""
        node = self._nodes.get(id)
        if node is None:
            return 0
        return sum(len(m["content"]) for m in node["messages"])
