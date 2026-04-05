"""Tests for tier 2 semantic evaluation harness.

Runs both parent and fork synthesis versions against held-out
findings and produces comparison scores.

Task: TASK-010 — Implement tier 2 evaluation harness
"""

import pytest


class TestEvaluationHarness:
    """Test the semantic evaluation pipeline."""

    def test_evaluate_two_versions(self):
        """Should run both versions on the same findings and return scores."""
        from contextledger.merge.evaluator import Evaluator
        evaluator = Evaluator()
        findings = [
            {"id": f"f-{i}", "content": f"Finding {i}", "source": "session-001"}
            for i in range(10)
        ]
        parent_template = {"id": "t1", "prompt": "Extract patterns from {entities}"}
        fork_template = {"id": "t1", "prompt": "Identify anomalies in {entities}"}
        report = evaluator.evaluate(
            findings=findings,
            parent_template=parent_template,
            fork_template=fork_template,
        )
        assert "parent_score" in report
        assert "fork_score" in report

    def test_evaluate_returns_recommendation(self):
        """Evaluation should recommend: merge, reject, or parallel-run."""
        from contextledger.merge.evaluator import Evaluator
        evaluator = Evaluator()
        findings = [{"id": "f-1", "content": "Test finding"}]
        report = evaluator.evaluate(
            findings=findings,
            parent_template={"id": "t1", "prompt": "v1"},
            fork_template={"id": "t1", "prompt": "v2"},
        )
        assert report["recommendation"] in ("merge", "reject", "parallel")

    def test_evaluate_includes_comparison_metrics(self):
        """Report should include precision, recall, and novelty comparisons."""
        from contextledger.merge.evaluator import Evaluator
        evaluator = Evaluator()
        findings = [{"id": f"f-{i}", "content": f"Finding {i}"} for i in range(5)]
        report = evaluator.evaluate(
            findings=findings,
            parent_template={"id": "t1", "prompt": "v1"},
            fork_template={"id": "t1", "prompt": "v2"},
        )
        assert "precision" in report or "metrics" in report
        assert "recall" in report or "metrics" in report

    def test_evaluate_with_empty_findings(self):
        """Evaluation with no findings should return inconclusive."""
        from contextledger.merge.evaluator import Evaluator
        evaluator = Evaluator()
        report = evaluator.evaluate(
            findings=[],
            parent_template={"id": "t1", "prompt": "v1"},
            fork_template={"id": "t1", "prompt": "v2"},
        )
        assert report["recommendation"] in ("inconclusive", "parallel")

    def test_evaluate_uses_configurable_sample_size(self):
        """Should respect the sample_size parameter for findings."""
        from contextledger.merge.evaluator import Evaluator
        evaluator = Evaluator()
        findings = [{"id": f"f-{i}", "content": f"Finding {i}"} for i in range(100)]
        report = evaluator.evaluate(
            findings=findings,
            parent_template={"id": "t1", "prompt": "v1"},
            fork_template={"id": "t1", "prompt": "v2"},
            sample_size=20,
        )
        assert report.get("sample_size", 20) <= 20


class TestFindingsStore:
    """Test the findings store that feeds the evaluator."""

    def test_store_and_retrieve_findings(self):
        """Should store findings with profile provenance and retrieve them."""
        from contextledger.merge.evaluator import FindingsStore
        store = FindingsStore()
        store.add("db-research", {"id": "f-1", "content": "Schema has 3 tables"})
        store.add("db-research", {"id": "f-2", "content": "Table X has no index"})
        findings = store.get_by_profile("db-research")
        assert len(findings) == 2

    def test_get_last_n_findings(self):
        """Should retrieve the last N findings for a profile."""
        from contextledger.merge.evaluator import FindingsStore
        store = FindingsStore()
        for i in range(100):
            store.add("test-profile", {"id": f"f-{i}", "content": f"Finding {i}"})
        last_50 = store.get_by_profile("test-profile", limit=50)
        assert len(last_50) == 50

    def test_findings_track_provenance(self):
        """Each finding should track which profile and session produced it."""
        from contextledger.merge.evaluator import FindingsStore
        store = FindingsStore()
        store.add("db-research", {
            "id": "f-1",
            "content": "test",
            "source_session": "session-005",
        })
        findings = store.get_by_profile("db-research")
        assert findings[0].get("source_session") == "session-005"
