"""Skill extractors for importing existing workflows into ContextLedger.

Three extractors:
- PythonExtractor: reads Python files, identifies extraction/synthesis functions,
  generates a profile.yaml stub.
- ClaudeSkillImporter: wraps an existing .claude/skills/SKILL.md in a profile.
- ExampleBasedCreator: infers extraction rules from example findings.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

import yaml


# Keywords that indicate a function is an extraction/synthesis candidate
_CANDIDATE_KEYWORDS = [
    "extract", "parse", "analyse", "analyze",
    "synthesise", "synthesize", "filter", "clean",
    "validate", "read", "load", "report",
    "summarise", "summarize",
]

# Map from keyword groups to DAG node types
_NODE_TYPE_MAP = {
    "extraction": ["extract", "parse", "read", "load"],
    "reasoning": ["analyse", "analyze"],
    "synthesis": ["synthesise", "synthesize", "summarise", "summarize", "report"],
    "filter": ["filter", "clean", "validate"],
}


class PythonExtractor:
    """Generates a profile.yaml stub from an existing Python file.

    Looks for:
    - Functions with candidate keywords in their names
    - Functions that return dicts with 'findings', 'entities', 'results' keys
    - Docstrings that describe what the function extracts
    """

    def extract(self, file_path: str) -> str:
        """Read a Python file, find candidate functions, generate a profile.yaml stub.

        Args:
            file_path: Path to the Python file to analyze.

        Returns:
            A YAML string representing the generated profile stub.
        """
        source = Path(file_path).read_text(encoding="utf-8")
        tree = ast.parse(source)

        candidates = self._find_candidates(tree)

        nodes = []
        for fn in candidates:
            node_type = self._infer_node_type(fn.name)
            depends_on = self._infer_dependencies(fn, candidates)
            nodes.append({
                "id": fn.name,
                "type": node_type,
                "depends_on": depends_on,
            })

        entities = self._infer_entities(candidates)
        return self._build_profile_stub(nodes, entities, file_path)

    def _find_candidates(self, tree: ast.Module) -> list[ast.FunctionDef]:
        """Find functions that look like extraction/synthesis logic.

        A function is a candidate if:
        - Its name contains one of the candidate keywords, OR
        - It returns a dict with keys like 'findings', 'entities', 'results'
        """
        candidates = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            name_lower = node.name.lower()

            # Check name keywords
            if any(kw in name_lower for kw in _CANDIDATE_KEYWORDS):
                candidates.append(node)
                continue

            # Check for dict returns with known keys
            if self._returns_known_dict(node):
                candidates.append(node)

        return candidates

    def _returns_known_dict(self, fn: ast.FunctionDef) -> bool:
        """Check if a function returns a dict with keys like findings/entities/results."""
        known_keys = {"findings", "entities", "results"}

        # Check return annotation for Dict
        if fn.returns and isinstance(fn.returns, ast.Subscript):
            if isinstance(fn.returns.value, ast.Name) and fn.returns.value.id == "Dict":
                return True

        # Walk the body for return statements returning dict literals
        for node in ast.walk(fn):
            if isinstance(node, ast.Return) and node.value:
                if isinstance(node.value, ast.Dict):
                    for key in node.value.keys:
                        if isinstance(key, ast.Constant) and isinstance(key.value, str):
                            if key.value in known_keys:
                                return True
        return False

    def _infer_node_type(self, fn_name: str) -> str:
        """Map a function name to a DAG node type based on keywords."""
        name_lower = fn_name.lower()
        for node_type, keywords in _NODE_TYPE_MAP.items():
            if any(kw in name_lower for kw in keywords):
                return node_type
        return "extraction"  # default

    def _infer_dependencies(
        self, fn: ast.FunctionDef, candidates: list[ast.FunctionDef]
    ) -> list[str]:
        """Inspect the function body for calls to other candidate functions."""
        candidate_names = {c.name for c in candidates}
        deps = []
        for node in ast.walk(fn):
            if isinstance(node, ast.Call):
                callee_name = None
                if isinstance(node.func, ast.Name):
                    callee_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    callee_name = node.func.attr
                if callee_name and callee_name in candidate_names and callee_name != fn.name:
                    if callee_name not in deps:
                        deps.append(callee_name)
        return deps

    def _infer_entities(self, candidates: list[ast.FunctionDef]) -> list[str]:
        """Extract entity type hints from return annotations and docstrings."""
        entities: list[str] = []
        known_entity_words = {
            "finding", "entity", "result", "table", "column",
            "component", "vulnerability", "decision", "pattern",
            "hypothesis", "relationship",
        }

        for fn in candidates:
            # Check return annotations
            if fn.returns:
                annotation_str = ast.dump(fn.returns)
                for word in known_entity_words:
                    if word in annotation_str.lower() and word not in entities:
                        entities.append(word)

            # Check docstring
            docstring = ast.get_docstring(fn)
            if docstring:
                doc_lower = docstring.lower()
                for word in known_entity_words:
                    if word in doc_lower and word not in entities:
                        entities.append(word)

            # Check return dict keys
            for node in ast.walk(fn):
                if isinstance(node, ast.Return) and node.value:
                    if isinstance(node.value, ast.Dict):
                        for key in node.value.keys:
                            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                                val = key.value.lower()
                                if val in known_entity_words and val not in entities:
                                    entities.append(val)

        if not entities:
            entities = ["finding", "entity", "result"]

        return entities

    def _build_profile_stub(
        self, nodes: list[dict], entities: list[str], file_path: str
    ) -> str:
        """Generate a valid YAML profile stub with REVIEW comments."""
        stem = Path(file_path).stem
        profile_name = stem.replace("_", "-") + "-skill"

        profile: dict[str, Any] = {
            "name": profile_name,
            "version": "1.0.0",
            "parent": None,
        }

        extraction: dict[str, Any] = {
            "entities": entities,
            "sources": ["unknown"],
        }

        dag_nodes = []
        for node in nodes:
            dag_node: dict[str, Any] = {
                "id": node["id"],
                "type": node["type"],
                "depends_on": node["depends_on"],
            }
            dag_nodes.append(dag_node)

        synthesis: dict[str, Any] = {
            "dag": {
                "nodes": dag_nodes,
            },
        }

        session_context: dict[str, Any] = {
            "mode": "skill_versioning",
            "cmv_enabled": True,
        }

        profile["extraction"] = extraction
        profile["synthesis"] = synthesis
        profile["session_context"] = session_context

        yaml_str = yaml.dump(profile, default_flow_style=False, sort_keys=False)

        # Add header comments and REVIEW markers
        lines = [
            f"# Auto-generated by: ctx extract --from {file_path}",
            "# Review and adjust before using.",
            "",
        ]

        for line in yaml_str.splitlines():
            lines.append(line)
            # Add REVIEW comments after key sections
            if line.strip() == "entities:" and "extraction" in yaml_str[:yaml_str.index(line)]:
                # Already emitted by yaml.dump, just add a comment after the section
                pass
            if line.strip().startswith("sources:"):
                pass

        yaml_output = "\n".join(lines) + "\n"

        # Insert REVIEW comments at strategic locations
        yaml_output = yaml_output.replace(
            "  sources:",
            "  sources:  # REVIEW: fill in actual data sources",
        )
        yaml_output = yaml_output.replace(
            "  entities:",
            "  entities:  # REVIEW: confirm these entity types",
            1,  # only first occurrence (in extraction section)
        )

        return yaml_output


class ClaudeSkillImporter:
    """Wraps an existing SKILL.md in a ContextLedger profile.

    The SKILL.md becomes a reference document in refs/.
    The profile YAML describes the skill's intent for extraction purposes.
    """

    def __init__(self, llm_client: Any) -> None:
        self.llm = llm_client

    def import_skill(self, skill_md_path: str) -> str:
        """Read a SKILL.md file and generate a profile.yaml that references it.

        Args:
            skill_md_path: Path to the .claude/skills/SKILL.md file.

        Returns:
            A YAML string for the generated profile.
        """
        content = Path(skill_md_path).read_text(encoding="utf-8")

        prompt = (
            "This is a Claude Code skill definition:\n\n"
            f"{content[:2000]}\n\n"
            "Infer:\n"
            "1. What domain is this skill for? (e.g. frontend development, security testing)\n"
            "2. What entities would be extracted from sessions using this skill?\n"
            "   (e.g. components, vulnerabilities, findings, decisions)\n"
            "3. What data sources does it work with?\n\n"
            'Return JSON only: {"domain": "...", "entities": [...], "sources": [...]}'
        )

        response = self.llm.complete(prompt, max_tokens=1000)
        data = self._parse_response(response)

        entities = data.get("entities", ["finding"])
        sources = data.get("sources", ["unknown"])
        domain = data.get("domain", "general")

        # Derive skill name from path
        skill_dir = Path(skill_md_path).parent.name
        profile_name = skill_dir + "-skill"
        if skill_dir in ("skills", ".claude"):
            # Fallback: use filename stem
            profile_name = Path(skill_md_path).stem.lower().replace(" ", "-") + "-skill"

        profile: dict[str, Any] = {
            "name": profile_name,
            "version": "1.0.0",
            "parent": None,
            "extraction": {
                "entities": entities,
                "sources": sources,
            },
            "synthesis": {
                "dag": {
                    "nodes": [
                        {
                            "id": "extract_entities",
                            "type": "extraction",
                            "depends_on": [],
                        },
                        {
                            "id": "build_relationships",
                            "type": "reasoning",
                            "depends_on": ["extract_entities"],
                        },
                        {
                            "id": "synthesise_findings",
                            "type": "synthesis",
                            "depends_on": ["build_relationships"],
                        },
                    ],
                },
            },
            "refs": [skill_md_path],
            "session_context": {
                "mode": "skill_versioning",
                "cmv_enabled": True,
            },
        }

        yaml_str = yaml.dump(profile, default_flow_style=False, sort_keys=False)

        header = (
            f"# Imported from: {skill_md_path}\n"
            f"# Domain: {domain}\n"
            "# REVIEW: verify inferred entities and sources\n"
            "\n"
        )

        return header + yaml_str

    def _parse_response(self, response: str) -> dict:
        """Parse LLM response as JSON, with fallback defaults."""
        try:
            clean = response.strip().replace("```json", "").replace("```", "").strip()
            return json.loads(clean)
        except (json.JSONDecodeError, ValueError):
            return {"domain": "general", "entities": ["finding"], "sources": ["unknown"]}


class ExampleBasedCreator:
    """Infers extraction rules from user-provided example findings.

    User provides 3+ examples of {session_excerpt, finding} pairs.
    The creator uses few-shot prompting to infer extraction rules,
    then generates a profile.yaml.
    """

    def __init__(self, llm_client: Any) -> None:
        self.llm = llm_client

    def create(self, examples: list[dict]) -> str:
        """Create a profile.yaml from example findings.

        Args:
            examples: List of dicts, each with 'session_excerpt' and 'finding' keys.
                      Minimum 3 examples required.

        Returns:
            A YAML string for the generated profile.

        Raises:
            ValueError: If fewer than 3 examples are provided.
        """
        if len(examples) < 3:
            raise ValueError(
                f"At least 3 examples are required, got {len(examples)}. "
                "More examples produce better extraction rules."
            )

        # Build few-shot prompt
        examples_text = ""
        for i, ex in enumerate(examples, 1):
            excerpt = ex.get("session_excerpt", "")
            finding = ex.get("finding", {})
            examples_text += (
                f"Example {i}:\n"
                f"  Session: {excerpt}\n"
                f"  Finding: {json.dumps(finding)}\n\n"
            )

        prompt = (
            "Given these examples of session excerpts and the findings extracted from them, "
            "infer the extraction rules.\n\n"
            f"{examples_text}"
            "Infer:\n"
            "1. What entity types are being extracted?\n"
            "2. What patterns in the session text trigger extraction?\n"
            "3. What fields does each finding have?\n\n"
            "Return JSON only:\n"
            '{"entities": [...], "rules": [{"match": "pattern description", '
            '"extract": "entity_type", "fields": [...]}], '
            '"domain": "..."}'
        )

        response = self.llm.complete(prompt, max_tokens=1000)
        data = self._parse_response(response)

        entities = data.get("entities", ["finding"])
        rules = data.get("rules", [])
        domain = data.get("domain", "general")

        # Build extraction rules in profile format
        profile_rules = []
        for rule in rules:
            profile_rule: dict[str, Any] = {
                "match": rule.get("match", ""),
                "extract": rule.get("extract", "finding"),
            }
            if "fields" in rule:
                profile_rule["fields"] = rule["fields"]
            if "confidence_threshold" in rule:
                profile_rule["confidence_threshold"] = rule["confidence_threshold"]
            profile_rules.append(profile_rule)

        # If no rules were inferred, create a default one
        if not profile_rules:
            profile_rules = [
                {"match": "general pattern", "extract": "finding", "confidence_threshold": 0.7}
            ]

        profile: dict[str, Any] = {
            "name": f"{domain}-skill",
            "version": "1.0.0",
            "parent": None,
            "extraction": {
                "entities": entities,
                "sources": ["session"],
                "rules": profile_rules,
            },
            "synthesis": {
                "dag": {
                    "nodes": [
                        {
                            "id": "extract_entities",
                            "type": "extraction",
                            "depends_on": [],
                        },
                        {
                            "id": "build_relationships",
                            "type": "reasoning",
                            "depends_on": ["extract_entities"],
                        },
                        {
                            "id": "synthesise_findings",
                            "type": "synthesis",
                            "depends_on": ["build_relationships"],
                        },
                    ],
                },
            },
            "session_context": {
                "mode": "skill_versioning",
                "cmv_enabled": True,
            },
        }

        yaml_str = yaml.dump(profile, default_flow_style=False, sort_keys=False)

        header = (
            f"# Generated from {len(examples)} examples\n"
            f"# Domain: {domain}\n"
            "# REVIEW: verify inferred extraction rules\n"
            "\n"
        )

        return header + yaml_str

    def _parse_response(self, response: str) -> dict:
        """Parse LLM response as JSON, with fallback defaults."""
        try:
            clean = response.strip().replace("```json", "").replace("```", "").strip()
            return json.loads(clean)
        except (json.JSONDecodeError, ValueError):
            return {"domain": "general", "entities": ["finding"], "rules": []}
