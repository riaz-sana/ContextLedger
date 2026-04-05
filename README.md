# ContextLedger

**Skill versioning and context synthesis for AI engineers working across multiple domains and interfaces.**

---

## The Problem

You've built a skill — a workflow that extracts findings from a supervised database. It works. Now you need to adapt it for filesystem documents. So you copy the files, make changes, and now you have two versions floating around with no clear relationship. Later you fix a synthesis bug in the filesystem version and want that fix in the original too. You have no way to do that cleanly.

Meanwhile, your research context is fragmented. You found something important in a Claude Code session three days ago. You're in Claude Chat now and can't access it. You switch to Cursor tomorrow and lose that thread again.

These are two versions of the same problem: **your work doesn't persist across iterations and interfaces.**

ContextLedger solves both.

---

## What ContextLedger Is

ContextLedger is two things built on the same infrastructure:

**1. Skill Versioning** — Version control for AI skill profiles. You build a workflow—extraction rules, reasoning logic, synthesis templates—for one domain. You want to fork it for a different domain, iterate independently on each, then merge improvements back without losing reproducibility. ContextLedger supports this for any workflow that has configurable extraction, reasoning, and synthesis steps.

Examples:
- Agent testing frameworks (fork Agent Prober rules per target type)
- Data pipelines (fork extraction logic per data source)
- RAG systems (fork retrieval strategies per knowledge domain)
- Document processors (fork parsing rules per document type)
- Research workflows (fork analysis rules per research question)

**2. Second Brain** — A unified context layer across all your AI interfaces. Claude Code, Claude Chat, Cursor, OpenAI, Perplexity — every session feeds into one memory. Query across all of it from anywhere.

---

## What ContextLedger Is NOT

This matters. Don't confuse it with tools that solve adjacent problems:

| Tool | What it does | Why it's not ContextLedger |
|---|---|---|
| MLflow / PromptLayer / Langfuse | Version prompts and track LLM experiments | They version *prompts*, not *skill bundles* with DAG pipelines, tools, and reference docs. No fork/merge semantics. |
| Mem0 / Supermemory | Personal memory layer for AI chat | No skill versioning. No domain-aware synthesis. No pluggable backends. Consumer-focused. |
| LangGraph / CrewAI | Agent orchestration frameworks | They orchestrate *execution*. ContextLedger versions *configuration and context*. Different layer. |
| Notion / Obsidian | Note-taking and personal knowledge management | Manual capture. No MCP integration. No semantic merge. |
| Git alone | Code versioning | Git doesn't understand skill semantics. It can't tell you whether merging a synthesis rule improves findings. ContextLedger uses Git as its backbone and adds that understanding on top. |

---

## The Gap We're Filling

Spring AI's documentation (January 2026) explicitly states: *"Limited Skill Versioning — there's currently no built-in versioning system for skills. If you update a skill's behavior, all applications using that skill will immediately use the new version."*

No framework today lets you fork a skill, iterate independently per domain, and merge back with evaluation-backed conflict resolution. ContextLedger is that layer.

---

## Domain-Agnostic Design

ContextLedger doesn't assume what you're extracting, reasoning about, or synthesizing. The profile schema is generic:

- `extraction.sources` can be database, filesystem, API, document store, sensor stream, etc.
- `extraction.entities` can be database tables, files, API endpoints, document types, etc.
- `synthesis.dag` defines the computational pipeline — same structure regardless of domain

The examples in this README use database/filesystem for concreteness. Your use cases may be completely different. The architecture is the same.

---

## Core Concepts

Before you start, understand these four things:

### 1. A Skill is a Directory Bundle

A skill isn't a single YAML file. It's a directory:

```
skills/
└── supervised-db-research/
    ├── profile.yaml      ← machine-executable config (what ContextLedger reads)
    ├── skill.md          ← human docs (ignored by the engine)
    ├── tools/            ← tool implementations
    ├── refs/             ← reference documents your skill uses
    └── tests/            ← evaluation data
```

When you fork a skill, **only overrides are stored**. Unchanged files reference the parent via content-addressable lookup — no duplication. This is Git's model applied to skill bundles.

### 2. Git is the Versioning Backbone

ContextLedger doesn't reinvent versioning. It uses Git. Skill versions are commits. Forks are branches. The registry is a Git repo. You get all of Git's guarantees — history, diff, rollback — plus semantic understanding layered on top.

### 3. Why DAG (Directed Acyclic Graph)?

Your skill's synthesis pipeline isn't linear. Extracting entities must happen before building relationships. Building relationships must happen before synthesising findings. The DAG makes these dependencies explicit and inspectable.

When you merge two forks, the conflict resolution engine understands DAG structure. If fork A changes a node that fork B depends on, that's a tier-3 conflict and it blocks. If they changed independent branches of the DAG, it auto-merges. Without the DAG, merge conflicts are just text diffs. With it, they're semantic dependency conflicts.

```
extract_entities  ─→  build_relationships  ─→  synthesise_findings
      ↑                        ↑                         ↑
  runs first          depends on extract          depends on both
```

### 4. Three-Tier Memory

Not all queries need the same memory. ContextLedger routes automatically:

| Query | Routes to | Why |
|---|---|---|
| "What were we just discussing?" | **Immediate** — verbatim last N turns | Fast, exact recall |
| "What did I find yesterday?" | **Synthesis** — compressed recent findings | Time-windowed, good for recent work |
| "What was my original hypothesis about X?" | **Archival** — full semantic history | Long-term, embedding-based search |
| "Show me all findings about X" | **Synthesis + Archival** | Cross-tier aggregation |

---

## Quick Start

```bash
pip install -e ".[dev]"
ctx init
```

---

## Mode 1: Skill Versioning (Any Workflow)

Define a workflow profile for any domain, fork it for other domains, iterate and merge with semantic conflict resolution.

### If you have an existing skill and want to version-control it

This is the most common entry point. You've already built something and want ContextLedger to manage its evolution.

**Step 1: Bring your existing skill in**

Create the directory structure alongside your existing code:

```
my-project/
├── your_existing_code.py
└── skills/
    └── my-existing-skill/
        ├── profile.yaml      ← create this (see schema below)
        ├── skill.md          ← copy your existing docs here
        └── tools/
            └── your_tool.py  ← symlink or copy your existing tools
```

Minimal `profile.yaml` to get started:

```yaml
name: my-existing-skill
version: 1.0.0
parent: null

extraction:
  entities: [finding, hypothesis, decision]
  sources: [your_data_source]

synthesis:
  dag:
    nodes:
      - id: extract_entities
        type: extraction
        depends_on: []
      - id: synthesise_findings
        type: synthesis
        depends_on: [extract_entities]

session_context:
  mode: skill_versioning
  cmv_enabled: true
```

**Step 2: Register it**

```bash
ctx checkout my-existing-skill
ctx status
```

ContextLedger now tracks this skill. Every session you run while this profile is active feeds into its memory graph.

**Step 3: Fork for a new domain**

```bash
ctx fork my-existing-skill my-new-domain-skill
```

Edit `skills/my-new-domain-skill/profile.yaml` to override only what's different:

```yaml
name: my-new-domain-skill
version: 1.0.0-fork-1
parent: my-existing-skill     # declares inheritance

extraction:
  sources: [new_data_source]   # only override what changes
  entities: [file, finding]
# everything else inherited from parent
```

**Step 4: Iterate, then merge back**

```bash
ctx diff my-new-domain-skill my-existing-skill    # see what changed
ctx merge my-new-domain-skill my-existing-skill   # merge improvements back
```

The merge runs tier-based conflict resolution:
- **Tier 1** (auto): non-overlapping changes merge silently
- **Tier 2** (evaluate): overlapping synthesis template changes get scored — you see precision/recall/novelty metrics before deciding
- **Tier 3** (block): conflicting DAG dependencies always require your explicit decision

### If you're starting a new skill from scratch

```bash
ctx new my-research-skill
# > Data source: your data source (database, filesystem, API, etc.)
# > Entity types: relevant entities for your domain
# > Domain: your domain
```

Or fork from a built-in base template:

```bash
ctx fork base-research-skill my-research-skill
```

### Switching between skill versions

```bash
ctx checkout supervised-db-research           # latest
ctx checkout supervised-db-research@1.2.0    # specific version
ctx list supervised-db-research --branches   # see all forks
```

---

## Mode 2: Second Brain (Zero Config)

No skill profile needed. Connect your AI interfaces and start querying across all your sessions.

```python
from contextledger.mcp.server import ContextLedgerMCP

server = ContextLedgerMCP()

# Ingest a session (happens automatically via MCP in practice)
result = server.ctx_ingest({
    "session_id": "session-001",
    "messages": [
        {"role": "user", "content": "What tables are in the database?"},
        {"role": "assistant", "content": "The database has 3 tables: users, orders, products."},
        {"role": "user", "content": "Any missing indexes?"},
        {"role": "assistant", "content": "The users table has no index on the email column."},
    ]
})
# {'status': 'ok', 'signals_extracted': 2}

# Query across all sessions (past week, full history, whatever's relevant)
results = server.ctx_query("missing indexes")

# Search by pattern
results = server.ctx_grep("users table")

# Check memory state
status = server.ctx_status()
```

---

## Using Both Modes Together

Both modes use the same infrastructure. Run them simultaneously:

```bash
ctx checkout supervised-db-research   # activate a skill profile
ctx query "database anomalies"        # queries route through that profile's memory
```

Or set `mode: combined` in your profile:

```yaml
session_context:
  mode: combined
  cmv_enabled: true
```

---

## Git Integration

ContextLedger uses Git as its registry backend. Here's how it sits alongside your existing Git workflow:

**Your project repo and your skills registry are separate concerns:**

```
your-project/           ← your normal Git repo (code, etc.)
~/.contextledger/       ← ContextLedger registry (its own Git repo)
    skills/
        supervised-db-research/
        filesystem-research/
```

ContextLedger manages its own internal Git repo at `CTX_HOME` (default: `~/.contextledger`). You don't need to do anything to get versioning — every `ctx` operation that changes a skill creates a commit automatically.

**If you want your skills inside your project repo:**

```bash
export CTX_HOME=./skills-registry
ctx init
```

Now your skill bundles live in `./skills-registry` which you can commit alongside your code. Same project Git repo, different directory.

**If you want to push your skills registry to GitHub:**

```bash
cd ~/.contextledger
git remote add origin https://github.com/your-org/contextledger-registry
git push -u origin main
```

From then on, `ctx` commands push/pull from GitHub automatically when you use the GitHub registry backend.

**Configuring the GitHub backend:**

```yaml
# ~/.contextledger/config.yaml
registry_backend: github
github_repo: your-org/contextledger-registry
github_token: ${GITHUB_TOKEN}
```

---

## Connecting AI Interfaces via MCP

ContextLedger exposes 5 MCP tools. Configure once per interface, then ingestion is automatic.

### Claude Code

Add to `~/.claude/settings.json` or your project's `.claude/settings.local.json`:

```json
{
  "mcpServers": {
    "contextledger": {
      "command": "python",
      "args": ["-m", "contextledger.mcp.mcp_server"]
    }
  }
}
```

### Cursor

Add to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "contextledger": {
      "command": "python",
      "args": ["-m", "contextledger.mcp.mcp_server"]
    }
  }
}
```

### Any MCP-compatible interface

Point it at `python -m contextledger.mcp.mcp_server`. The five tools it exposes:

| Tool | What it does |
|---|---|
| `ctx_ingest` | Capture a session into three-tier memory |
| `ctx_query` | Query across memory tiers (routes by intent) |
| `ctx_grep` | Pattern search across all findings |
| `ctx_status` | Show active profile, sessions ingested, memory stats |
| `skill_checkout` | Switch active skill profile |

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│         AI Interfaces (Claude, Cursor, OpenAI...)    │
└──────────────────────┬──────────────────────────────┘
                       │ MCP
                       ▼
┌─────────────────────────────────────────────────────┐
│                 Ingestion Layer                      │
│         Session capture → Signal extraction          │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│           Context Management Layer                   │
│    CMV DAG engine │ Three-tier memory │ Trimming      │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│              Skill Profile Layer                     │
│  Profile YAML │ DAG executor │ Fork/merge engine     │
│  Conflict resolution │ Evaluation harness            │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│           Pluggable Backend Layer                    │
│  StorageBackend  │ EmbeddingBackend │ RegistryBackend │
│  (Protocol-based — swap freely)                      │
└─────────────────────────────────────────────────────┘
```

### Pluggable Backends

Every backend is a Python `Protocol`. Swap without touching any other code:

| Backend | Default | Alternatives |
|---|---|---|
| Storage | SQLite (local, zero-config) | Postgres + pgvector |
| Embedding | Jina v3 (local, free, 570M params) | OpenAI text-embedding-3 |
| Registry | Git (local repo) | GitHub remote |

**Why Jina embeddings?** They run locally (no API calls, no cost), outperform older OpenAI embedding models on most benchmarks, and are free to self-host. If you prefer OpenAI embeddings for consistency with existing systems, swap the backend — one config change, nothing else changes.

---

## Project Structure

```
contextledger/
├── core/
│   ├── types.py          # MemoryUnit, SkillBundle, ProfileMetadata, ProfileDiff
│   └── protocols.py      # StorageBackend, EmbeddingBackend, RegistryBackend (Protocol classes)
├── memory/
│   ├── cmv.py            # CMV DAG engine — snapshot, branch, trim
│   ├── tiers.py          # Three-tier memory router
│   └── trimmer.py        # Lossless three-pass trimming (strips tool outputs, base64, metadata)
├── backends/
│   ├── storage/          # SQLite (default), Postgres, stub
│   ├── embedding/        # Jina (default), OpenAI, stub
│   └── registry/         # Git local (default), GitHub, stub
├── skill/
│   ├── parser.py         # Profile YAML parser and validator
│   ├── dag.py            # DAG executor — topological sort, dependency passing
│   ├── fork.py           # Fork/inheritance chain resolution
│   └── wizard.py         # Interactive profile generation
├── merge/
│   ├── resolver.py       # Tier 1/2/3 conflict resolution
│   ├── evaluator.py      # Tier 2 evaluation harness
│   └── scorer.py         # Precision/recall/novelty scoring
├── mcp/
│   └── server.py         # MCP server
└── cli/
    └── main.py           # ctx CLI
```

---

## Current Status

**214 tests passing. Core framework fully implemented.**

| Component | Status |
|---|---|
| Data types and Protocol interfaces | ✅ Ready |
| SQLite storage backend | ✅ Ready |
| Jina embedding backend | ✅ Ready (requires `pip install jina-embeddings`) |
| Git local registry backend | ✅ Ready |
| CMV session engine (snapshot/branch/trim) | ✅ Ready |
| Three-tier memory with intent routing | ✅ Ready |
| Profile YAML parser and validator | ✅ Ready |
| DAG executor (topological sort, dependency passing) | ✅ Ready |
| Fork and inheritance chain resolution | ✅ Ready |
| Conflict resolution (tier 1/2/3) | ✅ Ready |
| Evaluation harness (precision/recall/novelty) | ✅ Ready (stub scoring — full LLM integration in progress) |
| MCP server | ✅ Ready |
| CLI (`ctx`) | ✅ Ready |
| Postgres backend | ✅ Implemented (requires PostgreSQL + pgvector) |
| OpenAI embedding backend | ✅ Implemented (requires API key) |
| GitHub registry backend | ✅ Implemented (requires token + repo) |

**What's placeholder / coming next:**
- DAG node handlers return stub outputs. The executor manages ordering and dependency passing correctly — actual LLM-powered extraction/synthesis per node type is the next integration milestone.
- Evaluation harness uses synthetic scoring. Full template execution against real LLMs is in progress.

---

## Running Tests

```bash
# Full suite
pytest tests/ -v

# By layer
pytest tests/core/ -v
pytest tests/memory/ -v
pytest tests/backends/ -v
pytest tests/skill/ -v
pytest tests/merge/ -v
pytest tests/mcp/ -v
pytest tests/cli/ -v
pytest tests/integration/ -v

# Jina embedding tests (4 skipped by default without jina installed)
pip install jina-embeddings
pytest tests/backends/embedding/test_jina.py -v

# Optional backends (require external services)
export DATABASE_URL="postgresql://user:pass@localhost/contextledger"
pytest tests/backends/storage/test_postgres.py -v

export OPENAI_API_KEY="sk-..."
pytest tests/backends/embedding/test_openai.py -v

export GITHUB_TOKEN="ghp_..."
export CONTEXTLEDGER_GITHUB_REPO="owner/repo"
pytest tests/backends/registry/test_github.py -v
```

---

## CLI Reference

| Command | Description |
|---|---|
| `ctx init` | Initialize a ContextLedger registry |
| `ctx new <name>` | Create a new skill profile (interactive wizard) |
| `ctx list` | List all skill profiles |
| `ctx checkout <name>[@version]` | Switch active skill profile |
| `ctx fork <parent> <child>` | Fork a profile for domain-specific iteration |
| `ctx diff <a> <b>` | Compare two profiles section by section |
| `ctx merge <fork> <parent>` | Merge fork back into parent with tier-based resolution |
| `ctx query <text>` | Query across all memory tiers |
| `ctx status` | Show registry info, active profile, memory stats |
| `ctx connect <interface>` | Connect to an AI interface via MCP |

---

## Bringing Existing Skills/Workflows Into ContextLedger

If you already have a workflow you want to version and fork:

1. **Inventory your workflow**: What are you extracting? What rules govern reasoning? How do you synthesize findings?
2. **Map to profile structure**:
   - `extraction.sources` = where data comes from
   - `extraction.entities` = what you're looking for
   - `extraction.rules` = patterns and confidence thresholds for matching
   - `synthesis.dag` = how you process from extraction → reasoning → synthesis
3. **Create a profile.yaml** with your rules
4. **Fork and iterate** for new domains

ContextLedger will track versions, inheritance, and changes. No assumption about *what* you're working with.

---

## Dependencies

**Required:**
- Python 3.11+
- `click`
- `pyyaml`
- `mcp`

**Optional extras:**
```bash
pip install contextledger[jina]      # Jina embeddings (local, free)
pip install contextledger[openai]    # OpenAI embeddings
pip install contextledger[postgres]  # Postgres + pgvector storage
pip install contextledger[git]       # GitPython for Git registry backend
```

---

## Configuration

ContextLedger stores its registry at `CTX_HOME` (default: `~/.contextledger`).

```bash
export CTX_HOME=/path/to/your/registry
ctx init
```

---

## Key Design Decisions

1. **Git as versioning backbone** — don't reinvent it; add semantic understanding on top
2. **Protocol-first, implementation-second** — all backends are swappable without touching other code
3. **Inheritance not duplication** — forks store only overrides, reference parent for everything else
4. **DAG for synthesis pipelines** — makes dependency conflicts detectable and explicit, not just text diffs
5. **Zero-config second brain** — must deliver value without any skill profile setup
6. **Evaluation harness from day one** — semantic merge scoring is the key differentiator; it can't be bolted on later
7. **Tier 3 never auto-merges** — conflicting DAG dependencies always block and require human resolution

---

## Research Foundations

The architecture draws from:

- **arXiv:2602.22402** — Contextual Memory Virtualisation: DAG-based session history, lossless trimming achieving 20-86% token reduction
- **arXiv:2602.12430** — Agent Skills: skill security, lifecycle governance, trust framework
- **github.com/martian-engineering/lossless-claw** — Production DAG context with hierarchical summarisation
- **PlugMem (arXiv:2603.03296)** — Knowledge units as propositions and prescriptions, not just entities

---

## License

TBD
