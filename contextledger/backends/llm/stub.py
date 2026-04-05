"""Stub LLMClient for testing.

Returns deterministic stub outputs. Used in tests only.
"""

import json


class StubLLMClient:
    """Deterministic LLM stub that returns predictable JSON responses."""

    def complete(self, prompt: str, max_tokens: int = 1000) -> str:
        """Return a stub JSON response based on prompt content."""
        prompt_lower = prompt.lower()

        # Evaluation/judge prompts — check FIRST because they contain many
        # keywords that overlap with other categories
        if "evaluat" in prompt_lower and ("precision" in prompt_lower or "winner" in prompt_lower):
            return json.dumps({
                "winner": "b",
                "confidence": 0.75,
                "reasoning": "Fork version extracts more findings",
                "precision_a": 0.7,
                "precision_b": 0.85,
                "recall_a": 0.6,
                "recall_b": 0.8,
                "novelty_a": 0.3,
                "novelty_b": 0.6,
            })

        # Skill importer / extractor prompts — domain inference
        if "claude code skill definition" in prompt_lower and "domain" in prompt_lower:
            return json.dumps({
                "domain": "frontend development",
                "entities": ["component", "design_pattern", "finding"],
                "sources": ["coding_session"],
            })

        # Example-based creator — extraction rule inference
        if "infer the extraction rules" in prompt_lower or (
            "example" in prompt_lower and "rules" in prompt_lower and "fields" in prompt_lower
        ):
            return json.dumps({
                "entities": ["finding", "table_issue"],
                "rules": [
                    {"match": "missing index or constraint", "extract": "table_issue", "fields": ["table", "column"]},
                    {"match": "slow query", "extract": "finding", "fields": ["table", "column", "duration"]},
                ],
                "domain": "database-analysis",
            })

        if "extract" in prompt_lower and "entities" in prompt_lower:
            return json.dumps({
                "entities": [
                    {"type": "finding", "value": "stub entity", "confidence": 0.85},
                    {"type": "table", "value": "users", "confidence": 0.9},
                ]
            })

        if "relationship" in prompt_lower or "reasoning" in prompt_lower:
            return json.dumps({
                "relationships": [
                    {"from": "users", "to": "stub entity", "label": "discovered_in"},
                ]
            })

        if "synthesi" in prompt_lower or "pattern" in prompt_lower or "findings" in prompt_lower:
            return json.dumps({
                "findings": [
                    {"content": "stub finding", "confidence": 0.8},
                    {"content": "another stub finding", "confidence": 0.7},
                ]
            })

        return json.dumps({"result": "stub response"})
