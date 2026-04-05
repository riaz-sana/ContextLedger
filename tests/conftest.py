"""Shared pytest fixtures for ContextLedger tests.

Provides backend stubs, sample data, and fixture factories
that all test modules can use.
"""

import pytest
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Sample data factories
# ---------------------------------------------------------------------------

def make_memory_unit(
    id: str = "mem-001",
    content: str = "Sample finding about database schema",
    profile_name: str = "supervised-db-research",
    unit_type: str = "finding",
    embedding: Optional[List[float]] = None,
    tags: Optional[List[str]] = None,
    timestamp: Optional[datetime] = None,
    parent_id: Optional[str] = None,
    metadata: Optional[dict] = None,
):
    """Factory for creating MemoryUnit-like dicts until types.py is implemented."""
    return {
        "id": id,
        "content": content,
        "profile_name": profile_name,
        "unit_type": unit_type,
        "embedding": embedding or [0.1] * 128,
        "tags": tags or [],
        "timestamp": timestamp or datetime.now(timezone.utc),
        "parent_id": parent_id,
        "metadata": metadata or {},
    }


def make_profile_yaml(
    name: str = "supervised-db-research",
    version: str = "1.0.0",
    parent: Optional[str] = None,
    entities: Optional[List[str]] = None,
    sources: Optional[List[str]] = None,
):
    """Factory for creating profile YAML content strings."""
    entities = entities or ["table", "column", "finding", "hypothesis"]
    sources = sources or ["supervised_database"]
    parent_line = f"parent: {parent}" if parent else "parent: null"

    return f"""name: {name}
version: {version}
{parent_line}

extraction:
  entities:
{chr(10).join(f'    - {e}' for e in entities)}
  sources:
{chr(10).join(f'    - {s}' for s in sources)}
  rules:
    - match: "query pattern findings"
      extract: finding
      confidence_threshold: 0.7

synthesis:
  dag:
    nodes:
      - id: extract_entities
        type: extraction
        depends_on: []
      - id: build_relationships
        type: reasoning
        depends_on: [extract_entities]
      - id: synthesise_findings
        type: synthesis
        depends_on: [build_relationships]
        template: find_patterns
  templates:
    - id: find_patterns
      prompt: |
        Given these entities extracted, identify patterns.

memory_schema:
  graph_nodes:
    - Entity
    - Finding
    - Hypothesis
  graph_edges:
    - from: Finding
      to: Hypothesis
      label: supports_or_contradicts
    - from: Entity
      to: Finding
      label: discovered_in

session_context:
  mode: skill_versioning
  cmv_enabled: true
  trim_threshold: 0.3
  memory_tiers:
    immediate_turns: 10
    synthesis_window_days: 7
    archival: true
"""


def make_fork_profile_yaml(
    name: str = "filesystem-research",
    version: str = "1.0.0-fs-1",
    parent: str = "supervised-db-research",
):
    """Factory for creating a forked profile YAML."""
    return f"""name: {name}
version: {version}
parent: {parent}

extraction:
  sources:
    - filesystem
  entities:
    - file
    - directory
    - finding
"""


def make_session_log(
    turns: int = 5,
    include_tool_output: bool = True,
    include_base64: bool = False,
):
    """Factory for creating mock session logs for CMV testing."""
    messages = []
    for i in range(turns):
        messages.append({
            "role": "user",
            "content": f"User message {i+1}: What about the schema?",
            "timestamp": f"2026-01-01T00:{i:02d}:00Z",
        })
        assistant_content = f"Assistant response {i+1}: Here are my findings."
        if include_tool_output:
            assistant_content += f"\n[TOOL_OUTPUT] {{\"rows\": {i*100}, \"columns\": [\"id\", \"name\", \"value\"]}}"
        if include_base64:
            assistant_content += f"\n[IMAGE] data:image/png;base64,{'A' * 200}"
        messages.append({
            "role": "assistant",
            "content": assistant_content,
            "timestamp": f"2026-01-01T00:{i:02d}:30Z",
        })
    return {"session_id": "session-001", "messages": messages}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_memory_unit():
    return make_memory_unit()


@pytest.fixture
def sample_memory_units():
    """A batch of memory units for search/traverse testing."""
    return [
        make_memory_unit(id=f"mem-{i:03d}", content=f"Finding {i}", tags=[f"tag-{i % 3}"])
        for i in range(10)
    ]


@pytest.fixture
def sample_profile_yaml():
    return make_profile_yaml()


@pytest.fixture
def sample_fork_yaml():
    return make_fork_profile_yaml()


@pytest.fixture
def sample_session_log():
    return make_session_log()


@pytest.fixture
def sample_session_log_heavy():
    """Session log with lots of tool output and base64 — good for trimmer tests."""
    return make_session_log(turns=20, include_tool_output=True, include_base64=True)


@pytest.fixture
def tmp_git_repo(tmp_path):
    """Creates a temporary git repository for registry backend tests."""
    import subprocess
    repo_dir = tmp_path / "test_registry"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_dir, capture_output=True)
    return repo_dir


@pytest.fixture
def tmp_db_path(tmp_path):
    """Provides a temporary path for SQLite database."""
    return tmp_path / "test_contextledger.db"
