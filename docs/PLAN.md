# ContextLedger — Implementation Plan

> Reference: [contextledger-architecture.md](contextledger-architecture.md) for full architectural decisions.

---

## Project Summary

ContextLedger is a universal context layer and skill versioning platform for research engineers working across multiple AI interfaces. It operates in two modes:

- **Second Brain Mode**: Zero-config context capture across AI interfaces via MCP
- **Skill Versioning Mode**: Fork/merge skill profiles with semantic conflict resolution

---

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Language | Python 3.11+ | Type-hinted, Protocol-based interfaces |
| Storage (default) | SQLite + semantic index | Swappable via `StorageBackend` protocol |
| Embeddings (default) | Jina embeddings v3 | Swappable via `EmbeddingBackend` protocol |
| Registry (default) | Git (local, via `gitpython`) | Swappable via `RegistryBackend` protocol |
| Session management | CMV DAG engine | Based on arXiv:2602.22402 |
| Integration | MCP (Model Context Protocol) | Universal ingestion interface |
| CLI | `click` | `ctx` command with subcommands |
| Testing | `pytest` | Interface-first test design |
| Packaging | `pyproject.toml` / `pip` | `pip install contextledger` |

---

## Core Modules

```
contextledger/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── types.py              # MemoryUnit, SkillBundle, ProfileMetadata, ProfileDiff
│   └── protocols.py          # StorageBackend, EmbeddingBackend, RegistryBackend
├── memory/
│   ├── __init__.py
│   ├── cmv.py                # CMV DAG engine (snapshot, branch, trim)
│   ├── tiers.py              # Three-tier memory router (immediate/synthesis/archival)
│   └── trimmer.py            # Lossless three-pass trimming algorithm
├── backends/
│   ├── __init__.py
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── sqlite.py         # SQLite StorageBackend implementation
│   │   └── stub.py           # Mock/stub for testing
│   ├── embedding/
│   │   ├── __init__.py
│   │   ├── jina.py           # Jina EmbeddingBackend implementation
│   │   └── stub.py           # Mock/stub for testing
│   └── registry/
│       ├── __init__.py
│       ├── git_local.py      # Git (local) RegistryBackend implementation
│       └── stub.py           # Mock/stub for testing
├── skill/
│   ├── __init__.py
│   ├── parser.py             # Profile YAML parser and validator
│   ├── dag.py                # DAG executor for synthesis pipelines
│   ├── fork.py               # Fork/inheritance chain resolution
│   └── wizard.py             # Interactive profile generation wizard
├── merge/
│   ├── __init__.py
│   ├── resolver.py           # Tier 1/2/3 conflict resolution router
│   ├── evaluator.py          # Tier 2 semantic evaluation harness
│   └── scorer.py             # Precision/recall/novelty scoring
├── mcp/
│   ├── __init__.py
│   └── server.py             # MCP server (ingest, query, grep, status, checkout)
└── cli/
    ├── __init__.py
    └── main.py               # Click CLI (ctx init/new/checkout/fork/diff/merge/query/status/connect)
```

---

## Phased Build Order

### Phase 1: Interface Contracts (Weeks 1-2)
- [ ] Define data types in `core/types.py`
- [ ] Define Protocol classes in `core/protocols.py`
- [ ] Write stub backends returning mock data
- [ ] Write tests against interfaces (not implementations)

### Phase 2: CMV Session Layer (Weeks 3-4)
- [ ] Implement CMV DAG engine (snapshot, branch, trim)
- [ ] Implement three-pass lossless trimming
- [ ] Wire into SQLite storage stub
- [ ] Test on real session logs

### Phase 3: Default Backends (Weeks 5-6)
- [ ] SQLite `StorageBackend`
- [ ] Jina `EmbeddingBackend`
- [ ] Git (local) `RegistryBackend`
- [ ] Run interface tests against real implementations

### Phase 4: Skill Profile Layer (Weeks 7-8)
- [ ] Profile YAML parser/validator
- [ ] DAG executor (sequential first)
- [ ] Fork primitive with inheritance resolution
- [ ] Skill bundle directory structure
- [ ] Interactive wizard

### Phase 5: MCP Ingestion Server (Weeks 9-10)
- [ ] MCP server with ingestion and query tools
- [ ] Claude Code integration
- [ ] Claude Chat support
- [ ] End-to-end second brain mode test

### Phase 6: CLI (Weeks 11-12)
- [ ] All CLI commands: init, new, checkout, fork, diff, merge, query, status, connect
- [ ] Package as `pip install contextledger`
- [ ] Quickstart README

### Phase 7: Conflict Resolution (Month 2)
- [ ] Evaluation harness (findingsstore, runner, scorer)
- [ ] Tier 1 auto-merge
- [ ] Tier 2 semantic evaluation
- [ ] Tier 3 manual override

### Phase 8: Additional Backends (Month 2+)
- [ ] Postgres + pgvector StorageBackend
- [ ] OpenAI EmbeddingBackend
- [ ] GitHub remote RegistryBackend
- [ ] Cursor and OpenAI MCP integration

---

## Key Constraints

1. **Interface before implementation** — Protocol classes first, backends second
2. **Git for versioning** — do not reinvent it
3. **Inheritance not duplication** — forks store only overrides
4. **Zero-config second brain** — must work without skill profile setup
5. **Pluggable everything** — storage, embeddings, registry all swappable
6. **Evaluation harness from day one** — required for semantic merge (the key differentiator)
