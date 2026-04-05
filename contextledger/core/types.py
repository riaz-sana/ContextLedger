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


class RoutingStrategy:
    """How a query is routed to a skill."""
    DIRECTORY = "directory"
    KEYWORD = "keyword"
    FILE_PATTERN = "file_pattern"
    EXPLICIT = "explicit"
    ALL = "all"


@dataclass
class SkillRoute:
    """Maps a condition to a skill profile."""
    skill_name: str
    directories: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    file_patterns: List[str] = field(default_factory=list)
    priority: int = 0


@dataclass
class ProjectManifest:
    """Top-level project configuration for multi-skill projects."""
    name: str
    version: str = "1.0.0"
    description: str = ""
    skills: List[str] = field(default_factory=list)
    routes: List[SkillRoute] = field(default_factory=list)
    default_skill: Optional[str] = None
    fusion_enabled: bool = True
    project_root: str = ""


@dataclass
class MultiSkillQueryResult:
    """Result from a cross-skill query."""
    query: str
    results_by_skill: Dict[str, List] = field(default_factory=dict)
    fused_results: List = field(default_factory=list)
    active_skill: Optional[str] = None
    routing_reason: str = ""


@dataclass
class ProfileDiff:
    """Semantic diff between two profiles."""

    profile_a: str
    profile_b: str
    changed_sections: List[str] = field(default_factory=list)
    added_sections: List[str] = field(default_factory=list)
    removed_sections: List[str] = field(default_factory=list)
    conflict_tiers: Dict = field(default_factory=dict)
