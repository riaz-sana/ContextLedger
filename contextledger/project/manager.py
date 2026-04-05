"""Project manager — top-level orchestrator for multi-skill projects."""

from __future__ import annotations

import os
from typing import Optional

from contextledger.core.types import MultiSkillQueryResult, ProjectManifest
from contextledger.project.manifest import ManifestParser, ManifestLocator
from contextledger.project.router import SkillRouter
from contextledger.project.fusion import ContextFuser


class ProjectManager:
    """Manages a multi-skill project.

    Loads manifest, routes operations to correct skill, fuses results.
    """

    def __init__(self, registry_backend=None, memory_system=None):
        self.registry = registry_backend
        self.memory = memory_system
        self.parser = ManifestParser()
        self.locator = ManifestLocator()
        self.router = SkillRouter()
        self.fuser = ContextFuser()
        self._manifest: Optional[ProjectManifest] = None

    def load(self, project_root: Optional[str] = None) -> ProjectManifest:
        """Load project.yaml from project_root or by walking up from cwd."""
        if project_root:
            path = os.path.join(project_root, ".contextledger", "project.yaml")
        else:
            path = self.locator.find(os.getcwd())

        if not path or not os.path.exists(path):
            raise FileNotFoundError(
                "No .contextledger/project.yaml found. "
                "Run 'ctx project init' to create one."
            )

        self._manifest = self.parser.parse_file(path)
        return self._manifest

    def is_loaded(self) -> bool:
        return self._manifest is not None

    def active_manifest(self) -> ProjectManifest:
        if not self._manifest:
            raise RuntimeError("No project loaded. Call load() first.")
        return self._manifest

    def route(
        self,
        query: Optional[str] = None,
        current_dir: Optional[str] = None,
        file_path: Optional[str] = None,
        explicit_profile: Optional[str] = None,
    ) -> tuple:
        """Determine which skill to use. explicit_profile overrides all routing."""
        manifest = self.active_manifest()

        if explicit_profile:
            if explicit_profile not in manifest.skills:
                raise ValueError(
                    f"Profile '{explicit_profile}' not declared in project "
                    f"'{manifest.name}'. Declared skills: {manifest.skills}"
                )
            return explicit_profile, "explicit --profile flag"

        return self.router.route(
            manifest,
            query=query,
            current_dir=current_dir or os.getcwd(),
            file_path=file_path,
        )

    def query_all(self, query: str, limit: int = 10) -> MultiSkillQueryResult:
        """Query all skills simultaneously. Returns fused results."""
        manifest = self.active_manifest()
        primary_skill, routing_reason = self.route(query=query)

        results_by_skill: dict = {}
        for skill_name in manifest.skills:
            try:
                if self.memory:
                    results = self.memory.query(
                        query=query, profile_name=skill_name, limit=limit
                    )
                else:
                    results = []
                results_by_skill[skill_name] = results
            except Exception:
                results_by_skill[skill_name] = []

        return self.fuser.fuse(
            query=query,
            results_by_skill=results_by_skill,
            active_skill=primary_skill,
            routing_reason=routing_reason,
        )

    def query_routed(
        self,
        query: str,
        current_dir: Optional[str] = None,
        file_path: Optional[str] = None,
        explicit_profile: Optional[str] = None,
        limit: int = 10,
    ) -> MultiSkillQueryResult:
        """Query the auto-routed skill only."""
        skill_name, routing_reason = self.route(
            query=query,
            current_dir=current_dir,
            file_path=file_path,
            explicit_profile=explicit_profile,
        )

        results = []
        if self.memory:
            try:
                results = self.memory.query(
                    query=query, profile_name=skill_name, limit=limit
                )
            except Exception:
                results = []

        return MultiSkillQueryResult(
            query=query,
            results_by_skill={skill_name: results},
            fused_results=results,
            active_skill=skill_name,
            routing_reason=routing_reason,
        )
