"""Skill router — determines which skill profile to use given context signals."""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import List, Optional, Tuple

from contextledger.core.types import ProjectManifest


class SkillRouter:
    """Routes queries and operations to the appropriate skill profile.

    Routing priority (highest to lowest):
    1. Explicit --profile flag (handled in CLI, not here)
    2. Directory match (most specific path wins)
    3. File pattern match
    4. Keyword match (query content)
    5. Default skill
    6. First declared skill
    """

    def route_by_directory(
        self, manifest: ProjectManifest, current_dir: str
    ) -> Tuple[Optional[str], str]:
        """Route based on current working directory."""
        current = Path(current_dir).resolve()
        project_root = Path(manifest.project_root).resolve()

        best_match = None
        best_depth = -1
        best_priority = -1

        for route in manifest.routes:
            if not route.directories:
                continue
            for dir_pattern in route.directories:
                target = (project_root / dir_pattern).resolve()
                try:
                    current.relative_to(target)
                    depth = len(target.parts)
                    if depth > best_depth or (
                        depth == best_depth and route.priority > best_priority
                    ):
                        best_match = route.skill_name
                        best_depth = depth
                        best_priority = route.priority
                except ValueError:
                    continue

        if best_match:
            return best_match, f"directory match: working in {current_dir}"
        return None, "no directory match"

    def route_by_keywords(
        self, manifest: ProjectManifest, query: str
    ) -> Tuple[Optional[str], str]:
        """Route based on keywords found in query text."""
        query_lower = query.lower()
        matches = []

        for route in manifest.routes:
            if not route.keywords:
                continue
            matched_kws = [kw for kw in route.keywords if kw.lower() in query_lower]
            if matched_kws:
                matches.append((route, len(matched_kws), matched_kws))

        if not matches:
            return None, "no keyword match"

        matches.sort(key=lambda x: (x[1], x[0].priority), reverse=True)
        best_route, _, matched_kws = matches[0]
        return best_route.skill_name, f"keyword match: {', '.join(matched_kws)}"

    def route_by_file_pattern(
        self, manifest: ProjectManifest, file_path: str
    ) -> Tuple[Optional[str], str]:
        """Route based on a file path."""
        for route in sorted(manifest.routes, key=lambda r: r.priority, reverse=True):
            for pattern in route.file_patterns:
                if fnmatch.fnmatch(file_path, pattern):
                    return route.skill_name, f"file pattern match: {pattern}"
        return None, "no file pattern match"

    def route(
        self,
        manifest: ProjectManifest,
        query: Optional[str] = None,
        current_dir: Optional[str] = None,
        file_path: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Full routing with fallback chain. Always returns a skill."""
        if current_dir:
            skill, reason = self.route_by_directory(manifest, current_dir)
            if skill:
                return skill, reason

        if file_path:
            skill, reason = self.route_by_file_pattern(manifest, file_path)
            if skill:
                return skill, reason

        if query:
            skill, reason = self.route_by_keywords(manifest, query)
            if skill:
                return skill, reason

        if manifest.default_skill:
            return manifest.default_skill, "default skill"

        if manifest.skills:
            return manifest.skills[0], "first declared skill (no route matched)"

        raise ValueError(f"Project '{manifest.name}' has no skills declared")

    def route_all(self, manifest: ProjectManifest) -> List[str]:
        """Return all skills in the project (for cross-skill queries)."""
        return list(manifest.skills)
