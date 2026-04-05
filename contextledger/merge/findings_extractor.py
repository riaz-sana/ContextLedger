"""FindingsExtractor — privacy gate between synthesis pipeline and findings.db.

Transforms DAG synthesis outputs into privacy-safe Finding objects.
Enforces: no raw session content, no user messages, no personal identifiers.
"""

import uuid
from datetime import datetime, timezone
from typing import List


_FORBIDDEN_FIELDS = {
    "raw_content", "user_message", "session_log", "messages",
    "conversation", "prompt", "user_input", "personal_data",
}


class FindingsExtractor:
    """Extracts structured, privacy-safe findings from DAG synthesis outputs."""

    def __init__(self, embedding_backend, findings_backend):
        self._embedding = embedding_backend
        self._findings = findings_backend

    def extract_and_store(
        self,
        synthesis_outputs: dict,
        skill_profile: str,
        skill_version: str,
        domain: str,
        min_confidence: float = 0.5,
    ) -> List[dict]:
        """Extract findings from synthesis outputs and write to findings.db.

        Returns list of Finding dicts that were stored.
        """
        stored = []
        raw_findings = self._collect_findings(synthesis_outputs)

        for raw in raw_findings:
            if raw.get("confidence", 0.0) < min_confidence:
                continue

            self._check_privacy(raw)

            summary = raw.get("content") or raw.get("summary") or raw.get("finding", "")
            if not summary:
                continue

            finding = {
                "id": str(uuid.uuid4()),
                "skill_profile": skill_profile,
                "skill_version": skill_version,
                "finding_type": raw.get("type", "general"),
                "summary": summary,
                "confidence": raw.get("confidence", 0.7),
                "domain": domain,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "evaluation_eligible": True,
                "embedding": self._embedding.encode(summary),
                "tags": raw.get("tags", []),
                "metadata": {
                    k: v for k, v in raw.items()
                    if k not in _FORBIDDEN_FIELDS
                    and k not in {"content", "summary", "finding", "type", "confidence", "tags"}
                },
            }

            self._findings.write_finding(finding)
            stored.append(finding)

        return stored

    def _collect_findings(self, synthesis_outputs: dict) -> List[dict]:
        """Pull findings from all synthesis and filter node outputs."""
        findings = []
        for node_id, output in synthesis_outputs.items():
            if isinstance(output, dict):
                if "findings" in output:
                    findings.extend(output["findings"])
                elif "filtered_findings" in output:
                    findings.extend(output["filtered_findings"])
        return findings

    def _check_privacy(self, finding: dict):
        """Raise if finding contains forbidden fields."""
        violations = set(finding.keys()) & _FORBIDDEN_FIELDS
        if violations:
            raise ValueError(
                f"Finding contains forbidden fields: {violations}. "
                f"These fields cannot be stored in findings.db."
            )
