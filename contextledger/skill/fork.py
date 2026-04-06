"""Fork and inheritance chain resolution.

Implements copy-on-write fork semantics where child profiles
inherit from parent and only store overrides.
"""

from __future__ import annotations

from typing import Any


class ForkManager:
    """Manages fork creation and inheritance resolution for skill profiles."""

    def fork(self, parent: dict, new_name: str) -> dict:
        """Create a child profile dict from a parent profile.

        The child references the parent by name and inherits tools/refs
        by reference (no copying). Only overrides are stored on the child.
        The child's profile_yaml is updated with the new name and parent.
        """
        import yaml

        parent_version = parent.get("version", "0.0.0")
        parent_name = parent["name"]

        # Re-serialize YAML with updated name and parent
        raw_yaml = parent.get("profile_yaml", "")
        if raw_yaml:
            try:
                parsed = yaml.safe_load(raw_yaml) or {}
            except yaml.YAMLError:
                parsed = {}
            parsed["name"] = new_name
            parsed["parent"] = parent_name
            parsed["version"] = f"{parent_version}-fork-1"
            fork_yaml = yaml.dump(parsed, default_flow_style=False, sort_keys=False)
        else:
            fork_yaml = yaml.dump({
                "name": new_name,
                "version": f"{parent_version}-fork-1",
                "parent": parent_name,
            }, default_flow_style=False, sort_keys=False)

        return {
            "name": new_name,
            "parent": parent_name,
            "version": f"{parent_version}-fork-1",
            "profile_yaml": fork_yaml,
            "tools": [],
            "refs": [],
            "inherited_tools": parent.get("tools", []),
            "inherited_refs": parent.get("refs", []),
        }

    def resolve(self, profile: dict, registry: dict, _visited: set | None = None) -> dict:
        """Walk the parent chain and return a fully resolved profile.

        Parameters
        ----------
        profile:
            The profile dict to resolve. May contain a ``parent`` key
            referencing another profile by name.
        registry:
            Mapping of ``{profile_name: profile_dict}`` used for
            parent lookups.

        Returns
        -------
        dict
            A new dict with all inherited values merged in.
            Child values take precedence over parent values.

        Raises
        ------
        KeyError / ValueError
            If a referenced parent is not found in the registry,
            or if a cycle is detected in the parent chain.
        """
        if _visited is None:
            _visited = set()

        profile_name = profile.get("name", "")
        if profile_name in _visited:
            raise ValueError(f"Cycle detected in parent chain: '{profile_name}'")
        _visited.add(profile_name)

        parent_name = profile.get("parent")

        # Base case: no parent — parse profile_yaml if present, then return.
        if parent_name is None:
            if "profile_yaml" in profile and profile["profile_yaml"]:
                from contextledger.skill.parser import ProfileParser
                parsed = ProfileParser().parse(profile["profile_yaml"])
                # Overlay any explicit keys from the profile dict onto parsed
                merged = dict(parsed)
                for key, value in profile.items():
                    if key == "profile_yaml":
                        continue
                    merged[key] = value
                return merged
            return dict(profile)

        # Look up parent in registry.
        if parent_name not in registry:
            raise KeyError(
                f"Parent profile '{parent_name}' not found in registry"
            )

        parent_profile = registry[parent_name]
        resolved_parent = self.resolve(parent_profile, registry, _visited)

        # Deep-merge: parent provides base, child overrides.
        return _deep_merge(resolved_parent, profile)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge *override* onto *base*.

    - For nested dicts: merge recursively.
    - For lists and all other values: override replaces base entirely.
    - Keys only in base are preserved; keys only in override are added.
    """
    result = dict(base)
    for key, value in override.items():
        if key == "parent":
            # Keep the child's parent reference as-is.
            result[key] = value
            continue
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
