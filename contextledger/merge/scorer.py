"""Precision/recall/novelty scoring for merge evaluation.

Compares synthesis outputs from parent vs fork versions.
"""


class Scorer:
    """Scores merge candidates using precision, recall, and novelty metrics."""

    def precision(self, extracted: list) -> float:
        """Return fraction of extracted items marked correct.

        Each item is a dict with a "correct" bool field.
        Returns 0.0 for empty input.
        """
        if not extracted:
            return 0.0
        correct_count = sum(1 for item in extracted if item.get("correct"))
        return correct_count / len(extracted)

    def recall(self, expected: list, found: list) -> float:
        """Return fraction of expected items that appear in found.

        Returns 0.0 for empty expected.
        """
        if not expected:
            return 0.0
        expected_set = set(expected)
        found_set = set(found)
        return len(expected_set & found_set) / len(expected)

    def novelty(self, baseline: list, new_findings: list) -> float:
        """Return fraction of new_findings not present in baseline.

        Returns 0.0 for empty new_findings.
        """
        if not new_findings:
            return 0.0
        baseline_set = set(baseline)
        novel_count = sum(1 for item in new_findings if item not in baseline_set)
        return novel_count / len(new_findings)

    def compare(self, parent_outputs: list, fork_outputs: list, expected: list) -> dict:
        """Compare parent and fork outputs, returning a structured report.

        Returns a dict with "parent", "fork", and "winner"/"recommendation" keys.
        Recall is computed using the "id" fields from outputs matched against expected.
        """
        parent_precision = self.precision(parent_outputs)
        fork_precision = self.precision(fork_outputs)

        parent_ids = [item["id"] for item in parent_outputs]
        fork_ids = [item["id"] for item in fork_outputs]

        parent_recall = self.recall(expected, parent_ids)
        fork_recall = self.recall(expected, fork_ids)

        parent_score = (parent_precision + parent_recall) / 2
        fork_score = (fork_precision + fork_recall) / 2

        if fork_score > parent_score:
            winner = "fork"
        elif parent_score > fork_score:
            winner = "parent"
        else:
            winner = "tie"

        return {
            "parent": {"precision": parent_precision, "recall": parent_recall},
            "fork": {"precision": fork_precision, "recall": fork_recall},
            "winner": winner,
            "recommendation": winner,
        }
