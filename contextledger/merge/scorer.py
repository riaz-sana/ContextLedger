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

    def score_with_llm_judge(self, outputs_a: list, outputs_b: list, llm_client) -> dict:
        """Use LLM-as-judge to compare two sets of synthesis outputs.

        Returns dict with winner, confidence, reasoning, and per-set metrics.
        Falls back to tie if LLM response can't be parsed.
        """
        import json as _json
        prompt = (
            "You are evaluating two sets of findings extracted from the same source data.\n\n"
            f"Set A (parent profile version):\n{_json.dumps(outputs_a, indent=2)}\n\n"
            f"Set B (fork profile version):\n{_json.dumps(outputs_b, indent=2)}\n\n"
            "Evaluate each set on three dimensions (score 0.0 to 1.0):\n"
            "- Precision: are findings accurate and grounded in the source?\n"
            "- Recall: do findings capture all important information?\n"
            "- Novelty: does this set discover things the other misses?\n\n"
            "Respond ONLY in JSON:\n"
            '{"winner": "a" or "b" or "tie", "confidence": 0.0-1.0, '
            '"reasoning": "brief explanation", '
            '"precision_a": 0.0-1.0, "precision_b": 0.0-1.0, '
            '"recall_a": 0.0-1.0, "recall_b": 0.0-1.0, '
            '"novelty_a": 0.0-1.0, "novelty_b": 0.0-1.0}'
        )
        response = llm_client.complete(prompt, max_tokens=500)
        try:
            clean = response.strip().replace("```json", "").replace("```", "").strip()
            return _json.loads(clean)
        except Exception:
            return {
                "winner": "tie", "confidence": 0.0,
                "reasoning": "LLM judge parse failed",
                "precision_a": 0.5, "precision_b": 0.5,
                "recall_a": 0.5, "recall_b": 0.5,
                "novelty_a": 0.5, "novelty_b": 0.5,
            }

    def compare(self, parent_outputs: list, fork_outputs: list, expected: list) -> dict:
        """Compare parent and fork outputs, returning a structured report.

        Returns a dict with "parent", "fork", "winner"/"recommendation", and
        novelty scores. Recall is computed using "id" fields matched against expected.
        """
        parent_precision = self.precision(parent_outputs)
        fork_precision = self.precision(fork_outputs)

        parent_ids = [item["id"] for item in parent_outputs]
        fork_ids = [item["id"] for item in fork_outputs]

        parent_recall = self.recall(expected, parent_ids)
        fork_recall = self.recall(expected, fork_ids)

        # Novelty: how many findings does the fork surface that parent doesn't?
        fork_novelty = self.novelty(parent_ids, fork_ids)
        parent_novelty = self.novelty(fork_ids, parent_ids)

        parent_score = (parent_precision + parent_recall) / 2
        fork_score = (fork_precision + fork_recall) / 2

        if fork_score > parent_score:
            winner = "fork"
        elif parent_score > fork_score:
            winner = "parent"
        else:
            winner = "tie"

        return {
            "parent": {"precision": parent_precision, "recall": parent_recall, "novelty": parent_novelty},
            "fork": {"precision": fork_precision, "recall": fork_recall, "novelty": fork_novelty},
            "winner": winner,
            "recommendation": winner,
        }
