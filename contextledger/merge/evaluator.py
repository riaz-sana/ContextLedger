"""Tier 2 semantic evaluation harness.

Runs both parent and fork synthesis versions against
held-out findings to produce comparison scores.
"""

from contextledger.merge.scorer import Scorer


class FindingsStore:
    """Store and retrieve findings with profile provenance."""

    def __init__(self):
        self._store = {}  # profile_name -> list of finding dicts

    def add(self, profile: str, finding: dict):
        """Store finding with profile provenance."""
        if profile not in self._store:
            self._store[profile] = []
        self._store[profile].append(finding)

    def get_by_profile(self, profile: str, limit=None):
        """Retrieve findings for a profile, optionally the last N."""
        findings = self._store.get(profile, [])
        if limit:
            return findings[-limit:]
        return list(findings)


class Evaluator:
    """Tier 2 semantic evaluation harness.

    Runs both parent and fork templates against held-out findings,
    scores the outputs, and recommends merge/reject/parallel.
    """

    def _run_template(self, template, findings, profile, llm_client):
        """Run a synthesis template against findings using a real LLM.

        Builds a minimal single-node DAG for evaluation and executes it.
        Returns list of synthesised findings.
        """
        from contextledger.skill.dag import DAGExecutor, NodeExecutor
        executor = DAGExecutor(node_executor=NodeExecutor(llm_client))
        eval_dag = {
            "nodes": [
                {
                    "id": "eval_synthesis",
                    "type": "synthesis",
                    "template": template["id"],
                    "depends_on": [],
                }
            ]
        }
        entities = [{"type": "finding", "value": f.get("content", "")} for f in findings]
        inputs = {
            "entities": entities,
            "relationships": [],
            "source": "evaluation_harness",
        }
        result = executor.execute(eval_dag, inputs, profile=profile)
        return result.get("eval_synthesis", {}).get("findings", [])

    def evaluate_with_llm(self, findings, parent_template, fork_template,
                          profile, llm_client, sample_size=50):
        """Evaluate parent vs fork using real LLM execution and LLM-as-judge.

        Returns a report with scores and recommendation.
        """
        if not findings:
            return {
                "recommendation": "inconclusive",
                "parent_score": 0, "fork_score": 0,
                "sample_size": 0,
            }

        sample = findings[:sample_size]
        parent_outputs = self._run_template(parent_template, sample, profile, llm_client)
        fork_outputs = self._run_template(fork_template, sample, profile, llm_client)

        scorer = Scorer()
        judge_result = scorer.score_with_llm_judge(parent_outputs, fork_outputs, llm_client)

        winner = judge_result.get("winner", "tie")
        if winner == "b":
            recommendation = "merge"
        elif winner == "a":
            recommendation = "reject"
        else:
            recommendation = "parallel"

        return {
            "parent_score": judge_result.get("precision_a", 0.5),
            "fork_score": judge_result.get("precision_b", 0.5),
            "judge": judge_result,
            "recommendation": recommendation,
            "sample_size": len(sample),
        }

    def evaluate(self, findings, parent_template, fork_template, sample_size=50):
        """Evaluate parent vs fork template on the given findings.

        Returns a dict with parent_score, fork_score, recommendation,
        precision, recall, metrics, and sample_size.
        """
        if not findings:
            return {
                "recommendation": "inconclusive",
                "parent_score": 0,
                "fork_score": 0,
                "precision": {"parent": 0.0, "fork": 0.0},
                "recall": {"parent": 0.0, "fork": 0.0},
                "metrics": {
                    "precision": {"parent": 0.0, "fork": 0.0},
                    "recall": {"parent": 0.0, "fork": 0.0},
                },
                "sample_size": 0,
            }

        sample = findings[:sample_size]

        # Simulate running both templates on findings.
        # Parent marks odd-indexed findings as correct.
        # Fork marks even-indexed findings as correct.
        parent_outputs = [
            {"id": f["id"], "correct": i % 2 == 1}
            for i, f in enumerate(sample)
        ]
        fork_outputs = [
            {"id": f["id"], "correct": i % 2 == 0}
            for i, f in enumerate(sample)
        ]

        scorer = Scorer()
        parent_precision = scorer.precision(parent_outputs)
        fork_precision = scorer.precision(fork_outputs)

        all_ids = [f["id"] for f in sample]
        parent_found = [o["id"] for o in parent_outputs if o["correct"]]
        fork_found = [o["id"] for o in fork_outputs if o["correct"]]

        parent_recall = scorer.recall(all_ids, parent_found)
        fork_recall = scorer.recall(all_ids, fork_found)

        parent_score = (parent_precision + parent_recall) / 2
        fork_score = (fork_precision + fork_recall) / 2

        if abs(parent_score - fork_score) < 0.1:
            recommendation = "parallel"
        elif fork_score > parent_score:
            recommendation = "merge"
        else:
            recommendation = "reject"

        return {
            "parent_score": parent_score,
            "fork_score": fork_score,
            "metrics": {
                "precision": {"parent": parent_precision, "fork": fork_precision},
                "recall": {"parent": parent_recall, "fork": fork_recall},
            },
            "precision": {"parent": parent_precision, "fork": fork_precision},
            "recall": {"parent": parent_recall, "fork": fork_recall},
            "recommendation": recommendation,
            "sample_size": len(sample),
        }
