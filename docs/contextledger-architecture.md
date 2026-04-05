# ContextLedger — Architecture & Build Document
**For Claude Code. This document is the source of truth for all architectural decisions.**

---

## What We Are Building

ContextLedger is a **universal context layer and ctx versioning platform** for research engineers and developers working across multiple AI interfaces and domains.

It solves two distinct but related problems:

**Problem 1: Context Fragmentation**
A user works in Claude Code, Claude Chat, Cursor, OpenAI, Perplexity. Every session is isolated. Findings, decisions, architectural choices, and learned patterns disappear between sessions and across interfaces. There is no unified memory that understands the user's work across all of these.

**Problem 2: Skill Iteration Without Reproducibility**
A user builds a ctx (extraction rules, synthesis logic, tools, reference docs) for one domain (e.g. supervised database research). They want to fork it for a different domain (e.g. filesystem research), iterate independently, then merge improvements back. No existing tool supports this with semantic understanding of what changed and why.

**ContextLedger solves both in one system, with two modes:**
- **Second Brain Mode**: Auto-captures context across all AI interfaces. No ctx definition needed. Just connect and query.
- **Skill Versioning Mode**: Define a ctx profile, fork it per domain, iterate, merge with semantic conflict resolution.

Both modes use the same underlying infrastructure. A user can run both simultaneously.

---

## What We Are NOT Building

- An agent orchestration framework (that's LangGraph, CrewAI)
- A prompt versioning tool (that's MLflow, PromptLayer, Langfuse)
- A note-taking or second brain app (that's Notion, Obsidian)
- An enterprise knowledge base (that's Guru, Confluence)
- A multi-agent coordination system (separate concern)
- A replacement for Git (Git is our backend, not what we replace)

Do not conflate these. Every time a new feature is proposed, ask: does this belong in one of the above categories? If yes, don't build it.

---

## Core Principles (Never Violate These)

1. **Pluggability over convenience**: Every backend — storage, embedding, registry — must be swappable. Never hardcode a backend. Write interface contracts first, implementations second.
2. **Git as versioning backbone**: Do not reinvent versioning. Use Git for ctx bundle versioning. Add semantic understanding on top, not instead.
3. **Inheritance not duplication**: Forked skills inherit from parent. Only overridden sections are stored in the fork. Unchanged files reference parent via content-addressable lookup.
4. **Separation of concerns**: The ctx profile layer, synthesis layer, memory layer, and ingestion layer must not know about each other's internals. They communicate through defined interfaces only.
5. **Second brain mode must work with zero configuration**: A user who never defines a ctx profile must get value from day one. Don't gate the second brain mode behind ctx setup.
6. **Plan before build**: The three architecture decisions (memory abstraction, ctx profile schema, conflict resolution) must be finalized before any implementation begins.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    USER INTERFACES                       │
│  Claude Chat │ Claude Code │ Cursor │ OpenAI │ Perplexity│
└──────────────────────┬──────────────────────────────────┘
                       │ MCP (Model Context Protocol)
                       ▼
┌─────────────────────────────────────────────────────────┐
│                  INGESTION LAYER                         │
│  MCP Server → Session Capture → Signal Extraction        │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│              CONTEXT MANAGEMENT LAYER                    │
│  CMV DAG Engine │ Three-Tier Memory │ Lossless Trimming  │
└──────────────────────┬──────────────────────────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
┌──────────────┐ ┌──────────┐ ┌──────────────────────────┐
│  IMMEDIATE   │ │SYNTHESIS │ │       ARCHIVAL            │
│  (verbatim)  │ │(compressed│ │   (semantic embeddings)  │
│  last 10     │ │ findings) │ │   full history            │
└──────────────┘ └──────────┘ └──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                 SKILL PROFILE LAYER                      │
│  Profile YAML │ DAG Executor │ Extraction Rules          │
│  Fork/Merge   │ Synthesis Templates │ Profile Registry   │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│              PLUGGABLE BACKEND LAYER                     │
│  StorageBackend   │   EmbeddingBackend   │  RegistryBackend│
│  (SQLite/Postgres/│   (Jina/OpenAI/     │  (Git/S3/HTTP)  │
│   Neo4j/Chroma)   │   local transformers)│                 │
└─────────────────────────────────────────────────────────┘
```

---

## Architecture Decision 1: Memory Abstraction Layer

### The Two Required Abstract Interfaces

These must be written as Python `Protocol` classes **before any implementation**. Nothing else touches storage or embeddings directly.

#### StorageBackend Protocol

```python
from typing import Protocol, List, Optional, Any

class StorageBackend(Protocol):
    def write(self, unit: MemoryUnit) -> str:
        """Write a memory unit. Returns ID."""
        ...

    def read(self, id: str) -> Optional[MemoryUnit]:
        """Read a memory unit by ID."""
        ...

    def search(self, query_embedding: List[float], limit: int) -> List[MemoryUnit]:
        """Semantic search. Returns ranked results."""
        ...

    def traverse(self, node_id: str, depth: int) -> List[MemoryUnit]:
        """Graph traversal from a node. Returns related units."""
        ...

    def delete(self, id: str) -> bool:
        """Delete a memory unit. Returns success."""
        ...

    def list_by_profile(self, profile_name: str) -> List[MemoryUnit]:
        """List all memory units belonging to a ctx profile."""
        ...
```

#### EmbeddingBackend Protocol

```python
class EmbeddingBackend(Protocol):
    def encode(self, text: str) -> List[float]:
        """Encode text to embedding vector."""
        ...

    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        """Batch encode. More efficient than calling encode() in a loop."""
        ...

    def similarity(self, a: List[float], b: List[float]) -> float:
        """Cosine similarity between two embeddings."""
        ...
```

#### RegistryBackend Protocol

```python
class RegistryBackend(Protocol):
    def list_profiles(self, filter: Optional[dict] = None) -> List[ProfileMetadata]:
        """List all profiles, optionally filtered."""
        ...

    def get_profile(self, name: str, version: Optional[str] = None) -> SkillBundle:
        """Get a ctx bundle by name and optional version."""
        ...

    def save_profile(self, bundle: SkillBundle) -> str:
        """Save a ctx bundle. Returns version ID."""
        ...

    def fork_profile(self, parent_name: str, new_name: str) -> SkillBundle:
        """Fork a profile. New bundle inherits all parent files."""
        ...

    def list_versions(self, name: str) -> List[str]:
        """List all versions of a profile."""
        ...

    def get_diff(self, name_a: str, name_b: str) -> ProfileDiff:
        """Diff two profiles. Shows what changed."""
        ...
```

### Default Backend Implementations

| Backend | Default | Swap-in candidates | When to upgrade |
|---|---|---|---|
| StorageBackend | SQLite + semantic index | Postgres+pgvector, Neo4j, Chroma, Qdrant | When you need graph traversal at scale or multi-user |
| EmbeddingBackend | Jina embeddings (jina-embeddings-v3) | OpenAI text-embedding-3, local sentence-transformers, Qwen3-Embedding | When cost or latency matters at scale |
| RegistryBackend | Git (local repo) | GitHub remote, S3+DynamoDB, HTTP API | When teams need shared registry or cloud hosting |

### What Jina Embeddings Is

Jina AI produces the `jina-embeddings-v3` model — a state-of-the-art embedding model (as of 2026) that runs locally, is lightweight (570M params), multilingual, and free to self-host. It outperforms OpenAI's older embedding models on many benchmarks while costing nothing per call. This is the right default for a developer tool. It ships as a Python package: `pip install jina-embeddings`. If a user prefers OpenAI embeddings (for consistency with existing systems), they swap the EmbeddingBackend implementation — one class, no other changes.

---

## Architecture Decision 2: Skill Profile Schema

### A Skill is a Directory Bundle

A ctx is not a single file. It is a directory with a defined structure:

```
skills/
└── supervised-db-research/
    ├── profile.yaml          # REQUIRED: machine-executable config
    ├── skill.md              # OPTIONAL: human docs, examples, usage
    ├── tools/
    │   ├── db_connector.py   # tool implementations
    │   └── query_builder.py
    ├── refs/
    │   ├── schema_docs.pdf   # reference material
    │   └── domain_glossary.md
    └── tests/
        └── sample_findings.json
```

**The `skill.md` file**: human-readable documentation only. It describes what the ctx does, how to use it, examples. It is not machine-executable. It is not versioned by the synthesis engine. It travels with the bundle but is not parsed.

**The `profile.yaml` file**: machine-executable config. This is what gets versioned, forked, and merged semantically. See schema below.

**Tools directory**: actual implementation code the ctx calls. When a fork overrides a tool, it puts a new file in `tools/`. Unchanged tools are inherited from parent via content-addressable reference — not copied.

**Refs directory**: reference documents the ctx uses (domain glossary, schema docs, etc.). Same inheritance rule: only overrides are stored in fork.

**Inheritance rule**: A fork only stores what it changes. Everything else resolves to parent at runtime. This is Git's content-addressable model applied to ctx bundles.

### Profile YAML Schema

```yaml
# profile.yaml
name: supervised-db-research          # unique identifier
version: 1.0.0                        # semantic version
parent: null                          # null = base profile; or parent ctx name

base_skill: base-research-skill       # optional: inherit from a BASE-SKILL template
                                      # (like BASE-AGENT.md pattern from claude-mpm-agents)

extraction:
  entities:                           # entity types to extract from session context
    - table
    - column
    - finding
    - hypothesis
  sources:                            # data sources this ctx operates on
    - supervised_database
  rules:
    - match: "query pattern findings"
      extract: finding
      confidence_threshold: 0.7
    - match: "schema analysis"
      extract: table
      confidence_threshold: 0.8

synthesis:
  dag:                                # Directed Acyclic Graph of synthesis steps
    nodes:
      - id: extract_entities
        type: extraction              # node type: extraction | reasoning | synthesis | filter
        depends_on: []                # no dependencies = runs first
        tool: tools/db_connector.py  # optional: tool this node calls
      - id: build_relationships
        type: reasoning
        depends_on: [extract_entities]
      - id: synthesise_findings
        type: synthesis
        depends_on: [build_relationships]
        template: find_patterns       # references a template below
  templates:
    - id: find_patterns
      prompt: |
        Given these entities {entities} extracted from {source},
        identify patterns, anomalies, and findings.
        Return structured output with confidence scores.

memory_schema:
  graph_nodes:                        # types of nodes in the knowledge graph
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
  mode: skill_versioning              # second_brain | skill_versioning | combined
  cmv_enabled: true                   # enable DAG-based session history (CMV)
  trim_threshold: 0.3                 # trim sessions when overhead > 30% of tokens
  memory_tiers:
    immediate_turns: 10               # verbatim last N turns
    synthesis_window_days: 7          # compressed summaries from last N days
    archival: true                    # semantic search over full history
```

### Fork Schema

When forking, only changed sections are written. The fork YAML only needs to declare overrides:

```yaml
# filesystem-research/profile.yaml (fork of supervised-db-research)
name: filesystem-research
version: 1.0.0-fs-1
parent: supervised-db-research        # declares parent explicitly

# Everything below OVERRIDES the parent. Anything not declared here is inherited.

extraction:
  sources:
    - filesystem                      # override: different data source
  entities:
    - file
    - directory
    - finding                         # "finding" inherited concept, kept
  # query_builder.py tool inherited unchanged from parent

synthesis:
  dag:
    nodes:
      - id: extract_entities
        type: extraction
        depends_on: []
        tool: tools/filesystem_scanner.py  # override: different tool
      # build_relationships and synthesise_findings inherited from parent

memory_schema:
  # inherited unchanged
```

### BASE-SKILL Pattern

Adopt the inheritance model from `claude-mpm-agents` (bobmatnyc/claude-mpm-agents). Create a `base-research-skill` that all research skills inherit from. It defines common extraction patterns, default DAG structure, and shared synthesis templates. Domain-specific skills declare `base_skill: base-research-skill` and only override what they need. This reduces duplication by ~57% (proven by the MPM agents approach).

---

## Architecture Decision 3: Context Management — CMV + Three-Tier Memory

### CMV (Contextual Memory Virtualisation)

Based on the February 2026 paper (arXiv:2602.22402). Session history is modelled as a **Directed Acyclic Graph (DAG)** with three primitives:

- **Snapshot**: capture current session state as a versioned node
- **Branch**: create new session from a snapshot (with optional orientation message)
- **Trim**: lossless compression — strip mechanical bloat (raw tool outputs, base64 images, metadata) while preserving every user message and assistant response verbatim

CMV achieves 20% mean token reduction, up to 86% in heavy sessions. Sessions with significant tool output overhead (your Agent Prober sessions) get the most benefit.

This is not optional. CMV is enabled by default when `cmv_enabled: true` in profile YAML (which is the default).

### Three-Tier Memory Architecture

All incoming session context flows into three tiers:

| Tier | Content | Storage | Retrieval |
|---|---|---|---|
| Immediate | Verbatim last N turns (default: 10) | In-memory / SQLite | Direct lookup |
| Synthesis | Compressed findings from past week | StorageBackend (semantic index) | Semantic search |
| Archival | Full history, semantic embeddings | StorageBackend (full) | Embedding similarity |

When a query arrives, a lightweight **routing layer** decides which tiers to pull from based on query intent:
- "What did I find yesterday?" → Synthesis tier
- "What was my original hypothesis about X?" → Archival tier
- "What were we just discussing?" → Immediate tier
- "Show me all findings related to Y across my work" → Synthesis + Archival

### GCC Integration (Git Context Controller)

Adopt GCC's (arXiv paper) COMMIT/BRANCH/MERGE semantics inside the reasoning loop. When an agent session hits a decision point or completes a major finding, it commits context state. When exploring a hypothesis, it branches. When findings converge, it merges. This runs at the session level, complementary to ctx profile versioning which runs at the configuration level.

### Lossless-Claw Pattern

Adopt the Lossless-Claw plugin architecture for context retrieval tools. Agents (Claude Code sessions) should have access to:
- `ctx_grep(query)` — semantic search over ctx context history
- `ctx_describe(finding_id)` — describe a specific finding
- `ctx_expand(node_id)` — expand a compressed summary back to original detail

These are MCP tools exposed by the ContextLedger MCP server.

---

## Architecture Decision 4: ContextLedger Storage

### Git as Primary Registry Backend

The ContextLedger does not invent versioning. It uses Git. A ctx bundle is a directory in a Git repository. Versions are commits. Branches are forks. Merges are merges.

**What ContextLedger adds on top of Git:**
- Semantic understanding of profile YAML structure (knows which sections changed)
- Profile metadata index (fast lookup by name, version, parent)
- Fork inheritance resolution (follow parent chain to resolve overrides)
- Semantic conflict detection (tier two evaluation harness — see below)
- MCP ingestion hooks
- CLI for ctx checkout, fork, diff, merge

**Registry backends:**

| Backend | Use case | Implementation |
|---|---|---|
| Git (local) | Single developer, default | `gitpython` library, local repo |
| Git (remote) | Teams, GitHub/GitLab | Remote URL, push/pull on save |
| S3 + metadata DB | Cloud hosting, large teams | S3 for bundles, Postgres for metadata |
| HTTP API | Remote ContextLedger service | REST client pointing to hosted instance |

Default is Git local. Switching backends is one config change — `registry_backend: git_local` vs `registry_backend: s3`.

### CLI Commands

```bash
# Basic operations
ctx init                            # create new local registry
ctx new supervised-db-research      # create new ctx profile (with wizard)
ctx checkout supervised-db-research # load latest version
ctx checkout supervised-db-research@1.2.0  # specific version
ctx list                            # list all skills
ctx list supervised-db-research --branches  # list all forks

# Fork operations
ctx fork supervised-db-research filesystem-research  # create fork
ctx diff filesystem-research supervised-db-research  # compare
ctx merge filesystem-research supervised-db-research  # merge fork back to parent

# Context operations
ctx connect claude-code             # hook into Claude Code sessions
ctx connect openai                  # hook into OpenAI sessions
ctx query "what did I learn about X"  # query across context
ctx status                          # show active profile, recent findings
```

---

## Architecture Decision 5: Conflict Resolution (Tier System)

When merging a fork back to parent, three-tier resolution applies in order:

### Tier 1 — Automatic Merge
**Condition**: changes are in different sections of the profile YAML with no shared DAG node dependencies.
**Action**: auto-apply, log it, no user action needed.
**Example**: fork changed `extraction.sources`, parent changed `memory_schema.graph_edges`. No overlap. Auto-merge.

### Tier 2 — Semantic Evaluation (BUILD THIS FROM DAY ONE)
**Condition**: same section, different logic.
**Action**: run both versions on a held-out evaluation set, score outputs, surface diff to user with recommendation.

**How it works:**
1. Grab last N findings (default: 50) extracted under parent profile.
2. Run both synthesis templates (parent version vs fork version) on the same 50 findings.
3. Score both: precision, recall, novelty of findings extracted.
4. Generate a report: "Fork version detects 12% more novel findings but introduces 8% false positives vs parent."
5. User sees report, decides: merge, reject, or run both in parallel for further evaluation.

**This is the key differentiator from all existing tools.** No prompt versioning tool, no knowledge management system, and no ctx framework does this today. Spring AI explicitly called out "limited ctx versioning — no built-in versioning system for skills" as a known gap. This fills it.

**Implementation note**: The evaluation harness is a small Python module. It needs: a findingsstore (last N findings per profile, with provenance), a runner (executes a synthesis template against findings), and a scorer (compares outputs). Do not over-engineer this. Ship simple precision/recall scoring first. Add LLM-as-judge scoring later.

### Tier 3 — Manual Override
**Condition**: conflicting changes to the same synthesis template or extraction rule with no clear winner from evaluation.
**Action**: flag it, block the merge, require explicit user resolution via CLI or UI.
**Never auto-merge tier 3 conflicts.** Block clearly, explain what conflicts, give the user both versions side by side.

---

## Universal Interface Integration (MCP)

ContextLedger connects to any AI interface that supports MCP (Model Context Protocol). As of 2026, this includes: Claude Code, Claude Chat, Cursor, and any OpenAI-compatible interface with MCP support.

**Ingestion flow:**
```
AI Interface session ends
    → MCP hook fires
    → ContextLedger MCP server receives session log
    → Signal extraction runs (based on active profile)
    → Extracted signals feed into three-tier memory
    → DAG synthesis runs if new findings threshold met
```

**MCP server exposes:**
- `ctx_ingest(session_log)` — ingest a session
- `ctx_query(query, profile)` — query context
- `ctx_grep(pattern)` — search findings
- `ctx_status()` — current profile, recent activity
- `skill_checkout(name, version)` — switch active profile

The MCP server is the single integration point. Users configure their AI interface to point at the ContextLedger MCP server once. After that, all ingestion is automatic.

---

## Profile YAML Auto-Generation

Users must never be required to write profile YAML from scratch. Provide three paths:

**Path 1 — Interactive wizard (MVP)**
```bash
ctx new my-research-skill
> What data source does this ctx work with? (filesystem / database / API / documents)
> What entities should be extracted? (findings, hypotheses, anomalies, ...)
> What domain is this ctx for? (security research / data analysis / ...)
> Generating profile.yaml...
```

**Path 2 — Template fork**
Ship templates: `base-research-skill`, `base-security-skill`, `base-analysis-skill`. User runs `ctx fork base-research-skill my-skill` and edits the few relevant fields.

**Path 3 — Code inference (post-MVP)**
Point ContextLedger at a Python file with tool definitions. It parses function signatures, docstrings, and infers a profile YAML stub.

---

## What to Build and In What Order

### Phase 1 (Weeks 1–2): Interface Contracts
- Write Python `Protocol` classes for `StorageBackend`, `EmbeddingBackend`, `RegistryBackend`
- Define `MemoryUnit`, `SkillBundle`, `ProfileMetadata`, `ProfileDiff` data types
- Write stub implementations that return mock data
- Write tests against the interfaces (not implementations)
- **Do not touch actual storage yet**

### Phase 2 (Weeks 3–4): CMV Session Layer
- Implement CMV DAG engine: snapshot, branch, trim primitives
- Implement three-pass lossless trimming algorithm (from arXiv:2602.22402)
- Wire into SQLite storage stub
- Test on real Claude Code session logs

### Phase 3 (Weeks 5–6): Default Backends
- Implement SQLite StorageBackend
- Implement Jina EmbeddingBackend
- Implement Git (local) RegistryBackend using `gitpython`
- Run all interface tests against real implementations

### Phase 4 (Weeks 7–8): Skill Profile Layer
- Implement profile YAML parser and validator
- Implement DAG executor (sequential node execution first, parallel later)
- Implement fork primitive (inheritance chain resolution)
- Implement ctx bundle directory structure
- Add interactive wizard for profile generation

### Phase 5 (Weeks 9–10): MCP Ingestion Server
- Build MCP server exposing ingestion and query tools
- Connect to Claude Code first (highest priority)
- Add Claude Chat support
- Test second brain mode end to end

### Phase 6 (Weeks 11–12): CLI
- Implement all CLI commands: init, new, checkout, fork, diff, merge, query, status, connect
- Ship `pip install contextledger`
- Write README with quickstart

### Phase 7 (Month 2): Tier 2 Conflict Resolution
- Build evaluation harness (findingsstore, runner, scorer)
- Implement tier 1 auto-merge
- Implement tier 2 semantic evaluation
- Implement tier 3 manual override with clear error messaging

### Phase 8 (Month 2+): Additional Backends
- Postgres + pgvector StorageBackend
- OpenAI EmbeddingBackend
- GitHub remote RegistryBackend
- Add Cursor and OpenAI MCP integration

---

## What to Explicitly Avoid

| Avoid | Because |
|---|---|
| Hardcoding SQLite as the only storage option | Violates pluggability principle. Even if SQLite is the default, the interface must be abstract from day one. |
| Implementing versioning logic yourself | Git already does this correctly and reliably. Use it. |
| Building an agent orchestration layer | That's LangGraph/CrewAI. Out of scope. |
| Adding a web UI in MVP | Premature. CLI first, UI later if users ask for it. |
| Tight coupling between synthesis DAG and storage backend | They must only communicate through the StorageBackend interface. |
| Auto-merging tier 3 conflicts | Always block and require explicit resolution. Silent bad merges are worse than explicit failures. |
| Building the evaluation harness as an afterthought | It must exist from day one. Without it, semantic merging is impossible and the key differentiator doesn't exist. |
| Storing skill.md in the metadata index | It's documentation, not machine-executable. Parse profile.yaml only. |
| Requiring users to write YAML manually | Always provide wizard or template fork as the entry path. |
| Copying files in forks | Forks inherit via reference. Only overrides are stored. Copy-on-write only when a file is actually modified in the fork. |
| Locking to a single AI interface | The entire value of second brain mode depends on universal ingestion. Build MCP first, then wire each interface through it. |

---

## Key Research References

These papers and projects directly inform the architecture. Read them before implementing the relevant component.

| Reference | What it informs |
|---|---|
| arXiv:2602.22402 — CMV (Feb 2026) | Three-pass lossless trimming, DAG-based session history, snapshot/branch/trim primitives |
| arXiv:2602.12430 — Agent Skills (Feb 2026) | Skill security, lifecycle governance, trust framework. Read before implementing MCP ingestion. |
| github.com/martian-engineering/lossless-claw | Production implementation of DAG context with hierarchical summarisation, lcm_grep/describe/expand tools |
| github.com/bobmatnyc/claude-mpm-agents | BASE-AGENT inheritance pattern to adopt for base-skill templates |
| github.com/nuster1128/MemEngine | Pluggable memory module architecture reference |
| arXiv (GCC) — Git Context Controller | COMMIT/BRANCH/MERGE semantics in agent reasoning loop |
| arXiv:2603.03296 — PlugMem | Knowledge units as propositions + prescriptions (not just entities/relations) — informs memory schema design |
| spring.io — Spring AI Agent Skills (Jan 2026) | Explicit acknowledgement that ctx versioning is a known gap in current frameworks |

---

## Glossary

**Skill**: A directory bundle containing a `profile.yaml`, optional `skill.md`, tools, reference docs, and tests.

**Skill Profile**: The `profile.yaml` file within a ctx bundle. Machine-executable configuration defining extraction rules, synthesis DAG, memory schema, and session context settings.

**Profile Fork**: A child profile that inherits all sections from a parent profile and only declares overrides. Switching between forks at runtime requires no redeploy.

**ContextLedger**: The system that stores, versions, and manages ctx bundles. Uses Git as the versioning backbone. Pluggable backends for different deployment scenarios.

**Second Brain Mode**: ContextLedger operating without a custom ctx profile. Ingests all sessions via MCP, applies generic extraction, stores in three-tier memory, responds to queries. Zero configuration required.

**Skill Versioning Mode**: ContextLedger operating with a custom ctx profile. Domain-aware extraction and synthesis, fork/merge semantics, semantic conflict resolution.

**CMV (Contextual Memory Virtualisation)**: DAG-based session history management. Enables snapshot, branch, and trim operations on session context. Reduces token overhead by 20–86%.

**Three-Tier Memory**: Immediate (verbatim recent turns) + Synthesis (compressed recent findings) + Archival (full semantic history). Queries route to the appropriate tier based on intent.

**Evaluation Harness**: The module that runs two synthesis versions against the same findings and scores the results. Required for tier 2 conflict resolution in merge operations.

**StorageBackend / EmbeddingBackend / RegistryBackend**: Python Protocol interfaces that all storage, embedding, and registry implementations must satisfy. Nothing outside these interfaces should know about implementation details.

**DAG (Directed Acyclic Graph)**: Used in two places: (1) synthesis DAG — the computation graph defining how new data flows through extraction, reasoning, and synthesis nodes; (2) CMV session DAG — the version graph of session snapshots.

**MCP (Model Context Protocol)**: Anthropic's open standard (Nov 2024) for connecting AI interfaces to external tools and data sources. Adopted by all major AI providers. ContextLedger's universal ingestion interface.

---

*Document version: 1.0. Built from brainstorming session covering: second brain problem, ctx versioning problem, CMV research, GCC research, pluggable architecture, Git-as-backend decision, three-tier memory, conflict resolution tiers, and comparison with existing tools (Supermemory, Mem0, Zep, MLflow, PromptLayer, Langfuse, lossless-claw, claude-mpm-agents, Spring AI Agent Skills, MemEngine, PlugMem).*
