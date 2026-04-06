"""Interactive profile generation wizard.

Guides users through creating a new skill profile
via CLI prompts.
"""

from datetime import datetime, timezone
from typing import Optional

try:
    import yaml

    def _dump_yaml(data: dict) -> str:
        return yaml.dump(data, default_flow_style=False, sort_keys=False)

except ImportError:
    # Fallback: produce YAML manually for simple flat/nested dicts
    def _dump_yaml(data: dict, indent: int = 0) -> str:  # type: ignore[misc]
        lines: list[str] = []
        prefix = "  " * indent
        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"{prefix}{key}:")
                lines.append(_dump_yaml(value, indent + 1))
            elif isinstance(value, list):
                lines.append(f"{prefix}{key}:")
                for item in value:
                    lines.append(f"{prefix}- {item}")
            elif value is None:
                lines.append(f"{prefix}{key}: null")
            elif isinstance(value, bool):
                lines.append(f"{prefix}{key}: {'true' if value else 'false'}")
            else:
                lines.append(f"{prefix}{key}: {value}")
        return "\n".join(lines)


def _prompt(text: str, default: Optional[str] = None) -> str:
    """Prompt the user for input, using click if available, else builtin input()."""
    try:
        import click

        return click.prompt(text, default=default)
    except ImportError:
        if default is not None:
            raw = input(f"{text} [{default}]: ").strip()
            return raw if raw else default
        return input(f"{text}: ").strip()


_DATA_SOURCE_CHOICES = ["filesystem", "database", "API", "documents"]


class ProfileWizard:
    """Interactive wizard for creating and forking skill profiles."""

    def run(self) -> str:
        """Run the interactive wizard and return a valid profile.yaml string.

        Prompts the user for:
        - Data source (filesystem / database / API / documents)
        - Entity types to extract (comma-separated)
        - Domain (e.g. security research, data analysis)
        - Profile name

        Returns:
            A YAML-formatted string suitable for writing to profile.yaml.
        """
        print("=== ContextLedger Profile Wizard ===\n")

        # --- Data source ---
        choices_display = " / ".join(_DATA_SOURCE_CHOICES)
        data_source = _prompt(
            f"Data source ({choices_display})", default="filesystem"
        )
        # Normalise to a known value when possible
        data_source_lower = data_source.strip().lower()
        matched = [c for c in _DATA_SOURCE_CHOICES if c.lower() == data_source_lower]
        data_source = matched[0] if matched else data_source.strip()

        # --- Entity types ---
        entity_input = _prompt(
            "Entity types to extract (comma-separated)", default="concept,tool,decision"
        )
        entity_types = [e.strip() for e in entity_input.split(",") if e.strip()]

        # --- Domain ---
        domain = _prompt("Domain", default="general")

        # --- Profile name ---
        profile_name = _prompt("Profile name", default="my-profile")

        # Build the profile data structure
        now = datetime.now(timezone.utc).isoformat()
        profile_data = {
            "name": profile_name,
            "version": "0.1.0",
            "parent": None,
            "domain": domain,
            "extraction": {
                "entities": entity_types,
                "sources": [data_source],
                "rules": [],
            },
            "synthesis": {
                "dag": {
                    "nodes": [
                        {"id": "extract_entities", "type": "extraction", "depends_on": []},
                        {"id": "build_relationships", "type": "reasoning", "depends_on": ["extract_entities"]},
                        {"id": "synthesise_findings", "type": "synthesis", "depends_on": ["build_relationships"]},
                    ]
                }
            },
            "session_context": {
                "mode": "skill_versioning",
                "cmv_enabled": True,
                "trim_threshold": 0.3,
                "memory_tiers": {
                    "immediate_turns": 10,
                    "synthesis_window_days": 7,
                    "archival": True,
                },
            },
            "created_at": now,
            "updated_at": now,
        }

        yaml_str = _dump_yaml(profile_data)
        print(f"\nGenerated profile.yaml for '{profile_name}'.\n")
        return yaml_str

    def from_fork(self, parent_name: str, new_name: str) -> str:
        """Generate a minimal fork profile.yaml with parent reference.

        Args:
            parent_name: Name of the parent profile being forked.
            new_name: Name for the new forked profile.

        Returns:
            A YAML-formatted string for the forked profile.
        """
        now = datetime.now(timezone.utc).isoformat()
        fork_data = {
            "name": new_name,
            "version": "0.1.0",
            "parent": parent_name,
            "created_at": now,
            "updated_at": now,
        }

        return _dump_yaml(fork_data)
