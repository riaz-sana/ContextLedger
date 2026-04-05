# ContextLedger

A universal context layer and skill versioning platform for AI interfaces.

ContextLedger solves two problems:

1. **Context Fragmentation** — You work in Claude Code, Claude Chat, Cursor, OpenAI, Perplexity. Every session is isolated. Findings, decisions, and patterns disappear between sessions. ContextLedger provides unified memory across all interfaces.

2. **Skill Iteration Without Reproducibility** — You build a skill profile for one domain, want to fork it for another, iterate independently, then merge improvements back. ContextLedger supports this with semantic conflict resolution.

Two modes, one system:
- **Second Brain Mode**: Zero-config context capture. Connect and query. No skill profile needed.
- **Skill Versioning Mode**: Define profiles, fork per domain, iterate, merge with tier-based conflict resolution.

---

## Quick Start

### Install

```bash
pip install -e ".[dev]"
```

### Initialize

```bash
ctx init
```

### Create a skill profile

```bash
ctx new my-research-skill
```

### Fork and iterate

```bash
ctx fork my-research-skill my-domain-skill
ctx diff my-domain-skill my-research-skill
ctx merge my-domain-skill my-research-skill
```

### Query context (second brain mode)

```bash
ctx query "what did I find about the schema?"
ctx status
```

---

## Current Status

**Core framework: fully implemented and tested (214 tests passing).**

| What | Status | Notes |
|------|--------|-------|
| Data types & protocols | Ready | All 4 types, 3 protocol interfaces |
| In-memory stub backends | Ready | Full test coverage, usable for dev |
| SQLite storage | Ready | Persistent, tested |
| Jina embeddings | Ready | Requires `pip install jina-embeddings` |
| Git local registry | Ready | Uses real git for versioning |
| CMV session engine | Ready | Snapshot/branch/trim with lossless compression |
| Three-tier memory | Ready | Immediate/synthesis/archival with routing |
| Profile parser & validator | Ready | Full YAML schema support |
| DAG executor | Ready | Topological sort, dependency passing (stub node handlers) |
| Fork & inheritance | Ready | Deep merge with cycle detection |
| Conflict resolution | Ready | Tier 1/2/3 with evaluation harness |
| MCP server | Ready | Second brain mode works out of the box |
| CLI (`ctx`) | Ready | All commands functional |
| Postgres backend | Implemented | Needs PostgreSQL + pgvector to test |
| OpenAI embeddings | Implemented | Needs API key to test |
| GitHub registry | Implemented | Needs token + repo to test |

**What you can do today:**
- Run second brain mode (ingest sessions, query across them) — works immediately
- Create, fork, diff, and merge skill profiles via CLI
- Use any backend combination (SQLite + stub embeddings is the zero-config default)
- Build on the protocol interfaces with your own backends

**What's placeholder / future work:**
- DAG node handlers return stub outputs (extraction/reasoning/synthesis/filter nodes don't execute real logic yet — the executor manages ordering and data flow correctly, but actual domain-specific processing needs LLM integration)
- Evaluation harness uses synthetic scoring (real template execution requires wiring to an LLM)
- MCP integration with specific AI interfaces (Claude Code, Cursor, etc.) needs the MCP transport layer configured per-interface

---

## How It Works — Architecture Deep Dive

### The Problem

You use 5 different AI interfaces. Each session is isolated. Your findings, hypotheses, and decisions vanish when you close the tab. And when you build a skill profile for database research, you can't fork it for filesystem research and merge improvements back.

### The Solution: Three Core Innovations

#### 1. CMV — Contextual Memory Virtualisation

*Based on [arXiv:2602.22402](https://arxiv.org/abs/2602.22402)*

Session history is modeled as a **Directed Acyclic Graph**, not a flat log. Three primitives:

- **Snapshot**: Capture session state as a versioned node
- **Branch**: Fork a new exploration path from any snapshot (hypothesis testing, alternative approaches)
- **Trim**: Lossless compression — strip mechanical bloat while preserving every user/assistant message

The trimmer runs three passes:
1. **Strip tool outputs**: Remove `[TOOL_OUTPUT]` blocks (raw JSON, stderr, stdout)
2. **Strip base64**: Remove embedded images/files, replace with `[image removed]`
3. **Strip metadata**: Normalize whitespace, remove `[META:]` markers

Result: **20-86% token reduction** on real sessions. Sessions with heavy tool output (Agent Prober, code generation) benefit the most.

#### 2. Three-Tier Memory with Intent Routing

Not all queries need the same memory. A lightweight router classifies intent:

| Query | Routes to | Why |
|-------|-----------|-----|
| "What were we just discussing?" | **Immediate** | Recent conversation, verbatim recall |
| "What did I find yesterday?" | **Synthesis** | Compressed findings from recent window |
| "What was my original hypothesis?" | **Archival** | Full semantic history, embedding search |
| "Show me all findings about X" | **Synthesis + Archival** | Cross-tier aggregation |

**Immediate tier**: Ring buffer of last N turns. Fast, verbatim, no compression.

**Synthesis tier**: Time-windowed findings (default 7 days). Expired findings drop out. Good for "what have I been working on recently?"

**Archival tier**: Everything, forever. Semantic search via embedding similarity. The long-term memory.

#### 3. Semantic Conflict Resolution (The Key Differentiator)

When you merge a forked skill profile back to parent, changes go through a three-tier evaluation:

**Tier 1 — Auto-merge**: Changes don't overlap, or values are identical. Applied silently.

**Tier 2 — Semantic evaluation**: Same section, different logic (e.g., both modified a synthesis template). The evaluation harness:
1. Takes the last 50 findings extracted under the parent profile
2. Runs both versions (parent template vs fork template) on those findings
3. Scores both: **precision** (correctness), **recall** (completeness), **novelty** (new discoveries)
4. Reports: *"Fork version detects 12% more novel findings but introduces 8% false positives"*
5. You decide: merge, reject, or run both in parallel

**Tier 3 — Block**: Conflicting changes to DAG dependencies. **Never auto-merged.** You see both versions side-by-side and resolve manually.

No other tool does this. Spring AI explicitly calls out "limited skill versioning" as a known gap. This fills it.

### Protocol-Based Backend Architecture

Every backend is a Python `Protocol` — swap implementations without changing any other code:

```
StorageBackend (write / read / search / traverse / delete / list_by_profile)
    ├── SQLite (default) — local, zero-config
    ├── Postgres + pgvector — production scale, native vector search
    └── Stub — in-memory, for testing

EmbeddingBackend (encode / encode_batch / similarity)
    ├── Jina v3 (default) — local, free, 570M params
    ├── OpenAI text-embedding-3 — cloud, pay-per-call
    └── Stub — deterministic hash-based, for testing

RegistryBackend (save / get / fork / list_versions / get_diff)
    ├── Git local (default) — real git commits, branches = forks
    ├── GitHub remote — team collaboration
    └── Stub — in-memory, for testing
```

### Skill Profile Schema

A skill is a **directory bundle**, not a single file:

```
skills/supervised-db-research/
├── profile.yaml      # Machine-executable config (parsed, versioned, merged)
├── skill.md          # Human docs (never parsed, travels with the bundle)
├── tools/            # Tool implementations (inherited via reference, not copied)
├── refs/             # Reference documents (same inheritance rule)
└── tests/            # Evaluation data
```

Forks inherit everything by reference. Only overrides are stored. This is Git's content-addressable model applied to skill bundles — a fork that changes one extraction rule stores only that rule, not the entire profile.

### MCP Integration

ContextLedger connects via **MCP (Model Context Protocol)** — one server, all interfaces:

```
AI Interface session ends
    → MCP hook fires
    → ContextLedger MCP server receives session log
    → CMV snapshot + lossless trim
    → Signal extraction (assistant messages → findings)
    → Three-tier memory storage
    → Queryable immediately
```

Five MCP tools exposed:
- `ctx_ingest(session_log)` — capture a session
- `ctx_query(query, profile)` — search across memory tiers
- `ctx_grep(pattern)` — pattern match on findings
- `ctx_status()` — current profile, session count, memory stats
- `skill_checkout(name, version)` — switch active profile

---

## Usage

### Mode 1: Second Brain (Zero-Config)

No setup needed. Just connect your AI interface and start capturing context.

```python
from contextledger.mcp.server import ContextLedgerMCP

server = ContextLedgerMCP()

# Ingest a session (happens automatically via MCP in practice)
session = {
    "session_id": "session-001",
    "messages": [
        {"role": "user", "content": "What tables are in the database?"},
        {"role": "assistant", "content": "The database has 3 tables: users, orders, products."},
        {"role": "user", "content": "Any missing indexes?"},
        {"role": "assistant", "content": "The users table has no index on the email column."},
    ]
}
result = server.ctx_ingest(session)
# {'status': 'ok', 'signals_extracted': 2}

# Ingest more sessions over time — from Claude Code, Chat, Cursor, etc.
server.ctx_ingest(another_session)
server.ctx_ingest(yet_another_session)

# Query across all sessions
results = server.ctx_query("missing indexes")
# Returns relevant findings from any session

# Search findings by pattern
results = server.ctx_grep("users table")

# Check what's been captured
status = server.ctx_status()
# {'active_profile': None, 'sessions_ingested': 3, 'total_units': 6, ...}
```

Second brain mode works because:
- The MCP server stores every assistant response in three-tier memory
- Queries automatically route to the right tier (immediate/synthesis/archival)
- CMV trimming compresses heavy sessions (tool outputs, base64 images) losslessly
- No skill profile needed — all context is captured and searchable

### Mode 2: Skill Versioning

Define a skill profile, fork it for different domains, merge improvements back.

**Step 1: Create a base profile**

```bash
ctx init
ctx new supervised-db-research
# > Data source: database
# > Entity types: table, column, finding, hypothesis
# > Domain: data analysis
```

Or write `profile.yaml` directly:

```yaml
name: supervised-db-research
version: 1.0.0
parent: null

extraction:
  entities: [table, column, finding, hypothesis]
  sources: [supervised_database]
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

session_context:
  mode: skill_versioning
  cmv_enabled: true
  trim_threshold: 0.3
```

**Step 2: Fork for a new domain**

```bash
ctx fork supervised-db-research filesystem-research
```

Edit the fork to override what's different:

```yaml
# filesystem-research/profile.yaml
name: filesystem-research
version: 1.0.0-fork-1
parent: supervised-db-research

extraction:
  sources: [filesystem]
  entities: [file, directory, finding]
# Everything else inherited from parent
```

**Step 3: Iterate independently**

Work with each profile separately. ContextLedger tracks findings per profile.

```bash
ctx checkout supervised-db-research   # work on DB research
ctx checkout filesystem-research      # switch to filesystem research
```

**Step 4: Merge improvements back**

```bash
ctx diff filesystem-research supervised-db-research
ctx merge filesystem-research supervised-db-research
```

The merge uses three-tier conflict resolution:
- **Tier 1** (auto-merge): non-overlapping changes merge silently
- **Tier 2** (evaluation): overlapping template changes get scored — you see a report with precision/recall/novelty metrics
- **Tier 3** (blocked): conflicting DAG dependencies require your explicit decision

**Step 5: Resolve inheritance programmatically**

```python
from contextledger.skill.parser import ProfileParser
from contextledger.skill.fork import ForkManager

parser = ProfileParser()
mgr = ForkManager()

# Parse profiles
parent = parser.parse(open("supervised-db-research/profile.yaml").read())
child = parser.parse(open("filesystem-research/profile.yaml").read())

# Resolve: child overrides merge on top of parent defaults
registry = {"supervised-db-research": parent}
resolved = mgr.resolve(child, registry=registry)

# resolved has all sections — parent provides base, child overrides win
print(resolved["extraction"]["sources"])  # ['filesystem']
print(resolved["memory_schema"])          # inherited from parent
```

### Using Both Modes Together

Both modes use the same infrastructure and can run simultaneously:

```python
server = ContextLedgerMCP()

# Second brain: capture everything
server.ctx_ingest(session_log)

# Skill versioning: switch to a profile for domain-specific work
server.skill_checkout("supervised-db-research")

# Queries still work across all captured context
results = server.ctx_query("database schema anomalies")
```

Set `mode: combined` in your profile's `session_context` to use both simultaneously:

```yaml
session_context:
  mode: combined
  cmv_enabled: true
```

---

## Architecture

```
User Interfaces (Claude Code, Chat, Cursor, OpenAI, Perplexity)
    ↓ MCP (Model Context Protocol)
Ingestion Layer → Signal Extraction
    ↓
Context Management (CMV DAG + Three-Tier Memory)
    ↓
Skill Profile Layer (YAML profiles, DAG executor, fork/merge)
    ↓
Pluggable Backends (Storage, Embedding, Registry — all Protocol-based)
```

### Three-Tier Memory

| Tier | Content | Retrieval |
|------|---------|-----------|
| **Immediate** | Verbatim last N turns | Direct lookup |
| **Synthesis** | Compressed findings from past week | Semantic search |
| **Archival** | Full history with embeddings | Embedding similarity |

### CMV (Contextual Memory Virtualisation)

DAG-based session history with snapshot/branch/trim primitives. Achieves 20-86% token reduction through lossless three-pass trimming (tool output stripping, base64 removal, metadata normalization).

### Conflict Resolution Tiers

| Tier | Condition | Action |
|------|-----------|--------|
| **1** | Non-overlapping or identical changes | Auto-merge |
| **2** | Same section, different logic | Semantic evaluation (precision/recall/novelty scoring) |
| **3** | Conflicting DAG dependencies | **Block** — always requires manual resolution |

### Pluggable Backends

All backends are Python `Protocol` classes — swap implementations freely:

| Backend | Default | Alternatives |
|---------|---------|-------------|
| Storage | SQLite | Postgres + pgvector |
| Embedding | Jina v3 (local) | OpenAI text-embedding-3 |
| Registry | Git (local) | GitHub remote |

---

## Project Structure

```
contextledger/
├── core/
│   ├── types.py          # MemoryUnit, SkillBundle, ProfileMetadata, ProfileDiff
│   └── protocols.py      # StorageBackend, EmbeddingBackend, RegistryBackend
├── memory/
│   ├── cmv.py            # CMV DAG engine (snapshot, branch, trim)
│   ├── tiers.py          # Three-tier memory router
│   └── trimmer.py        # Lossless three-pass trimming
├── backends/
│   ├── storage/          # SQLite (default), Postgres, stub
│   ├── embedding/        # Jina (default), OpenAI, stub
│   └── registry/         # Git local (default), GitHub, stub
├── skill/
│   ├── parser.py         # Profile YAML parser + validator
│   ├── dag.py            # DAG executor for synthesis pipelines
│   ├── fork.py           # Fork/inheritance chain resolution
│   └── wizard.py         # Interactive profile generation
├── merge/
│   ├── resolver.py       # Tier 1/2/3 conflict resolution
│   ├── evaluator.py      # Tier 2 semantic evaluation harness
│   └── scorer.py         # Precision/recall/novelty scoring
├── mcp/
│   └── server.py         # MCP server (ingest, query, grep, status)
└── cli/
    └── main.py           # `ctx` CLI entry point
```

---

## Running Tests

### Full test suite

```bash
pytest tests/ -v
```

Current status: **214 passed, 4 skipped**.

### Running the Jina embedding tests

The 4 skipped tests are for the Jina embedding backend. They skip automatically when `jina-embeddings` is not installed. To run them:

```bash
pip install jina-embeddings
pytest tests/backends/embedding/test_jina.py -v
```

These tests verify:
- `encode()` returns a valid float vector
- `encode_batch()` produces correct number of vectors
- `similarity()` returns values in [-1, 1]
- Semantically similar texts produce higher similarity than unrelated texts

### Running tests for specific layers

```bash
# Core types and protocols
pytest tests/core/ -v

# Memory layer (CMV, tiers, trimmer)
pytest tests/memory/ -v

# All backends
pytest tests/backends/ -v

# Skill layer (parser, DAG, fork)
pytest tests/skill/ -v

# Merge layer (scorer, resolver, evaluator)
pytest tests/merge/ -v

# MCP server
pytest tests/mcp/ -v

# CLI
pytest tests/cli/ -v

# Integration tests
pytest tests/integration/ -v
```

### Running tests for optional backends

The Postgres, OpenAI, and GitHub backends require external services:

```bash
# Postgres (requires running PostgreSQL with pgvector)
export DATABASE_URL="postgresql://user:pass@localhost/contextledger"
pytest tests/backends/storage/test_postgres.py -v

# OpenAI embeddings (requires API key)
export OPENAI_API_KEY="sk-..."
pytest tests/backends/embedding/test_openai.py -v

# GitHub registry (requires token and repo)
export GITHUB_TOKEN="ghp_..."
export CONTEXTLEDGER_GITHUB_REPO="owner/repo"
pytest tests/backends/registry/test_github.py -v
```

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `ctx init` | Initialize a ContextLedger registry |
| `ctx new <name>` | Create a new skill profile (interactive wizard) |
| `ctx list` | List all skill profiles |
| `ctx checkout <name>[@version]` | Switch active skill profile |
| `ctx fork <parent> <child>` | Fork a profile for domain-specific iteration |
| `ctx diff <a> <b>` | Compare two profiles section by section |
| `ctx merge <fork> <parent>` | Merge fork back into parent (tier-based resolution) |
| `ctx query <text>` | Query across all memory tiers |
| `ctx status` | Show registry info and active profile |
| `ctx connect <interface>` | Connect to an AI interface via MCP |

---

## Configuration

ContextLedger stores its registry at `CTX_HOME` (default: `~/.contextledger`).

```bash
export CTX_HOME=/path/to/your/registry
ctx init
```

---

## Dependencies

**Required:**
- Python 3.11+
- click
- pyyaml

**Optional (installable extras):**

```bash
pip install contextledger[jina]      # Jina embeddings (local, free)
pip install contextledger[openai]    # OpenAI embeddings
pip install contextledger[postgres]  # Postgres + pgvector storage
pip install contextledger[git]       # GitPython for registry
```

---

## Key Design Decisions

1. **Interface before implementation** — Protocol classes first, backends second
2. **Git for versioning** — don't reinvent it; use Git as the backbone
3. **Inheritance not duplication** — forks store only overrides, reference parent for everything else
4. **Zero-config second brain** — must deliver value without skill profile setup
5. **Pluggable everything** — storage, embeddings, registry all swappable via Protocol
6. **Evaluation harness from day one** — semantic merge scoring (precision/recall/novelty) is the key differentiator
7. **Tier 3 never auto-merges** — conflicting DAG dependencies always block and require human resolution

---

## License

TBD
