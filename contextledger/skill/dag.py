"""DAG executor for synthesis pipelines.

Executes directed acyclic graph of synthesis steps
defined in profile.yaml.
"""

from __future__ import annotations

import json
from collections import deque
from typing import Any, Callable, Optional


VALID_NODE_TYPES = {"extraction", "reasoning", "synthesis", "filter"}


class NodeExecutor:
    """Executes individual DAG nodes using an LLM client.

    Each node type has a handler that builds a prompt from the node's
    configuration and upstream outputs, calls the LLM, and parses the result.
    """

    def __init__(self, llm_client):
        self.llm_client = llm_client

    def execute(self, node: dict, inputs: dict, profile: dict) -> dict:
        """Execute a single node, dispatching to the correct handler."""
        handlers = {
            "extraction": self._handle_extraction,
            "reasoning": self._handle_reasoning,
            "synthesis": self._handle_synthesis,
            "filter": self._handle_filter,
        }
        handler = handlers.get(node["type"])
        if not handler:
            raise ValueError(f"Unknown node type: {node['type']}")
        return handler(node, inputs, profile)

    def _handle_extraction(self, node: dict, inputs: dict, profile: dict) -> dict:
        entity_types = profile.get("extraction", {}).get("entities", [])
        rules = profile.get("extraction", {}).get("rules", [])
        raw_content = inputs.get("raw_content", "")
        prompt = (
            f"Extract entities of types {entity_types} from the following content.\n"
            f"Rules: {rules}\n\n"
            f"Content:\n{raw_content}\n\n"
            f'Respond in JSON: {{"entities": [{{"type": ..., "value": ..., "confidence": 0-1}}]}}'
        )
        response = self.llm_client.complete(prompt, max_tokens=1000)
        return self._parse_json(response, {"entities": []})

    def _handle_reasoning(self, node: dict, inputs: dict, profile: dict) -> dict:
        entities = inputs.get("entities", [])
        graph_schema = profile.get("memory_schema", {})
        prompt = (
            f"Given these entities: {entities}\n"
            f"And this graph schema: {graph_schema}\n\n"
            f"Identify relationships between entities.\n"
            f'Respond in JSON: {{"relationships": [{{"from": ..., "to": ..., "label": ...}}]}}'
        )
        response = self.llm_client.complete(prompt, max_tokens=1000)
        return self._parse_json(response, {"relationships": []})

    def _handle_synthesis(self, node: dict, inputs: dict, profile: dict) -> dict:
        template_id = node.get("template")
        templates = profile.get("synthesis", {}).get("templates", [])
        template = next((t for t in templates if t["id"] == template_id), None)
        if not template:
            raise ValueError(f"Template '{template_id}' not found in profile")
        prompt = template["prompt"].format(
            entities=inputs.get("entities", []),
            relationships=inputs.get("relationships", []),
            source=inputs.get("source", "unknown"),
        )
        response = self.llm_client.complete(prompt, max_tokens=1500)
        return self._parse_json(response, {"findings": []})

    def _handle_filter(self, node: dict, inputs: dict, profile: dict) -> dict:
        findings = inputs.get("findings", [])
        threshold = node.get("confidence_threshold", 0.5)
        filtered = [f for f in findings if f.get("confidence", 1.0) >= threshold]
        return {"filtered_findings": filtered, "dropped": len(findings) - len(filtered)}

    @staticmethod
    def _parse_json(response: str, default: dict) -> dict:
        try:
            clean = response.strip().replace("```json", "").replace("```", "").strip()
            return json.loads(clean)
        except Exception:
            return default


class DAGExecutor:
    """Executes a DAG of synthesis nodes in topological (dependency) order.

    Accepts an optional ``node_executor`` for LLM-backed execution.
    Without it, nodes produce stub output dicts (backward compatible).
    """

    def __init__(self, node_executor: Optional[NodeExecutor] = None):
        self._node_executor = node_executor

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
        profile: Optional[dict] = None,
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

            if self._node_executor is not None and profile is not None:
                # Flatten upstream outputs into a single input dict
                merged_inputs = dict(context)
                for dep_output in upstream_outputs.values():
                    if isinstance(dep_output, dict):
                        merged_inputs.update(dep_output)
                outputs[node_id] = self._node_executor.execute(
                    node, merged_inputs, profile
                )
            else:
                outputs[node_id] = {
                    "node_id": node_id,
                    "type": node["type"],
                    "inputs": upstream_outputs,
                    "context": context,
                }

        return outputs
