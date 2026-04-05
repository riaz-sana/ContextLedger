"""Core data types for ContextLedger.

Define here:
- MemoryUnit
- SkillBundle
- ProfileMetadata
- ProfileDiff
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


@dataclass
class MemoryUnit:
    """Atomic unit of stored context."""

    id: str
    content: str
    unit_type: str
    profile_name: str
    embedding: List[float] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    parent_id: Optional[str] = None
    metadata: Dict = field(default_factory=dict)


@dataclass
class SkillBundle:
    """A complete skill directory bundle."""

    name: str
    version: str
    profile_yaml: str
    parent: Optional[str] = None
    tools: List[str] = field(default_factory=list)
    refs: List[str] = field(default_factory=list)


@dataclass
class ProfileMetadata:
    """Lightweight index entry for a skill profile."""

    name: str
    version: str
    parent: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ProfileDiff:
    """Semantic diff between two profiles."""

    profile_a: str
    profile_b: str
    changed_sections: List[str] = field(default_factory=list)
    added_sections: List[str] = field(default_factory=list)
    removed_sections: List[str] = field(default_factory=list)
    conflict_tiers: Dict = field(default_factory=dict)
