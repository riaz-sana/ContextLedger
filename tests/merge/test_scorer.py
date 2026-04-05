"""Tests for precision/recall/novelty scoring.

Compares synthesis outputs from parent vs fork versions
to determine which produces better results.

Task: TASK-011 — Implement merge scoring module
"""

import pytest


class TestPrecisionScoring:
    """Test precision scoring of synthesis outputs."""

    def test_perfect_precision(self):
        """All extracted items being correct should yield precision 1.0."""
        from contextledger.merge.scorer import Scorer
        scorer = Scorer()
        extracted = [{"id": "1", "correct": True}, {"id": "2", "correct": True}]
        score = scorer.precision(extracted)
        assert score == pytest.approx(1.0)

    def test_zero_precision(self):
        """No correct items should yield precision 0.0."""
        from contextledger.merge.scorer import Scorer
        scorer = Scorer()
        extracted = [{"id": "1", "correct": False}, {"id": "2", "correct": False}]
        score = scorer.precision(extracted)
        assert score == pytest.approx(0.0)

    def test_partial_precision(self):
        """Mix of correct/incorrect should yield proportional precision."""
        from contextledger.merge.scorer import Scorer
        scorer = Scorer()
        extracted = [
            {"id": "1", "correct": True},
            {"id": "2", "correct": False},
            {"id": "3", "correct": True},
            {"id": "4", "correct": False},
        ]
        score = scorer.precision(extracted)
        assert score == pytest.approx(0.5)

    def test_precision_empty_input(self):
        """Empty extraction should return 0.0, not error."""
        from contextledger.merge.scorer import Scorer
        scorer = Scorer()
        score = scorer.precision([])
        assert score == pytest.approx(0.0)


class TestRecallScoring:
    """Test recall scoring of synthesis outputs."""

    def test_perfect_recall(self):
        """Finding all expected items should yield recall 1.0."""
        from contextledger.merge.scorer import Scorer
        scorer = Scorer()
        expected = ["a", "b", "c"]
        found = ["a", "b", "c"]
        score = scorer.recall(expected, found)
        assert score == pytest.approx(1.0)

    def test_zero_recall(self):
        """Finding none of the expected items should yield recall 0.0."""
        from contextledger.merge.scorer import Scorer
        scorer = Scorer()
        expected = ["a", "b", "c"]
        found = []
        score = scorer.recall(expected, found)
        assert score == pytest.approx(0.0)

    def test_partial_recall(self):
        """Finding some expected items should yield proportional recall."""
        from contextledger.merge.scorer import Scorer
        scorer = Scorer()
        expected = ["a", "b", "c", "d"]
        found = ["a", "c"]
        score = scorer.recall(expected, found)
        assert score == pytest.approx(0.5)


class TestNoveltyScoring:
    """Test novelty scoring — measuring new findings not in the baseline."""

    def test_all_novel(self):
        """All new findings not in baseline should be 100% novel."""
        from contextledger.merge.scorer import Scorer
        scorer = Scorer()
        baseline = ["old-1", "old-2"]
        new_findings = ["new-1", "new-2", "new-3"]
        score = scorer.novelty(baseline, new_findings)
        assert score == pytest.approx(1.0)

    def test_no_novelty(self):
        """Findings that are all duplicates of baseline should be 0% novel."""
        from contextledger.merge.scorer import Scorer
        scorer = Scorer()
        baseline = ["a", "b", "c"]
        new_findings = ["a", "b"]
        score = scorer.novelty(baseline, new_findings)
        assert score == pytest.approx(0.0)

    def test_partial_novelty(self):
        """Mix of novel and known findings should yield proportional novelty."""
        from contextledger.merge.scorer import Scorer
        scorer = Scorer()
        baseline = ["a", "b"]
        new_findings = ["a", "c"]  # "a" known, "c" novel
        score = scorer.novelty(baseline, new_findings)
        assert score == pytest.approx(0.5)


class TestComparativeScoring:
    """Test comparing two synthesis versions against each other."""

    def test_compare_returns_structured_report(self):
        """compare() should return a report with both versions' metrics."""
        from contextledger.merge.scorer import Scorer
        scorer = Scorer()
        parent_outputs = [{"id": "1", "correct": True}, {"id": "2", "correct": True}]
        fork_outputs = [{"id": "1", "correct": True}, {"id": "3", "correct": False}]
        report = scorer.compare(parent_outputs, fork_outputs, expected=["1", "2", "3"])
        assert "parent" in report
        assert "fork" in report
        assert "precision" in report["parent"]
        assert "precision" in report["fork"]

    def test_compare_identifies_winner(self):
        """compare() should identify which version scored higher overall."""
        from contextledger.merge.scorer import Scorer
        scorer = Scorer()
        parent_outputs = [{"id": "1", "correct": True}]
        fork_outputs = [{"id": "1", "correct": True}, {"id": "2", "correct": True}]
        report = scorer.compare(parent_outputs, fork_outputs, expected=["1", "2"])
        assert "winner" in report or "recommendation" in report
