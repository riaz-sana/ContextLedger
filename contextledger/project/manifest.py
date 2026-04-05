"""Project manifest — loads, validates, and resolves project.yaml."""

import os
from pathlib import Path
from typing import Optional

import yaml

from contextledger.core.types import ProjectManifest, SkillRoute

MANIFEST_FILENAME = "project.yaml"
MANIFEST_DIR = ".contextledger"


class ManifestParser:
    """Parses and validates project.yaml."""

    def parse(self, yaml_str: str) -> ProjectManifest:
        """Parse YAML string into ProjectManifest."""
        data = yaml.safe_load(yaml_str) or {}
        self._validate(data)
        return self._build(data)

    def parse_file(self, path: str) -> ProjectManifest:
        """Load and parse a project.yaml file."""
        with open(path) as f:
            manifest = self.parse(f.read())
        manifest.project_root = str(Path(path).parent.parent)
        return manifest

    def _validate(self, data: dict):
        if "name" not in data:
            raise ValueError("project.yaml must have a 'name' field")
        if "skills" not in data or not data["skills"]:
            raise ValueError("project.yaml must declare at least one skill")
        for route in data.get("routes", []):
            if "skill" not in route:
                raise ValueError(f"Route missing 'skill' field: {route}")
            if not any(k in route for k in ["directories", "keywords", "file_patterns"]):
                raise ValueError(f"Route must have at least one condition: {route}")

    def _build(self, data: dict) -> ProjectManifest:
        routes = []
        for r in data.get("routes", []):
            routes.append(SkillRoute(
                skill_name=r["skill"],
                directories=r.get("directories", []),
                keywords=r.get("keywords", []),
                file_patterns=r.get("file_patterns", []),
                priority=r.get("priority", 0),
            ))
        return ProjectManifest(
            name=data["name"],
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            skills=data["skills"],
            routes=routes,
            default_skill=data.get("default_skill"),
            fusion_enabled=data.get("fusion_enabled", True),
        )

    def to_yaml(self, manifest: ProjectManifest) -> str:
        """Serialize a ProjectManifest back to YAML."""
        data = {
            "name": manifest.name,
            "version": manifest.version,
            "skills": manifest.skills,
            "default_skill": manifest.default_skill,
            "fusion_enabled": manifest.fusion_enabled,
            "routes": [
                {
                    "skill": r.skill_name,
                    **({"directories": r.directories} if r.directories else {}),
                    **({"keywords": r.keywords} if r.keywords else {}),
                    **({"file_patterns": r.file_patterns} if r.file_patterns else {}),
                    **({"priority": r.priority} if r.priority else {}),
                }
                for r in manifest.routes
            ],
        }
        return yaml.dump(data, default_flow_style=False, sort_keys=False)


class ManifestLocator:
    """Finds project.yaml by walking up the directory tree."""

    def find(self, start_path: str = ".") -> Optional[str]:
        """Walk up from start_path looking for .contextledger/project.yaml.

        Returns full path to project.yaml, or None if not found.
        """
        current = Path(start_path).resolve()
        while True:
            candidate = current / MANIFEST_DIR / MANIFEST_FILENAME
            if candidate.exists():
                return str(candidate)
            parent = current.parent
            if parent == current:
                return None
            current = parent
