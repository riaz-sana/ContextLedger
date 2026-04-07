"""Dependency checking for skill profiles (GAP 4).

Validates that declared ``requires:`` blocks are satisfied
by the versions available in the registry.
"""

from __future__ import annotations

import re
from typing import Any


def check_dependencies(registry: dict[str, dict]) -> list[str]:
    """Check all profiles in *registry* for unsatisfied dependencies.

    Parameters
    ----------
    registry:
        Mapping of ``{profile_name: parsed_profile_dict}``.

    Returns
    -------
    list[str]
        Human-readable issue strings.  Empty list means all deps satisfied.
    """
    issues: list[str] = []

    for name, profile in registry.items():
        requires = profile.get("requires")
        if not requires:
            continue

        for dep_name, version_spec in requires.items():
            if dep_name not in registry:
                issues.append(
                    f"{name}: requires '{dep_name}' but it is not in the registry"
                )
                continue

            dep_version = registry[dep_name].get("version", "0.0.0")
            if not _version_satisfies(dep_version, version_spec):
                issues.append(
                    f"{name}: requires '{dep_name} {version_spec}' "
                    f"but registry has v{dep_version}"
                )

    return issues


def _version_satisfies(version: str, spec: str) -> bool:
    """Check if *version* satisfies a simple version spec.

    Supports:
    - Exact: ``"1.2.0"``
    - Range: ``">=1.2,<2.0"``
    - Minimum: ``">=1.2"``
    - Compatible: ``"^1.2"`` (>=1.2.0, <2.0.0)
    """
    if not spec or not version:
        return True

    # Normalise version to tuple
    ver = _parse_version(version)

    # Split on comma for compound specs
    parts = [s.strip() for s in spec.split(",")]
    for part in parts:
        if not _check_single(ver, part):
            return False
    return True


def _parse_version(v: str) -> tuple[int, ...]:
    """Parse ``"1.2.3"`` into ``(1, 2, 3)``.  Non-numeric suffixes are stripped."""
    # Strip common suffixes like -fork-1, -beta, etc.
    clean = re.split(r"[-+]", v)[0]
    parts = []
    for p in clean.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            break
    return tuple(parts) if parts else (0,)


def _check_single(ver: tuple[int, ...], spec: str) -> bool:
    """Check one constraint like ``>=1.2`` or ``<2.0``."""
    spec = spec.strip()
    if not spec:
        return True

    # Caret notation: ^1.2 means >=1.2.0, <2.0.0
    if spec.startswith("^"):
        base = _parse_version(spec[1:])
        upper = (base[0] + 1,)
        return ver >= base and ver < upper

    # Comparison operators
    for op in (">=", "<=", "!=", ">", "<", "="):
        if spec.startswith(op):
            target = _parse_version(spec[len(op):])
            if op == ">=":
                return ver >= target
            if op == "<=":
                return ver <= target
            if op == ">":
                return ver > target
            if op == "<":
                return ver < target
            if op == "!=":
                return ver != target
            if op == "=":
                return ver == target

    # Plain version string — exact match
    return ver == _parse_version(spec)
