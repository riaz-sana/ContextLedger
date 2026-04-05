"""Stub RegistryBackend for testing.

Returns mock profile data. Implements RegistryBackend protocol.
"""

from typing import Any, Dict, List, Optional

from contextledger.core.types import ProfileDiff


class StubRegistryBackend:
    """In-memory dict-backed registry backend for testing."""

    def __init__(self) -> None:
        # Keyed by (name, version) -> bundle dict
        self._profiles: Dict[tuple, dict] = {}

    def save_profile(self, bundle: dict) -> str:
        name = bundle["name"]
        version = bundle["version"]
        self._profiles[(name, version)] = dict(bundle)
        return version

    def get_profile(self, name: str, version: Optional[str] = None) -> Optional[dict]:
        if version is not None:
            return self._profiles.get((name, version))
        # Return latest (last saved) for this name
        matches = [v for k, v in self._profiles.items() if k[0] == name]
        if not matches:
            return None
        return matches[-1]

    def list_profiles(self, filter: Optional[dict] = None) -> List[Any]:
        profiles = list(self._profiles.values())
        if filter and "parent" in filter:
            profiles = [p for p in profiles if p.get("parent") == filter["parent"]]
        return profiles

    def fork_profile(self, parent_name: str, new_name: str) -> dict:
        # Find latest version of parent
        parent = self.get_profile(parent_name)
        if parent is None:
            raise ValueError(f"Parent profile '{parent_name}' not found")
        forked = dict(parent)
        forked["name"] = new_name
        forked["parent"] = parent_name
        forked["version"] = "1.0.0"
        self._profiles[(new_name, "1.0.0")] = forked
        return forked

    def list_versions(self, name: str) -> List[str]:
        return [k[1] for k in self._profiles if k[0] == name]

    def get_diff(self, name_a: str, name_b: str) -> ProfileDiff:
        return ProfileDiff(
            profile_a=name_a,
            profile_b=name_b,
            changed_sections=[],
            added_sections=[],
            removed_sections=[],
            conflict_tiers={},
        )
