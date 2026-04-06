# ContextLedger

You iterate AI workflows across multiple domains.
Each domain needs different extraction rules, different synthesis logic, different tools.
You want to merge improvements back without losing reproducibility.
No existing tool handles this.

**ContextLedger does.**

```bash
pip install contextledger
```

### Embedding Backend — Read This First

ContextLedger needs an embedding backend for semantic search (`ctx query`, memory tiers, Tier 2 evaluation). You must choose one:

**Option A — Local embeddings (PRIVATE, recommended)**
```bash
pip install contextledger[jina-local]
```
Uses `sentence-transformers` to run Jina embeddings v3 locally. **All data stays on your machine.** No API calls, no external servers. Requires Python 3.11-3.13 (no 3.14 wheel yet).

**Option B — Jina API (Python 3.14 compatible)**
```bash
pip install contextledger[jina-api]
export JINA_API_KEY=jina_...  # free at https://jina.ai
```
Calls Jina's REST API. Works on any Python version including 3.14. **WARNING: your query text and finding summaries are sent to Jina's servers.** Only use this if you accept that trade-off or are not working with sensitive data.

**Option C — OpenAI API**
```bash
pip install contextledger[openai]
export OPENAI_API_KEY=sk-...
```
Same privacy trade-off as Option B — text is sent to OpenAI's servers.

**Option D — OpenRouter (routes to any model)**
```bash
pip install contextledger[openrouter]
export OPENROUTER_API_KEY=sk-or-...
# Optional: override model (default: openai/text-embedding-3-small)
export OPENROUTER_EMBEDDING_MODEL=openai/text-embedding-3-large
```
Uses the OpenAI-compatible SDK with OpenRouter's endpoint. Access any embedding model available on OpenRouter. Same privacy trade-off — text goes through OpenRouter's servers.

> **Python 3.14 users:** `sentence-transformers` has no 3.14 wheel yet. Your options are the Jina API (Option B), OpenAI (Option C), OpenRouter (Option D), or downgrading to Python 3.12 for local embeddings. We recommend Python 3.12 if privacy matters.

---

### Skill Versioning

Fork a workflow for a new domain. Iterate independently. Merge back with
tier-based conflict resolution — auto-merge for non-overlapping changes,
LLM-evaluated scoring for overlapping synthesis changes (requires ANTHROPIC_API_KEY),
and explicit blocking for conflicting DAG dependencies.

```bash
ctx fork agent-prober-skill agent-prober-telco
# ... iterate on telco-specific extraction rules ...
ctx merge agent-prober-telco agent-prober-skill
# → Tier 2: fork detects 14% more novel findings, precision unchanged → merge recommended
```

### Second Brain

Unified context across Claude Code, Claude Chat, Cursor, OpenAI, Perplexity.
Every session feeds one memory. Query across all of it from anywhere.

```bash
ctx query "what did I find about the authentication bypass last week"
# → retrieves from whichever session, whichever interface
```

### Multi-Skill Projects

One project, many skills, automatic routing. ContextLedger reads your
working directory and routes to the right skill profile automatically.

```bash
# Working in sdk/ → routes to sdk-skill
# Working in analyzer/ → routes to analyzer-skill
ctx project query "how does retry detection work"
# → auto-routed to analyzer-skill, returns relevant findings
```

---

**What this is not:** a prompt manager, a note-taking app, an agent framework,
or a memory widget. See [What ContextLedger Is Not](#what-contextledger-is-not).

---

## What ContextLedger Is Not

| Tool | What it does | Why it's not ContextLedger |
|---|---|---|
| MLflow / PromptLayer / Langfuse | Version prompts and track LLM experiments | They version *prompts*, not *skill bundles* with DAG pipelines, tools, and reference docs. No fork/merge semantics. |
| Mem0 / Supermemory | Personal memory layer for AI chat | No skill versioning. No domain-aware synthesis. No pluggable backends. |
| LangGraph / CrewAI | Agent orchestration frameworks | They orchestrate *execution*. ContextLedger versions *configuration and context*. Different layer. |
| Git alone | Code versioning | Git doesn't understand skill semantics. It can't tell you whether merging a synthesis rule improves findings. ContextLedger uses Git as its backbone and adds that understanding on top. |

Spring AI's documentation (January 2026) explicitly states: *"Limited Skill Versioning — there's currently no built-in versioning system for skills."* No framework today lets you fork a skill, iterate independently per domain, and merge back with evaluation-backed conflict resolution. ContextLedger is that layer.

---

## Core Concepts

### 1. A Skill is a Directory Bundle

```
skills/
└── my-skill/
    ├── profile.yaml      ← machine-executable config (what ContextLedger reads)
    ├── skill.md          ← human docs (ignored by the engine)
    ├── tools/            ← tool implementations
    ├── refs/             ← reference documents
    └── tests/            ← evaluation data
```

When you fork a skill, **only overrides are stored**. Unchanged files reference the parent via content-addressable lookup — no duplication.

### 2. Git is the Versioning Backbone

ContextLedger uses Git. Skill versions are commits. Forks are branches. You get all of Git's guarantees — history, diff, rollback — plus semantic understanding layered on top. Three concrete things this means: (1) section-aware diffing — profiles are compared field by field (extraction.entities, synthesis.dag.nodes, memory_schema.graph_edges), not as raw text; (2) DAG dependency analysis — if a merged change touches a node that downstream nodes depend on, it's flagged as a conflict; (3) Tier 2 evaluation — overlapping synthesis template changes are scored by running both versions against real findings via LLM-as-judge.

### 3. Why DAG?

Your synthesis pipeline isn't linear. The DAG makes dependencies explicit. When you merge two forks, the conflict resolution engine understands DAG structure — if fork A changes a node that fork B depends on, that's a tier-3 conflict and it blocks. If they changed independent branches, it auto-merges.

```
extract_entities  ─→  build_relationships  ─→  synthesise_findings
      ↑                        ↑                         ↑
  runs first          depends on extract          depends on both
```

### 4. Three-Tier Memory

| Query | Routes to | Why |
|---|---|---|
| "What were we just discussing?" | **Immediate** — verbatim last N turns | Fast, exact recall |
| "What did I find yesterday?" | **Synthesis** — compressed recent findings | Time-windowed |
| "What was my original hypothesis about X?" | **Archival** — full semantic history | Embedding-based search |
| "Show me all findings about X" | **Synthesis + Archival** | Cross-tier aggregation |

---

## Quick Start

```bash
pip install -e ".[dev]"
python -m contextledger init
```

---

## Mode 1: Skill Versioning

Works for any workflow you model as a skill profile — you define what to extract,
how to reason about it, and how to synthesise findings. ContextLedger versions,
forks, and merges that configuration.

- Agent testing frameworks (fork rules per target type or environment)
- LLM cost analysis pipelines (fork detector rules per provider or use case)
- Data extraction workflows (fork parsing rules per data source)
- RAG systems (fork retrieval strategies per knowledge domain)
- Document processors (fork parsing rules per document type)
- Research workflows (fork analysis rules per research question)

### Create a profile

```bash
python -m contextledger new my-skill
# > Data source: your data source (database, filesystem, API, etc.)
# > Entity types: relevant entities for your domain
# > Domain: your domain
```

Or write `profile.yaml` directly:

```yaml
name: my-skill
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

### Fork, iterate, merge

```bash
python -m contextledger fork my-skill my-domain-variant
# Edit the fork to override only what's different
python -m contextledger diff my-domain-variant my-skill
python -m contextledger merge my-domain-variant my-skill
```

Merge uses tier-based conflict resolution:
- **Tier 1** (auto): non-overlapping changes merge silently
- **Tier 2** (evaluate): overlapping template changes get scored — precision/recall/novelty metrics
- **Tier 3** (block): conflicting DAG dependencies require your explicit decision

---

## Mode 2: Second Brain (Zero Config)

No skill profile needed. Connect your AI interfaces and query across all sessions.

```python
from contextledger.backends.embedding.factory import get_embedding_backend
from contextledger.mcp.server import ContextLedgerMCP

server = ContextLedgerMCP(embedding_backend=get_embedding_backend())

# Ingest sessions (happens automatically via MCP)
server.ctx_ingest({
    "session_id": "session-001",
    "messages": [
        {"role": "user", "content": "What's the API rate limit?"},
        {"role": "assistant", "content": "The rate limit is 1000 req/min with burst to 2000."},
    ]
})

# Query across all sessions
results = server.ctx_query("rate limit")
```

---

## Mode 3: Multi-Skill Projects

If your project has multiple distinct components — each with its own workflow,
terminology, and context — declare them all in a project manifest.
ContextLedger auto-routes queries to the right skill based on your working directory,
the file you're editing, or keywords in your query.

### Setup

```bash
python -m contextledger project init
```

Or write `.contextledger/project.yaml` directly:

```yaml
name: my-project
version: 1.0.0

skills:
  - extraction-skill
  - analysis-skill
  - reporting-skill

default_skill: analysis-skill
fusion_enabled: true

routes:
  - skill: extraction-skill
    directories: [src/extractors/]
    keywords: [extract, parse, ingest]

  - skill: analysis-skill
    directories: [src/analysis/]
    keywords: [analyze, detect, score]

  - skill: reporting-skill
    directories: [src/reports/]
    keywords: [report, summary, output]
```

### Querying

```bash
# Auto-routes based on cwd + query keywords
python -m contextledger project query "how does entity extraction work"

# Query all skills simultaneously, returns fused results with attribution
python -m contextledger project query "what findings cross extraction and analysis" --all

# Override routing
python -m contextledger project query "detection thresholds" --profile analysis-skill

# Debug routing without running a query
python -m contextledger project route --query "retry waste detector"
# → "analysis-skill (keyword match: detector)"

# Project health
python -m contextledger project status
```

### When to use multi-skill vs single-skill

**Single-skill:** one domain, one workflow, or you're iterating via fork/merge.
**Multi-skill:** distinct components with different terminology, and you want context
from one to surface when querying another.

---

## Adding ContextLedger to a Project

After installing ContextLedger once, set up any project with one command:

```bash
cd ~/my-project
python -m contextledger setup
```

This automatically:
1. Creates the global registry (first time only)
2. Discovers existing skills in your project
3. Creates/updates `.contextledger/project.yaml` with auto-routing
4. Wires MCP into `.claude/settings.local.json`

Second brain is always active (MCP captures sessions). Skill versioning activates when you add skills — no mode flag needed. Safe to re-run anytime:

```bash
python -m contextledger setup          # full setup
python -m contextledger setup --no-mcp # skip MCP wiring

# Add skill versioning to a project that started with just second brain:
python -m contextledger new my-skill
python -m contextledger setup          # re-run picks up the new skill
```

### First-time setup with Claude Code Skill

For the initial installation (choosing embedding backend, findings backend, API keys), use the interactive skill:

```
/contextledger-setup
```

This walks through every decision. After that, `python -m contextledger setup` is all you need per project.

---

## Connecting AI Interfaces via MCP

Configure once per interface, then ingestion is automatic.

### Claude Code

Add to `~/.claude/settings.json` or `.claude/settings.local.json`:

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

### MCP Tools

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
| Embedding | Jina v3 local (private, offline) | Jina API, OpenAI API (send data to servers) |
| Registry | Git (local repo) | GitHub remote |
| LLM | Claude (via Anthropic API) | Any LLMClient implementation |

---

## Current Status

| Component | Status |
|---|---|
| Core types and protocols | Done |
| Three-tier memory + CMV | Done |
| Default backends (SQLite, Jina, Git) | Done |
| Skill profiles (parser, DAG executor, fork/merge) | Done |
| Conflict resolution tier 1 (auto-merge) | Done |
| Conflict resolution tier 2 (LLM evaluation) | Done |
| Conflict resolution tier 3 (block + manual) | Done |
| Evaluation harness (precision/recall/novelty + LLM-as-judge) | Done |
| MCP server | Done |
| CLI (`ctx` commands) | Done |
| Multi-skill project manifests (Phase 2) | Done |
| Skill extractors (Phase 3) | Done |
| Visual editor | Done |
| VS Code extension | Done |
| GitHub Actions | Done |
| LangChain integration | Done |

**316 tests passing, 0 skipped.**

---

## CLI Reference

| Command | Description |
|---|---|
| `ctx init` | Initialize a ContextLedger registry (with git) |
| `ctx new <name>` | Create a new skill profile (interactive wizard) |
| `ctx list` | List all skill profiles |
| `ctx checkout <name>[@version]` | Switch active skill profile |
| `ctx fork <parent> <child>` | Fork a profile for domain-specific iteration |
| `ctx diff <a> <b>` | Compare two profiles section by section |
| `ctx merge <fork> <parent>` | Merge fork back into parent with tier-based resolution |
| `ctx query <text>` | Query across all memory tiers |
| `ctx status` | Show registry info, active profile, memory stats |
| `ctx extract --from <file>` | Generate profile from Python code |
| `ctx import --from <skill.md>` | Import Claude Code skill as profile |
| `ctx project init` | Initialize a multi-skill project |
| `ctx project query <text>` | Query with auto-routing |
| `ctx project status` | Show project and skill health |
| `ctx editor` | Launch visual profile editor in browser |

---

## Key Design Decisions

1. **Git as versioning backbone** — don't reinvent it; add semantic understanding on top
2. **Protocol-first** — all backends are swappable without touching other code
3. **Inheritance not duplication** — forks store only overrides
4. **DAG for synthesis pipelines** — dependency conflicts are semantic, not just text diffs
5. **Zero-config second brain** — must deliver value without any skill profile setup
6. **Evaluation harness from day one** — semantic merge scoring is the key differentiator
7. **Tier 3 never auto-merges** — conflicting DAG dependencies always require human resolution
8. **No silent fallback to stubs** — production paths fail loudly with clear instructions

---

## Dependencies

**Core:** Python 3.11+, `click`, `pyyaml`, `gitpython`, `anthropic`, `mcp`

**Embedding backend (pick one):**
```bash
pip install contextledger[jina-local]  # Local, private, offline (Python 3.11-3.13)
pip install contextledger[jina-api]    # Jina API, needs JINA_API_KEY (any Python)
pip install contextledger[openai]      # OpenAI API, needs OPENAI_API_KEY
```

**Other optional extras:**
```bash
pip install contextledger[supabase]    # Shared findings backend
pip install contextledger[postgres]    # Postgres + pgvector storage
pip install contextledger[editor]      # Visual profile editor (FastAPI)
pip install contextledger[langchain]   # LangChain callback handler
```

---

## Research Foundations

- **arXiv:2602.22402** — Contextual Memory Virtualisation: DAG-based session history, lossless trimming (20-86% token reduction)
- **arXiv:2602.12430** — Agent Skills: skill security, lifecycle governance, trust framework
- **github.com/martian-engineering/lossless-claw** — Production DAG context with hierarchical summarisation
- **PlugMem (arXiv:2603.03296)** — Knowledge units as propositions and prescriptions

---

## License

TBD
