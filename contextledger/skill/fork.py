"""Fork and inheritance chain resolution.

Implements copy-on-write fork semantics where child profiles
inherit from parent and only store overrides.

Supports three-layer composition (GAP 3):
  core → backend adapter → domain config

And section-level inheritance (GAP 1):
  composition.base + composition.overrides
"""

from __future__ import annotations

from typing import Any


class ForkManager:
    """Manages fork creation and inheritance resolution for skill profiles."""

    def fork(
        self,
        parent: dict,
        new_name: str,
        *,
        backend: str | None = None,
        domain_config: dict | None = None,
    ) -> dict:
        """Create a child profile dict from a parent profile.

        The child references the parent by name and inherits tools/refs
        by reference (no copying). Only overrides are stored on the child.
        The child's profile_yaml is updated with the new name and parent.

        Parameters
        ----------
        backend:
            Optional backend adapter name to set in the composition layer.
        domain_config:
            Optional domain-specific config overrides.
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
        else:
            parsed = {
                "name": new_name,
                "version": f"{parent_version}-fork-1",
                "parent": parent_name,
            }

        # GAP 3: three-layer composition support
        if backend or domain_config:
            comp = parsed.get("composition", {})
            comp["base"] = f"{parent_name}:{parent_version}"
            if backend:
                backends = parsed.get("backends", {})
                backends["storage"] = backend
                parsed["backends"] = backends
            if domain_config:
                overrides = comp.get("overrides", {})
                overrides.update(domain_config)
                comp["overrides"] = overrides
            parsed["composition"] = comp

        fork_yaml = yaml.dump(parsed, default_flow_style=False, sort_keys=False)

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

        Supports both legacy ``parent:`` inheritance and the newer
        ``composition:`` block (GAP 1/3).  When ``composition.base``
        is present, it is used as the parent reference (with optional
        version pinning).  Section-level overrides from
        ``composition.overrides`` are applied after the parent merge.

        Parameters
        ----------
        profile:
            The profile dict to resolve. May contain a ``parent`` key
            referencing another profile by name, or a ``composition``
            block with ``base`` and ``overrides``.
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

        # Determine parent: composition.base takes precedence over parent field
        composition = profile.get("composition", {})
        parent_ref = composition.get("base") or profile.get("parent")

        # Strip version pin from composition base (e.g. "core:1.2" -> "core")
        parent_name = None
        pinned_version = None
        if parent_ref:
            parts = parent_ref.split(":", 1)
            parent_name = parts[0]
            if len(parts) > 1:
                pinned_version = parts[1]

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

        # Warn if version pin doesn't match registry version
        if pinned_version:
            import warnings
            registry_version = parent_profile.get("version", "")
            if registry_version and not registry_version.startswith(pinned_version):
                warnings.warn(
                    f"composition.base pins '{parent_name}:{pinned_version}' "
                    f"but registry has v{registry_version}",
                    stacklevel=2,
                )

        resolved_parent = self.resolve(parent_profile, registry, _visited)

        # Deep-merge: parent provides base, child overrides.
        result = _deep_merge(resolved_parent, profile)

        # GAP 1: Apply section-level overrides from composition block
        section_overrides = composition.get("overrides", {})
        for section, override_val in section_overrides.items():
            # Section overrides *replace* the section entirely (not deep-merge)
            result[section] = override_val

        return result


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
