"""Profile YAML parser and validator.

Parses profile.yaml files and validates against the skill profile schema.
"""

from typing import Any

import yaml


_VALID_NODE_TYPES = {"extraction", "reasoning", "synthesis", "filter"}


class ProfileParser:
    """Parses and validates skill profile YAML documents."""

    def parse(self, yaml_string: str) -> dict[str, Any]:
        """Parse a YAML string into a profile dict.

        Returns the dict with keys: name, version, parent, extraction,
        synthesis, memory_schema, session_context.  Missing sections
        default to empty dicts/lists as appropriate.
        """
        raw = yaml.safe_load(yaml_string) or {}

        parent = raw.get("parent")
        if parent == "null" or parent is None:
            parent = None

        return {
            "name": raw.get("name"),
            "version": raw.get("version"),
            "parent": parent,
            "extraction": raw.get("extraction", {}),
            "synthesis": raw.get("synthesis", {}),
            "memory_schema": raw.get("memory_schema", {}),
            "session_context": raw.get("session_context", {}),
        }

    def validate(self, profile: dict[str, Any]) -> None:
        """Validate a parsed profile dict.

        Raises ``ValueError`` when the profile violates schema rules.
        """
        # Required top-level fields
        if not profile.get("name"):
            raise ValueError("Profile must have a 'name'")
        if not profile.get("version"):
            raise ValueError("Profile must have a 'version'")

        # Validate extraction rules
        extraction = profile.get("extraction", {})
        for rule in extraction.get("rules", []):
            threshold = rule.get("confidence_threshold")
            if threshold is not None and not (0 <= threshold <= 1):
                raise ValueError(
                    f"confidence_threshold must be between 0 and 1, got {threshold}"
                )

        # Validate synthesis DAG
        synthesis = profile.get("synthesis", {})
        dag = synthesis.get("dag", {})
        nodes = dag.get("nodes")
        if nodes:
            self._validate_dag(nodes)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_dag(nodes: list[dict[str, Any]]) -> None:
        """Check node types, dangling refs, and cycles."""
        node_ids = {n["id"] for n in nodes}

        for node in nodes:
            # Check node type
            ntype = node.get("type")
            if ntype not in _VALID_NODE_TYPES:
                raise ValueError(
                    f"Invalid node type '{ntype}'. "
                    f"Must be one of {sorted(_VALID_NODE_TYPES)}"
                )

            # Check dangling dependencies
            for dep in node.get("depends_on", []):
                if dep not in node_ids:
                    raise ValueError(
                        f"Node '{node['id']}' depends on '{dep}' which does not exist"
                    )

        # Cycle detection via iterative topological sort (Kahn's algorithm)
        in_degree: dict[str, int] = {n["id"]: 0 for n in nodes}
        adjacency: dict[str, list[str]] = {n["id"]: [] for n in nodes}
        for node in nodes:
            for dep in node.get("depends_on", []):
                adjacency[dep].append(node["id"])
                in_degree[node["id"]] += 1

        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        visited = 0
        while queue:
            current = queue.pop(0)
            visited += 1
            for neighbour in adjacency[current]:
                in_degree[neighbour] -= 1
                if in_degree[neighbour] == 0:
                    queue.append(neighbour)

        if visited != len(nodes):
            raise ValueError("Cycle detected in synthesis DAG")
