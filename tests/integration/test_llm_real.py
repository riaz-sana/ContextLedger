"""Real LLM integration tests using ANTHROPIC_API_KEY.

These test the actual Tier 2 evaluation pipeline, NodeExecutor,
and LLM-as-judge scoring against a live Claude API.

Requires ANTHROPIC_API_KEY in environment or .env file.
"""

import os
import json
import pytest

# Load .env if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

_has_api_key = bool(os.environ.get("ANTHROPIC_API_KEY"))

if not _has_api_key:
    pytest.skip(
        "ANTHROPIC_API_KEY not set — skipping real LLM tests",
        allow_module_level=True,
    )


from contextledger.backends.llm.claude import ClaudeLLMClient
from contextledger.skill.dag import DAGExecutor, NodeExecutor
from contextledger.merge.evaluator import Evaluator
from contextledger.merge.scorer import Scorer
from contextledger.merge.resolver import ConflictResolver


@pytest.fixture(scope="module")
def llm():
    return ClaudeLLMClient()


class TestClaudeLLMClient:
    def test_complete_returns_string(self, llm):
        result = llm.complete("Say hello in one word.", max_tokens=10)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_complete_returns_json_when_asked(self, llm):
        result = llm.complete(
            'Return only this JSON, no other text: {"status": "ok"}',
            max_tokens=50,
        )
        # Should be parseable as JSON (possibly with markdown fencing)
        clean = result.strip().replace("```json", "").replace("```", "").strip()
        parsed = json.loads(clean)
        assert parsed["status"] == "ok"


class TestNodeExecutorWithRealLLM:
    def test_extraction_node(self, llm):
        executor = NodeExecutor(llm)
        node = {"id": "extract", "type": "extraction", "depends_on": []}
        profile = {
            "extraction": {
                "entities": ["database_table", "finding"],
                "rules": [{"match": "table", "extract": "database_table"}],
            }
        }
        result = executor.execute(
            node,
            {"raw_content": "The users table has no index on the email column. Query times are 4.2 seconds."},
            profile,
        )
        # LLM must return a dict with entities key — even if empty, the structure matters
        assert "entities" in result
        assert isinstance(result["entities"], list)

    def test_reasoning_node(self, llm):
        executor = NodeExecutor(llm)
        node = {"id": "reason", "type": "reasoning", "depends_on": []}
        profile = {
            "memory_schema": {
                "graph_nodes": ["Entity", "Finding"],
                "graph_edges": [{"from": "Entity", "to": "Finding", "label": "discovered_in"}],
            }
        }
        result = executor.execute(
            node,
            {"entities": [{"type": "table", "value": "users"}, {"type": "finding", "value": "missing index"}]},
            profile,
        )
        assert "relationships" in result

    def test_full_dag_pipeline(self, llm):
        executor = DAGExecutor(node_executor=NodeExecutor(llm))
        dag = {
            "nodes": [
                {"id": "extract", "type": "extraction", "depends_on": []},
                {"id": "reason", "type": "reasoning", "depends_on": ["extract"]},
            ]
        }
        profile = {
            "extraction": {"entities": ["finding"], "rules": []},
            "memory_schema": {"graph_nodes": ["Finding"]},
        }
        results = executor.execute(
            dag,
            context={"raw_content": "The API endpoint /users returns 500 errors under load"},
            profile=profile,
        )
        assert "extract" in results
        assert "reason" in results


class TestTier2WithRealLLM:
    def test_evaluator_with_real_llm(self, llm):
        evaluator = Evaluator()
        findings = [
            {"id": "f1", "content": "Database has no index on users.email"},
            {"id": "f2", "content": "API response time spikes at 3pm daily"},
            {"id": "f3", "content": "Log rotation is misconfigured, filling disk"},
        ]
        parent_template = {"id": "t1", "prompt": "List all issues found in: {entities}"}
        fork_template = {"id": "t1", "prompt": "Analyze severity and impact of: {entities}"}
        profile = {"synthesis": {"templates": [parent_template, fork_template]}}

        report = evaluator.evaluate_with_llm(
            findings, parent_template, fork_template, profile, llm, sample_size=3
        )
        assert report["recommendation"] in ("merge", "reject", "parallel", "inconclusive")
        assert "judge" in report
        assert report["sample_size"] == 3

    def test_scorer_llm_judge(self, llm):
        scorer = Scorer()
        result = scorer.score_with_llm_judge(
            [{"content": "Missing index on email column", "confidence": 0.9}],
            [{"content": "Missing index on email column", "confidence": 0.9},
             {"content": "Potential N+1 query in user lookup", "confidence": 0.7}],
            llm,
        )
        assert result["winner"] in ("a", "b", "tie")
        assert 0.0 <= result["confidence"] <= 1.0
        assert "reasoning" in result

    def test_resolver_tier2_evaluation(self, llm):
        resolver = ConflictResolver()
        findings = [{"id": "f1", "content": "Test finding for evaluation"}]
        profile = {
            "synthesis": {
                "templates": [
                    {"id": "parent_eval", "prompt": "Summarize: {entities}"},
                    {"id": "fork_eval", "prompt": "Analyze critically: {entities}"},
                ]
            }
        }
        result = resolver.evaluate_tier2(
            "synthesis.templates.t1",
            "Summarize findings", "Analyze findings critically",
            profile, llm, recent_findings=findings,
        )
        assert result["conflict_type"] == "tier2"
        assert result["requires_user_decision"] is True
        assert result["recommendation"] in ("merge", "reject", "parallel", "inconclusive")
