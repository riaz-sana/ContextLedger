"""DAG executor for synthesis pipelines.

Executes directed acyclic graph of synthesis steps
defined in profile.yaml.
"""

from __future__ import annotations

from collections import deque
from typing import Callable, Optional


VALID_NODE_TYPES = {"extraction", "reasoning", "synthesis", "filter"}


class DAGExecutor:
    """Executes a DAG of synthesis nodes in topological (dependency) order."""

    def topological_sort(self, dag: dict) -> list[str]:
        """Return node IDs in valid execution order using Kahn's algorithm.

        Args:
            dag: Dict with "nodes" key containing list of node dicts,
                 each having "id", "type", and "depends_on" keys.

        Returns:
            List of node IDs in a valid topological order.

        Raises:
            ValueError: If the DAG contains a cycle.
        """
        nodes = dag.get("nodes", [])
        if not nodes:
            return []

        # Build adjacency and in-degree structures
        in_degree: dict[str, int] = {}
        dependents: dict[str, list[str]] = {}

        for node in nodes:
            node_id = node["id"]
            in_degree.setdefault(node_id, 0)
            dependents.setdefault(node_id, [])
            for dep in node.get("depends_on", []):
                dependents.setdefault(dep, [])
                dependents[dep].append(node_id)
                in_degree[node_id] = in_degree.get(node_id, 0) + 1

        # Kahn's algorithm
        queue: deque[str] = deque()
        for node_id, degree in in_degree.items():
            if degree == 0:
                queue.append(node_id)

        order: list[str] = []
        while queue:
            current = queue.popleft()
            order.append(current)
            for dependent in dependents.get(current, []):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(order) != len(nodes):
            raise ValueError("DAG contains a cycle")

        return order

    def execute(
        self,
        dag: dict,
        context: dict,
        on_node: Optional[Callable[[str], None]] = None,
    ) -> dict:
        """Execute all nodes in the DAG in topological order.

        Args:
            dag: Dict with "nodes" key containing list of node dicts.
            context: Shared context dict passed to every node.
            on_node: Optional callback invoked with each node_id before execution.

        Returns:
            Dict mapping node_id to its output dict.

        Raises:
            ValueError: If a node has an invalid type or the DAG has a cycle.
        """
        nodes = dag.get("nodes", [])
        if not nodes:
            return {}

        # Build a lookup for node definitions
        node_map: dict[str, dict] = {}
        for node in nodes:
            node_map[node["id"]] = node

        # Validate node types before executing anything
        for node in nodes:
            if node["type"] not in VALID_NODE_TYPES:
                raise ValueError(
                    f"Invalid node type '{node['type']}'. "
                    f"Valid types: {VALID_NODE_TYPES}"
                )

        order = self.topological_sort(dag)
        outputs: dict[str, dict] = {}

        for node_id in order:
            if on_node is not None:
                on_node(node_id)

            node = node_map[node_id]
            upstream_outputs = {
                dep: outputs[dep] for dep in node.get("depends_on", [])
            }

            outputs[node_id] = {
                "node_id": node_id,
                "type": node["type"],
                "inputs": upstream_outputs,
                "context": context,
            }

        return outputs
