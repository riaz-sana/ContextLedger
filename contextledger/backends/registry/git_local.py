"""Git (local) RegistryBackend implementation.

Uses subprocess for local repository-based skill registry.
"""

import os
import subprocess
from typing import Any, Dict, List, Optional

import yaml

from contextledger.core.types import ProfileDiff


class GitLocalRegistryBackend:
    """RegistryBackend backed by a local git repository.

    Skills are stored as directory bundles under ``skills/<name>/profile.yaml``.
    Each save_profile call creates a git commit, providing built-in versioning.
    """

    def __init__(self, repo_path: str):
        self._repo_path = repo_path
        self._skills_dir = os.path.join(repo_path, "skills")
        os.makedirs(self._skills_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git"] + list(args),
            cwd=self._repo_path,
            capture_output=True,
            text=True,
        )

    def _skill_dir(self, name: str) -> str:
        return os.path.join(self._skills_dir, name)

    def _profile_path(self, name: str) -> str:
        return os.path.join(self._skill_dir(name), "profile.yaml")

    # ------------------------------------------------------------------
    # Protocol methods
    # ------------------------------------------------------------------

    def save_profile(self, bundle: dict) -> str:
        name = bundle["name"]
        version = bundle.get("version", "0.0.0")
        profile_yaml = bundle.get("profile_yaml", "")

        skill_dir = self._skill_dir(name)
        os.makedirs(skill_dir, exist_ok=True)

        profile_path = self._profile_path(name)
        with open(profile_path, "w", encoding="utf-8") as f:
            f.write(profile_yaml)

        # Write a version marker so git always detects a change even if
        # the profile_yaml content is identical across versions.
        version_file = os.path.join(skill_dir, ".version")
        with open(version_file, "w", encoding="utf-8") as f:
            f.write(version)

        rel_dir = os.path.relpath(skill_dir, self._repo_path)
        self._git("add", rel_dir)
        self._git("commit", "-m", f"Save {name} v{version}")

        return version

    def get_profile(self, name: str, version: Optional[str] = None) -> Optional[dict]:
        profile_path = self._profile_path(name)
        if not os.path.exists(profile_path):
            return None

        with open(profile_path, "r", encoding="utf-8") as f:
            content = f.read()

        try:
            parsed = yaml.safe_load(content) or {}
        except yaml.YAMLError:
            parsed = {}

        return {
            "name": name,
            "version": parsed.get("version", "0.0.0"),
            "profile_yaml": content,
            "parent": parsed.get("parent"),
        }

    def fork_profile(self, parent_name: str, new_name: str) -> dict:
        parent = self.get_profile(parent_name)
        if parent is None:
            raise ValueError(f"Parent profile '{parent_name}' not found")

        parent_yaml = parent["profile_yaml"]

        # Parse, update name and parent, then re-serialize
        try:
            parsed = yaml.safe_load(parent_yaml) or {}
        except yaml.YAMLError:
            parsed = {}

        parsed["name"] = new_name
        parsed["parent"] = parent_name

        new_yaml = yaml.dump(parsed, default_flow_style=False, sort_keys=False)

        new_bundle = {
            "name": new_name,
            "version": parsed.get("version", "1.0.0"),
            "profile_yaml": new_yaml,
        }
        self.save_profile(new_bundle)

        return {
            "name": new_name,
            "version": parsed.get("version", "1.0.0"),
            "profile_yaml": new_yaml,
            "parent": parent_name,
        }

    def list_profiles(self, filter: Optional[dict] = None) -> list:
        if not os.path.isdir(self._skills_dir):
            return []

        profiles = []
        for entry in os.listdir(self._skills_dir):
            skill_dir = os.path.join(self._skills_dir, entry)
            if os.path.isdir(skill_dir):
                profile = self.get_profile(entry)
                if profile is not None:
                    profiles.append(profile)
        return profiles

    def list_versions(self, name: str) -> List[str]:
        rel_dir = os.path.join("skills", name)
        result = self._git("log", "--format=%s", "--", rel_dir)
        versions: List[str] = []
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                # Commit messages are like "Save <name> v<version>"
                if line.startswith("Save ") and " v" in line:
                    ver = line.split(" v", 1)[-1]
                    if ver and ver not in versions:
                        versions.append(ver)
        return versions

    def get_diff(self, name_a: str, name_b: str) -> ProfileDiff:
        profile_a = self.get_profile(name_a)
        profile_b = self.get_profile(name_b)

        yaml_a = profile_a["profile_yaml"] if profile_a else ""
        yaml_b = profile_b["profile_yaml"] if profile_b else ""

        try:
            parsed_a = yaml.safe_load(yaml_a) or {}
        except yaml.YAMLError:
            parsed_a = {}
        try:
            parsed_b = yaml.safe_load(yaml_b) or {}
        except yaml.YAMLError:
            parsed_b = {}

        keys_a = set(parsed_a.keys())
        keys_b = set(parsed_b.keys())

        added = list(keys_b - keys_a)
        removed = list(keys_a - keys_b)
        changed = [
            k for k in keys_a & keys_b
            if parsed_a[k] != parsed_b[k]
        ]

        return ProfileDiff(
            profile_a=name_a,
            profile_b=name_b,
            changed_sections=changed,
            added_sections=added,
            removed_sections=removed,
        )
