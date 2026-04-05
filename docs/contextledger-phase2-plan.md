# ContextLedger Phase 2 — Project Manifest & Multi-Skill Support

**For Claude Code. Implement in order. Do not skip sections.**

---

## What Phase 2 Adds

Phase 1 supports one active skill profile at a time. Phase 2 adds:

1. **Project manifest** — a `project.yaml` that declares all skills in a project and rules for routing between them
2. **Auto-switching** — ContextLedger detects which skill is relevant based on working directory, file path, or query content
3. **Multi-skill querying** — query across all skills in a project simultaneously, with results tagged by source skill
4. **Cross-skill context fusion** — findings from one skill surface in another when relevant
5. **CLI project commands** — `ctx project init`, `ctx project status`, `ctx project query`

---

## What Does NOT Change in Phase 2

- All Phase 1 Protocol interfaces remain unchanged
- All Phase 1 backends remain unchanged
- Single-skill mode still works exactly as before
- `ctx checkout`, `ctx fork`, `ctx merge`, `ctx diff` all unchanged
- The profile YAML schema does not change

Phase 2 is purely additive. It adds a project layer on top of the existing skill layer.

---

## New Data Types

Add to `contextledger/core/types.py`:

```python
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from enum import Enum

class RoutingStrategy(Enum):
    DIRECTORY = "directory"      # route based on file path / working directory
    KEYWORD = "keyword"          # route based on query keywords
    EXPLICIT = "explicit"        # user explicitly specifies --profile
    ALL = "all"                  # query all skills simultaneously

@dataclass
class SkillRoute:
    """Maps a condition to a skill profile."""
    skill_name: str
    # At least one of these must be set:
    directories: List[str] = field(default_factory=list)   # e.g. ["sdk/", "sdk/src/"]
    keywords: List[str] = field(default_factory=list)       # e.g. ["instrumentation", "tracker"]
    file_patterns: List[str] = field(default_factory=list)  # e.g. ["*.detector.py", "detectors/"]
    # Optional: weight for ambiguous routing
    priority: int = 0  # higher = preferred when multiple routes match

@dataclass
class ProjectManifest:
    """Top-level project configuration."""
    name: str
    version: str = "1.0.0"
    description: str = ""
    # Declared skills (name must match a profile in the registry)
    skills: List[str] = field(default_factory=list)
    # Routing rules
    routes: List[SkillRoute] = field(default_factory=list)
    # Default skill when no route matches
    default_skill: Optional[str] = None
    # Cross-skill context fusion
    fusion_enabled: bool = True
    # Path to project root (set at load time, not stored in YAML)
    project_root: str = ""

@dataclass
class MultiSkillQueryResult:
    """Result from a cross-skill query."""
    query: str
    results_by_skill: Dict[str, List]   # skill_name -> list of MemoryUnits
    fused_results: List                 # merged + deduped results
    active_skill: Optional[str]         # which skill was primary (if auto-routed)
    routing_reason: str                 # why this skill was chosen
```

---

## New File: `contextledger/project/manifest.py`

This is the core of Phase 2. Implement fully before anything else.

```python
"""
Project manifest — loads, validates, and resolves project.yaml.
"""

import os
import yaml
from pathlib import Path
from typing import Optional, List, Tuple
from contextledger.core.types import ProjectManifest, SkillRoute, RoutingStrategy

MANIFEST_FILENAME = "project.yaml"
MANIFEST_DIR = ".contextledger"

class ManifestParser:
    """Parses and validates project.yaml."""

    def parse(self, yaml_str: str) -> ProjectManifest:
        """Parse YAML string into ProjectManifest."""
        data = yaml.safe_load(yaml_str)
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
        """
        Walk up from start_path looking for .contextledger/project.yaml.
        Returns full path to project.yaml, or None if not found.
        """
        current = Path(start_path).resolve()
        while True:
            candidate = current / MANIFEST_DIR / MANIFEST_FILENAME
            if candidate.exists():
                return str(candidate)
            parent = current.parent
            if parent == current:
                return None  # reached filesystem root
            current = parent
```

---

## New File: `contextledger/project/router.py`

The routing engine. Decides which skill is active based on context.

```python
"""
Skill router — determines which skill profile to use given context signals.
"""

from typing import Optional, List, Tuple
from pathlib import Path
import fnmatch

from contextledger.core.types import ProjectManifest, SkillRoute, RoutingStrategy

class SkillRouter:
    """
    Routes queries and operations to the appropriate skill profile.

    Routing priority (highest to lowest):
    1. Explicit --profile flag (handled in CLI, not here)
    2. Directory match (most specific path wins)
    3. File pattern match
    4. Keyword match (query content)
    5. Default skill
    6. First declared skill
    """

    def route_by_directory(
        self,
        manifest: ProjectManifest,
        current_dir: str,
    ) -> Tuple[Optional[str], str]:
        """
        Route based on current working directory.
        Returns (skill_name, reason) or (None, reason).
        """
        current = Path(current_dir).resolve()
        project_root = Path(manifest.project_root).resolve()

        best_match = None
        best_depth = -1
        best_priority = -1

        for route in manifest.routes:
            if not route.directories:
                continue
            for dir_pattern in route.directories:
                # Resolve relative to project root
                target = (project_root / dir_pattern).resolve()
                # Check if current_dir is inside target
                try:
                    current.relative_to(target)
                    # It's a match. Prefer deeper (more specific) paths.
                    depth = len(target.parts)
                    if (depth > best_depth or
                            (depth == best_depth and route.priority > best_priority)):
                        best_match = route.skill_name
                        best_depth = depth
                        best_priority = route.priority
                except ValueError:
                    continue

        if best_match:
            return best_match, f"directory match: working in {current_dir}"
        return None, "no directory match"

    def route_by_keywords(
        self,
        manifest: ProjectManifest,
        query: str,
    ) -> Tuple[Optional[str], str]:
        """
        Route based on keywords found in query text.
        Returns (skill_name, reason) or (None, reason).
        """
        query_lower = query.lower()
        matches = []

        for route in manifest.routes:
            if not route.keywords:
                continue
            matched_kws = [kw for kw in route.keywords if kw.lower() in query_lower]
            if matched_kws:
                matches.append((route, len(matched_kws)))

        if not matches:
            return None, "no keyword match"

        # Sort by number of keyword matches, then priority
        matches.sort(key=lambda x: (x[1], x[0].priority), reverse=True)
        best_route = matches[0][0]
        matched_kws = [kw for kw in best_route.keywords if kw.lower() in query_lower]
        return (
            best_route.skill_name,
            f"keyword match: {', '.join(matched_kws)}"
        )

    def route_by_file_pattern(
        self,
        manifest: ProjectManifest,
        file_path: str,
    ) -> Tuple[Optional[str], str]:
        """
        Route based on a file path (e.g. the file currently open in the editor).
        Returns (skill_name, reason) or (None, reason).
        """
        for route in sorted(manifest.routes, key=lambda r: r.priority, reverse=True):
            for pattern in route.file_patterns:
                if fnmatch.fnmatch(file_path, pattern):
                    return route.skill_name, f"file pattern match: {pattern}"
        return None, "no file pattern match"

    def route(
        self,
        manifest: ProjectManifest,
        query: Optional[str] = None,
        current_dir: Optional[str] = None,
        file_path: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Full routing with fallback chain.
        Returns (skill_name, reason).
        Always returns a skill — falls back to default or first declared.
        """
        # 1. Directory (most reliable signal)
        if current_dir:
            skill, reason = self.route_by_directory(manifest, current_dir)
            if skill:
                return skill, reason

        # 2. File pattern
        if file_path:
            skill, reason = self.route_by_file_pattern(manifest, file_path)
            if skill:
                return skill, reason

        # 3. Keywords from query
        if query:
            skill, reason = self.route_by_keywords(manifest, query)
            if skill:
                return skill, reason

        # 4. Default skill
        if manifest.default_skill:
            return manifest.default_skill, "default skill"

        # 5. First declared skill
        if manifest.skills:
            return manifest.skills[0], "first declared skill (no route matched)"

        raise ValueError(f"Project '{manifest.name}' has no skills declared")

    def route_all(self, manifest: ProjectManifest) -> List[str]:
        """Return all skills in the project (for cross-skill queries)."""
        return list(manifest.skills)
```

---

## New File: `contextledger/project/fusion.py`

Cross-skill context fusion. Merges results from multiple skills.

```python
"""
Context fusion — merges and deduplicates results from multiple skill queries.
"""

from typing import List, Dict, Tuple
from contextledger.core.types import MemoryUnit, MultiSkillQueryResult

class ContextFuser:
    """
    Fuses memory query results from multiple skills.

    Strategy:
    1. Deduplicate by content hash (same finding from multiple skills = one result)
    2. Rank by recency + relevance score
    3. Tag each result with its source skill(s)
    4. Preserve skill attribution for transparency
    """

    def fuse(
        self,
        query: str,
        results_by_skill: Dict[str, List[MemoryUnit]],
        active_skill: str = None,
        routing_reason: str = "",
    ) -> MultiSkillQueryResult:
        """
        Merge results from multiple skills into a single ranked list.
        """
        # Deduplicate by content
        seen_content = {}  # content_hash -> (MemoryUnit, [skill_names])

        for skill_name, units in results_by_skill.items():
            for unit in units:
                content_key = self._content_key(unit)
                if content_key in seen_content:
                    # Same finding from multiple skills — add attribution
                    seen_content[content_key][1].append(skill_name)
                else:
                    seen_content[content_key] = (unit, [skill_name])

        # Build fused list with attribution metadata
        fused = []
        for content_key, (unit, skill_names) in seen_content.items():
            fused_unit = self._annotate(unit, skill_names)
            fused.append(fused_unit)

        # Sort: active skill first, then by recency
        fused.sort(key=lambda u: self._sort_key(u, active_skill), reverse=True)

        return MultiSkillQueryResult(
            query=query,
            results_by_skill=results_by_skill,
            fused_results=fused,
            active_skill=active_skill,
            routing_reason=routing_reason,
        )

    def _content_key(self, unit: MemoryUnit) -> str:
        """Stable key for deduplication."""
        return unit.content[:200]  # first 200 chars as proxy

    def _annotate(self, unit: MemoryUnit, skill_names: List[str]) -> MemoryUnit:
        """Add skill attribution to a memory unit's metadata."""
        annotated = MemoryUnit(
            id=unit.id,
            content=unit.content,
            tier=unit.tier,
            timestamp=unit.timestamp,
            profile_name=unit.profile_name,
            metadata={
                **(unit.metadata or {}),
                "source_skills": skill_names,
                "cross_skill": len(skill_names) > 1,
            },
            embedding=unit.embedding,
        )
        return annotated

    def _sort_key(self, unit: MemoryUnit, active_skill: Optional[str]) -> Tuple:
        """Sort: active skill first, then recency."""
        is_active = (
            active_skill is not None and
            active_skill in (unit.metadata or {}).get("source_skills", [])
        )
        return (int(is_active), unit.timestamp or 0)
```

---

## New File: `contextledger/project/manager.py`

The top-level project manager. Orchestrates manifest, router, and fusion.

```python
"""
Project manager — top-level orchestrator for multi-skill projects.
"""

import os
from typing import Optional, List, Dict
from contextledger.core.types import ProjectManifest, MultiSkillQueryResult
from contextledger.project.manifest import ManifestParser, ManifestLocator
from contextledger.project.router import SkillRouter
from contextledger.project.fusion import ContextFuser

class ProjectManager:
    """
    Manages a multi-skill project.
    Loads manifest, routes operations to correct skill, fuses results.
    """

    def __init__(self, registry_backend, memory_system):
        self.registry = registry_backend
        self.memory = memory_system
        self.parser = ManifestParser()
        self.locator = ManifestLocator()
        self.router = SkillRouter()
        self.fuser = ContextFuser()
        self._manifest: Optional[ProjectManifest] = None

    def load(self, project_root: Optional[str] = None) -> ProjectManifest:
        """
        Load project.yaml from project_root or by walking up from cwd.
        Raises FileNotFoundError if no manifest found.
        """
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
        """
        Determine which skill to use.
        explicit_profile overrides all routing logic.
        Returns (skill_name, reason).
        """
        manifest = self.active_manifest()

        if explicit_profile:
            if explicit_profile not in manifest.skills:
                raise ValueError(
                    f"Profile '{explicit_profile}' not declared in project '{manifest.name}'. "
                    f"Declared skills: {manifest.skills}"
                )
            return explicit_profile, "explicit --profile flag"

        return self.router.route(
            manifest,
            query=query,
            current_dir=current_dir or os.getcwd(),
            file_path=file_path,
        )

    def query_all(self, query: str, limit: int = 10) -> MultiSkillQueryResult:
        """
        Query all skills in the project simultaneously.
        Returns fused results with skill attribution.
        """
        manifest = self.active_manifest()

        # Route to determine primary skill (for ranking)
        primary_skill, routing_reason = self.route(query=query)

        # Query each skill's memory
        results_by_skill = {}
        for skill_name in manifest.skills:
            try:
                profile = self.registry.get_profile(skill_name)
                results = self.memory.query(
                    query=query,
                    profile_name=skill_name,
                    limit=limit,
                )
                results_by_skill[skill_name] = results
            except Exception as e:
                # Don't let one failing skill break the whole query
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
        """
        Query the auto-routed skill only.
        Use this for context-aware queries where you want the most relevant skill.
        """
        skill_name, routing_reason = self.route(
            query=query,
            current_dir=current_dir,
            file_path=file_path,
            explicit_profile=explicit_profile,
        )

        results = self.memory.query(
            query=query,
            profile_name=skill_name,
            limit=limit,
        )

        return MultiSkillQueryResult(
            query=query,
            results_by_skill={skill_name: results},
            fused_results=results,
            active_skill=skill_name,
            routing_reason=routing_reason,
        )
```

---

## Project YAML Schema

```yaml
# .contextledger/project.yaml

name: genopt                          # required: project identifier
version: 1.0.0
description: LLM workflow optimizer

skills:                               # required: all skills in this project
  - sdk-skill
  - analyzer-skill
  - api-skill
  - dashboard-skill
  - config-skill

default_skill: analyzer-skill         # fallback when no route matches

fusion_enabled: true                  # merge results from all skills in cross-skill queries

routes:
  - skill: sdk-skill
    directories:
      - sdk/
      - sdk/src/genopt/
    keywords:
      - instrumentation
      - tracker
      - buffer
      - flush
      - patch
      - sdk
    file_patterns:
      - "sdk/**/*.py"

  - skill: analyzer-skill
    directories:
      - analyzer/
      - analyzer/src/genopt_analyzer/
    keywords:
      - detector
      - detection
      - analysis
      - quality
      - topology
      - suggestion
      - recipe
    file_patterns:
      - "analyzer/**/*.py"
      - "config/recipes.yaml"
      - "config/thresholds.yaml"

  - skill: api-skill
    directories:
      - api/
      - api/src/genopt_api/
    keywords:
      - endpoint
      - route
      - fastapi
      - api
      - request
      - response
    file_patterns:
      - "api/**/*.py"

  - skill: dashboard-skill
    directories:
      - dashboard/
      - dashboard/src/
    keywords:
      - dashboard
      - page
      - component
      - frontend
      - chart
      - typescript
    file_patterns:
      - "dashboard/**/*.ts"
      - "dashboard/**/*.tsx"

  - skill: config-skill
    directories:
      - config/
    keywords:
      - pricing
      - thresholds
      - models
      - configuration
    file_patterns:
      - "config/*.yaml"
```

---

## CLI Commands (New)

Add to `contextledger/cli/main.py`:

### `ctx project init`

```
ctx project init [--root PATH]
```

Interactive wizard. Asks:
- Project name
- List of existing skills (tab-completes from registry)
- Default skill
- Whether to auto-generate routes from skill names (yes/no)
  - If yes: generates directory routes based on skill name (e.g. `sdk-skill` → `sdk/`)
  - If no: opens editor for manual route definition

Creates `.contextledger/project.yaml` in current directory.

### `ctx project status`

```
ctx project status
```

Shows:
- Project name and version
- All declared skills with their status (profile exists in registry? Y/N)
- Current routing context (which skill would be active right now based on cwd)
- Memory stats per skill (sessions ingested, total findings)

### `ctx project query`

```
ctx project query <text> [--all] [--profile SKILL_NAME]
```

- Default: auto-routes based on cwd + query keywords, queries that skill
- `--all`: queries all skills, returns fused results with attribution
- `--profile SKILL_NAME`: override routing, query specific skill

### `ctx project route`

```
ctx project route [--query TEXT] [--dir PATH] [--file PATH]
```

Dry-run routing. Shows which skill would be selected and why. Useful for debugging route configuration.

### `ctx project add-skill`

```
ctx project add-skill <skill-name> [--directories DIR...] [--keywords KW...]
```

Adds a skill to the project manifest with optional route config. Validates skill exists in registry first.

### `ctx project remove-skill`

```
ctx project remove-skill <skill-name>
```

Removes a skill from the manifest. Does not delete the skill from the registry.

---

## MCP Server Updates

Add two new MCP tools to `contextledger/mcp/server.py`:

### `ctx_project_query`

```python
def ctx_project_query(
    self,
    query: str,
    mode: str = "routed",           # "routed" | "all"
    current_dir: Optional[str] = None,
    file_path: Optional[str] = None,
    profile: Optional[str] = None,
    limit: int = 10,
) -> dict:
    """
    Query context in a multi-skill project.

    mode="routed": auto-selects the most relevant skill, returns its results
    mode="all": queries all skills, returns fused results with attribution
    """
```

### `ctx_project_status`

```python
def ctx_project_status(self) -> dict:
    """
    Returns project manifest info: name, skills, current routing context.
    """
```

---

## Directory Structure After Phase 2

```
contextledger/
├── core/
│   ├── types.py          # + ProjectManifest, SkillRoute, MultiSkillQueryResult (NEW)
│   └── protocols.py      # unchanged
├── project/              # NEW directory
│   ├── __init__.py
│   ├── manifest.py       # ManifestParser, ManifestLocator
│   ├── router.py         # SkillRouter
│   ├── fusion.py         # ContextFuser
│   └── manager.py        # ProjectManager
├── memory/               # unchanged
├── backends/             # unchanged
├── skill/                # unchanged
├── merge/                # unchanged
├── mcp/
│   └── server.py         # + ctx_project_query, ctx_project_status (UPDATED)
└── cli/
    └── main.py           # + ctx project subcommands (UPDATED)
```

---

## Tests Required

### `tests/project/test_manifest.py`

```
- test_parse_valid_manifest
- test_parse_missing_name_raises
- test_parse_missing_skills_raises
- test_parse_route_missing_skill_raises
- test_parse_route_missing_condition_raises
- test_locator_finds_manifest_in_current_dir
- test_locator_finds_manifest_in_parent_dir
- test_locator_returns_none_when_not_found
- test_locator_stops_at_filesystem_root
- test_to_yaml_roundtrip
```

### `tests/project/test_router.py`

```
- test_route_by_directory_exact_match
- test_route_by_directory_subdirectory_match
- test_route_by_directory_most_specific_wins
- test_route_by_directory_no_match_returns_none
- test_route_by_keywords_single_match
- test_route_by_keywords_multiple_matches_most_keywords_wins
- test_route_by_keywords_no_match_returns_none
- test_route_by_file_pattern_match
- test_route_by_file_pattern_no_match
- test_route_full_chain_directory_first
- test_route_full_chain_falls_back_to_keywords
- test_route_full_chain_falls_back_to_default
- test_route_full_chain_falls_back_to_first_skill
- test_route_all_returns_all_skills
```

### `tests/project/test_fusion.py`

```
- test_fuse_single_skill_no_dedup
- test_fuse_multi_skill_dedup_same_content
- test_fuse_multi_skill_attribution_preserved
- test_fuse_active_skill_ranked_first
- test_fuse_empty_results
- test_fuse_cross_skill_flag_set_when_multiple_sources
```

### `tests/project/test_manager.py`

```
- test_load_from_explicit_path
- test_load_from_cwd_walk_up
- test_load_raises_when_no_manifest
- test_route_explicit_profile_overrides_all
- test_route_explicit_profile_not_in_manifest_raises
- test_route_auto_uses_router
- test_query_all_queries_each_skill
- test_query_all_handles_failing_skill_gracefully
- test_query_routed_uses_routing_result
```

### `tests/integration/test_multi_skill_project.py`

```
- test_full_genopt_project_setup
  # Creates a project.yaml matching genopt structure
  # Verifies routing to sdk-skill when cwd is sdk/
  # Verifies routing to analyzer-skill when cwd is analyzer/
  # Verifies keyword routing when cwd is project root
  # Verifies cross-skill query returns results from all skills
  # Verifies deduplication works when same finding ingested to two skills
```

### `tests/cli/test_project_commands.py`

```
- test_ctx_project_init_creates_manifest
- test_ctx_project_status_shows_all_skills
- test_ctx_project_query_routes_correctly
- test_ctx_project_query_all_flag
- test_ctx_project_query_profile_override
- test_ctx_project_route_dry_run
- test_ctx_project_add_skill
- test_ctx_project_remove_skill
```

---

## Explicit Rules for Implementation

**Do:**
- Keep `ProjectManager` as a thin orchestrator. Logic lives in `ManifestParser`, `SkillRouter`, `ContextFuser`.
- Implement `ManifestLocator.find()` to walk up directory tree like Git does with `.git/`
- Let `query_all()` fail gracefully per-skill — one missing skill doesn't break the whole query
- Log routing decisions clearly so users can debug why a skill was selected
- Add `--explain-routing` flag to `ctx project query` that prints the routing decision

**Don't:**
- Don't modify Phase 1 Protocol interfaces
- Don't add project-awareness to `StorageBackend`, `EmbeddingBackend`, or `RegistryBackend`
- Don't require a project manifest for single-skill mode — it must remain optional
- Don't auto-infer routes from project structure at runtime — routes must be explicit in `project.yaml`
- Don't store the project manifest in the registry backend — it lives in `.contextledger/project.yaml` in the project directory, version-controlled with the project's own Git repo
- Don't implement fuzzy keyword matching (substring match is enough for now)

---

## Backward Compatibility

Phase 2 must be 100% backward compatible with Phase 1:

- All existing `ctx` commands work unchanged
- If no `.contextledger/project.yaml` exists, `ctx` behaves exactly as Phase 1
- `ctx project` subcommands are only available when a manifest exists (or for `init`)
- Single-skill `ctx checkout`, `ctx query`, `ctx fork`, `ctx merge`, `ctx diff` unchanged

---

## Build Order

1. New data types in `core/types.py` (30 min)
2. `project/manifest.py` — ManifestParser + ManifestLocator (1–2 hours)
3. `project/router.py` — SkillRouter (1–2 hours)
4. `project/fusion.py` — ContextFuser (1 hour)
5. `project/manager.py` — ProjectManager (1 hour)
6. Tests for all four modules (2–3 hours)
7. CLI `ctx project` subcommands (1–2 hours)
8. MCP server additions (30 min)
9. Integration test with GenOpt-style project structure (1 hour)
10. Update README with multi-skill section (30 min)

**Estimated total: 1–2 days of focused implementation.**

---

## GenOpt Integration Example (End-to-End)

After Phase 2 is implemented, this is how GenOpt uses ContextLedger:

```bash
# Inside genopt repo
cd genopt
ctx project init
# Wizard creates .contextledger/project.yaml with 5 skills

# Working on a detector
cd analyzer/src/genopt_analyzer/detectors
ctx project query "how does retry waste detection work"
# → routes to analyzer-skill (directory match: analyzer/)
# → returns findings from analyzer-skill memory

# Cross-skill query (SDK calls analyzer)
ctx project query "how does the SDK pass data to the analyzer" --all
# → queries both sdk-skill and analyzer-skill
# → returns fused results with source attribution

# Debugging routing
ctx project route --query "retry waste detector"
# → "analyzer-skill (keyword match: detector, retry)"

# Check project health
ctx project status
# → Shows all 5 skills, memory stats per skill, current routing context
```

---

*Phase 2 plan version 1.0. Builds on Phase 1 (214 tests passing). All Phase 1 interfaces unchanged.*
