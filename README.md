# ContextLedger

**Skill versioning and context synthesis for AI engineers working across multiple domains and interfaces.**

---

## The Problem

You build a workflow—extraction rules, reasoning logic, synthesis templates—for one domain. It works. Now you need to adapt it for a different domain. So you copy the files, make changes, and now you have two versions floating around with no clear relationship. Later you fix a synthesis bug in the second version and want that fix in the original too. You have no way to do that cleanly.

Meanwhile, your research context is fragmented. You found something important in a Claude Code session three days ago. You're in Claude Chat now and can't access it. You switch to Cursor tomorrow and lose that thread again.

These are two versions of the same problem: **your work doesn't persist across iterations and interfaces.**

ContextLedger solves both.

### Domain-Agnostic Design

ContextLedger doesn't assume what you're extracting, reasoning about, or synthesizing. The profile schema is generic:

- `extraction.sources` can be database, filesystem, API, document store, sensor stream, etc.
- `extraction.entities` can be database tables, files, API endpoints, document types, etc.
- `synthesis.dag` defines the computational pipeline — same structure regardless of domain

The examples in this README use generic names for concreteness. Your use cases may be completely different. The architecture is the same.

---

## What ContextLedger Is

ContextLedger is two things built on the same infrastructure:

**1. Skill Versioning** — Fork a workflow for a new domain, iterate independently, merge improvements back with semantic conflict resolution that understands whether a change actually improves findings, not just whether the text differs. Works for any workflow with configurable extraction, reasoning, and synthesis steps:

- Agent testing frameworks (fork rules per target type)
- Data pipelines (fork extraction logic per data source)
- RAG systems (fork retrieval strategies per knowledge domain)
- Document processors (fork parsing rules per document type)
- Research workflows (fork analysis rules per research question)

The profile schema is generic — `extraction.sources` can be anything (database, filesystem, API, sensor stream), `extraction.entities` can be anything (tables, files, endpoints, document types), and `synthesis.dag` defines the computational pipeline regardless of domain.

**2. Second Brain** — A unified context layer across all your AI interfaces. Claude Code, Claude Chat, Cursor, OpenAI, Perplexity — every session feeds into one memory. Query across all of it from anywhere. Zero configuration required.

---

## What ContextLedger Is NOT

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

ContextLedger uses Git. Skill versions are commits. Forks are branches. You get all of Git's guarantees — history, diff, rollback — plus semantic understanding layered on top.

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
ctx init
```

---

## Skill Versioning (Any Workflow)

Define a workflow profile for any domain, fork it for other domains, iterate and merge with semantic conflict resolution.

**Example: Agent Testing Framework**

You have extraction rules for testing Agent A. You want to fork for Agent B, add domain-specific tests, then merge back improvements to the base testing framework.

### Bring an existing workflow in

**1. Create a profile.yaml:**

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

Map your workflow: `extraction.sources` = where data comes from, `extraction.entities` = what you're looking for, `synthesis.dag` = how you process from extraction → reasoning → synthesis.

**2. Register and fork:**

```bash
ctx checkout my-skill
ctx fork my-skill my-domain-variant
```

Edit the fork to override only what's different:

```yaml
name: my-domain-variant
version: 1.0.0-fork-1
parent: my-skill

extraction:
  sources: [different_source]
  entities: [different_entity, finding]
# everything else inherited from parent
```

**3. Iterate, then merge back:**

```bash
ctx diff my-domain-variant my-skill
ctx merge my-domain-variant my-skill
```

Merge uses tier-based conflict resolution:
- **Tier 1** (auto): non-overlapping changes merge silently
- **Tier 2** (evaluate): overlapping template changes get scored — precision/recall/novelty metrics
- **Tier 3** (block): conflicting DAG dependencies require your explicit decision

### Start from scratch

```bash
ctx new my-skill
# > Data source: your data source (database, filesystem, API, etc.)
# > Entity types: relevant entities for your domain
# > Domain: your domain
```

### Switch versions

```bash
ctx checkout my-skill              # latest
ctx checkout my-skill@1.2.0       # specific version
```

---

## Second Brain (Zero Config)

No skill profile needed. Connect your AI interfaces and query across all sessions.

```python
from contextledger.mcp.server import ContextLedgerMCP

server = ContextLedgerMCP()

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

# Search by pattern
results = server.ctx_grep("API")

# Check memory state
status = server.ctx_status()
```

### Using Both Modes Together

```yaml
session_context:
  mode: combined
  cmv_enabled: true
```

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

### MCP Tools

| Tool | What it does |
|---|---|
| `ctx_ingest` | Capture a session into three-tier memory |
| `ctx_query` | Query across memory tiers (routes by intent) |
| `ctx_grep` | Pattern search across all findings |
| `ctx_status` | Show active profile, sessions ingested, memory stats |
| `skill_checkout` | Switch active skill profile |

---

## Git Integration

Your project repo and skills registry are separate concerns:

```
your-project/           ← your normal Git repo
~/.contextledger/       ← ContextLedger registry (its own Git repo)
    skills/
```

Every `ctx` operation that changes a skill creates a Git commit automatically.

**Skills inside your project repo:**

```bash
export CTX_HOME=./skills-registry
ctx init
```

**Push to GitHub:**

```bash
cd ~/.contextledger
git remote add origin https://github.com/your-org/contextledger-registry
git push -u origin main
```

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
| Embedding | Jina v3 (local, free) | OpenAI text-embedding-3 |
| Registry | Git (local repo) | GitHub remote |

---

## Project Structure

```
contextledger/
├── core/
│   ├── types.py          # MemoryUnit, SkillBundle, ProfileMetadata, ProfileDiff
│   └── protocols.py      # StorageBackend, EmbeddingBackend, RegistryBackend
├── memory/
│   ├── cmv.py            # CMV DAG engine — snapshot, branch, trim
│   ├── tiers.py          # Three-tier memory router
│   └── trimmer.py        # Lossless three-pass trimming
├── backends/
│   ├── storage/          # SQLite, Postgres, stub
│   ├── embedding/        # Jina, OpenAI, stub
│   └── registry/         # Git local, GitHub, stub
├── skill/
│   ├── parser.py         # Profile YAML parser and validator
│   ├── dag.py            # DAG executor
│   ├── fork.py           # Fork/inheritance resolution
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
   - `synthesis.dag` = how you process from extraction → reasoning → synthesis
3. **Create a profile.yaml** with your rules
4. **Fork and iterate** for new domains

ContextLedger will track versions, inheritance, and changes. No assumption about *what* you're working with.

---

## Dependencies

**Required:** Python 3.11+, `click`, `pyyaml`, `mcp`

**Optional extras:**
```bash
pip install contextledger[jina]      # Jina embeddings (local, free)
pip install contextledger[openai]    # OpenAI embeddings
pip install contextledger[postgres]  # Postgres + pgvector storage
pip install contextledger[git]       # GitPython for registry
```

---

## Key Design Decisions

1. **Git as versioning backbone** — don't reinvent it; add semantic understanding on top
2. **Protocol-first** — all backends are swappable without touching other code
3. **Inheritance not duplication** — forks store only overrides
4. **DAG for synthesis pipelines** — dependency conflicts are semantic, not just text diffs
5. **Zero-config second brain** — must deliver value without any skill profile setup
6. **Evaluation harness from day one** — semantic merge scoring is the key differentiator
7. **Tier 3 never auto-merges** — conflicting DAG dependencies always require human resolution

---

## Research Foundations

- **arXiv:2602.22402** — Contextual Memory Virtualisation: DAG-based session history, lossless trimming (20-86% token reduction)
- **arXiv:2602.12430** — Agent Skills: skill security, lifecycle governance, trust framework
- **github.com/martian-engineering/lossless-claw** — Production DAG context with hierarchical summarisation
- **PlugMem (arXiv:2603.03296)** — Knowledge units as propositions and prescriptions

---

## License

TBD
