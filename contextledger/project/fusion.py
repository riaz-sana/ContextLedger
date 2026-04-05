"""Context fusion — merges and deduplicates results from multiple skill queries."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from contextledger.core.types import MultiSkillQueryResult


class ContextFuser:
    """Fuses memory query results from multiple skills.

    Strategy:
    1. Deduplicate by content (first 200 chars as proxy key)
    2. Rank by relevance to active skill, then recency
    3. Tag each result with source skill(s)
    4. Preserve skill attribution for transparency
    """

    def fuse(
        self,
        query: str,
        results_by_skill: Dict[str, List],
        active_skill: Optional[str] = None,
        routing_reason: str = "",
    ) -> MultiSkillQueryResult:
        """Merge results from multiple skills into a single ranked list."""
        seen_content: Dict[str, Tuple[dict, List[str]]] = {}

        for skill_name, units in results_by_skill.items():
            for unit in units:
                content_key = self._content_key(unit)
                if content_key in seen_content:
                    seen_content[content_key][1].append(skill_name)
                else:
                    seen_content[content_key] = (unit, [skill_name])

        fused = []
        for content_key, (unit, skill_names) in seen_content.items():
            fused_unit = self._annotate(unit, skill_names)
            fused.append(fused_unit)

        fused.sort(key=lambda u: self._sort_key(u, active_skill), reverse=True)

        return MultiSkillQueryResult(
            query=query,
            results_by_skill=results_by_skill,
            fused_results=fused,
            active_skill=active_skill,
            routing_reason=routing_reason,
        )

    def _content_key(self, unit) -> str:
        """Stable key for deduplication."""
        if isinstance(unit, dict):
            return unit.get("content", "")[:200]
        return getattr(unit, "content", "")[:200]

    def _annotate(self, unit, skill_names: List[str]):
        """Add skill attribution to a unit's metadata."""
        if isinstance(unit, dict):
            annotated = dict(unit)
            meta = dict(annotated.get("metadata", {}))
            meta["source_skills"] = skill_names
            meta["cross_skill"] = len(skill_names) > 1
            annotated["metadata"] = meta
            return annotated
        # MemoryUnit dataclass
        from contextledger.core.types import MemoryUnit
        return MemoryUnit(
            id=unit.id,
            content=unit.content,
            unit_type=unit.unit_type,
            profile_name=unit.profile_name,
            timestamp=unit.timestamp,
            metadata={
                **(unit.metadata or {}),
                "source_skills": skill_names,
                "cross_skill": len(skill_names) > 1,
            },
            embedding=unit.embedding,
            tags=unit.tags,
            parent_id=unit.parent_id,
        )

    def _sort_key(self, unit, active_skill: Optional[str]) -> Tuple:
        """Sort: active skill first, then by content length as proxy for relevance."""
        if isinstance(unit, dict):
            meta = unit.get("metadata", {})
            content = unit.get("content", "")
        else:
            meta = getattr(unit, "metadata", {}) or {}
            content = getattr(unit, "content", "")

        is_active = (
            active_skill is not None
            and active_skill in meta.get("source_skills", [])
        )
        return (int(is_active), len(content))
