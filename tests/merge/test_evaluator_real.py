"""Tests for Tier 2 LLM-backed evaluation.

Task: TASK-029 — Wire LLM into Tier 2 evaluation
"""

import pytest

from contextledger.merge.evaluator import Evaluator, FindingsStore
from contextledger.merge.scorer import Scorer
from contextledger.merge.resolver import ConflictResolver
from contextledger.backends.llm.stub import StubLLMClient


class TestEvaluatorWithLLM:
    def setup_method(self):
        self.llm = StubLLMClient()
        self.evaluator = Evaluator()

    def test_run_template_returns_findings(self):
        template = {"id": "t1", "prompt": "Find patterns in {entities}"}
        findings = [{"id": "f1", "content": "test finding"}]
        profile = {"synthesis": {"templates": [template]}}
        result = self.evaluator._run_template(template, findings, profile, self.llm)
        assert isinstance(result, list)

    def test_evaluate_with_llm_returns_report(self):
        findings = [{"id": f"f{i}", "content": f"Finding {i}"} for i in range(5)]
        parent_t = {"id": "t1", "prompt": "Analyze {entities}"}
        fork_t = {"id": "t1", "prompt": "Deep analyze {entities}"}
        profile = {"synthesis": {"templates": [parent_t, fork_t]}}
        report = self.evaluator.evaluate_with_llm(
            findings, parent_t, fork_t, profile, self.llm
        )
        assert "recommendation" in report
        assert report["recommendation"] in ("merge", "reject", "parallel")
        assert "parent_score" in report
        assert "fork_score" in report

    def test_evaluate_with_llm_empty_findings(self):
        report = self.evaluator.evaluate_with_llm(
            [], {"id": "t1", "prompt": "v1"}, {"id": "t1", "prompt": "v2"},
            {}, self.llm
        )
        assert report["recommendation"] == "inconclusive"

    def test_evaluate_with_llm_includes_judge(self):
        findings = [{"id": "f1", "content": "test"}]
        profile = {"synthesis": {"templates": [{"id": "t1", "prompt": "Analyze {entities}"}]}}
        report = self.evaluator.evaluate_with_llm(
            findings,
            {"id": "t1", "prompt": "v1"},
            {"id": "t1", "prompt": "v2"},
            profile, self.llm,
        )
        assert "judge" in report
        assert "sample_size" in report


class TestScorerLLMJudge:
    def test_llm_judge_returns_winner(self):
        llm = StubLLMClient()
        scorer = Scorer()
        # The prompt contains "winner" and "precision" so StubLLMClient routes correctly
        result = scorer.score_with_llm_judge(
            [{"content": "finding a"}], [{"content": "finding b"}], llm
        )
        # StubLLMClient checks for "evaluat" or "winner" or "precision" in the prompt
        # scorer.score_with_llm_judge builds a prompt containing all three
        assert "winner" in result
        assert result["winner"] in ("a", "b", "tie")

    def test_llm_judge_returns_metrics(self):
        llm = StubLLMClient()
        scorer = Scorer()
        result = scorer.score_with_llm_judge(
            [{"content": "a"}], [{"content": "b"}], llm
        )
        assert "precision_a" in result
        assert "recall_b" in result
        assert "confidence" in result

    def test_llm_judge_parse_failure_returns_tie(self):
        """If LLM returns unparseable response, should gracefully return tie."""

        class BadLLM:
            def complete(self, prompt, max_tokens=1000):
                return "this is not json"

        scorer = Scorer()
        result = scorer.score_with_llm_judge([], [], BadLLM())
        assert result["winner"] == "tie"
        assert result["confidence"] == 0.0


class TestResolverTier2:
    def test_evaluate_tier2_with_stub_llm(self):
        resolver = ConflictResolver()
        llm = StubLLMClient()
        findings = [{"id": "f1", "content": "test finding"}]
        profile = {"synthesis": {"templates": [{"id": "parent_eval", "prompt": "v1"}, {"id": "fork_eval", "prompt": "v2"}]}}
        result = resolver.evaluate_tier2(
            "synthesis.templates.t1",
            "original prompt", "modified prompt",
            profile, llm, recent_findings=findings,
        )
        assert result["conflict_type"] == "tier2"
        assert result["requires_user_decision"] is True
        assert "recommendation" in result

    def test_evaluate_tier2_without_findings(self):
        resolver = ConflictResolver()
        llm = StubLLMClient()
        result = resolver.evaluate_tier2(
            "section", "v1", "v2", {}, llm, recent_findings=[]
        )
        assert result["conflict_type"] == "tier2"
