# ContextLedger — Session Handover

> This file is the source of truth for any new Claude Code session entering this project.
> Read this FIRST, then `PLAN.md`, then `contextledger-architecture.md` if you need deep detail.

---

## Project Identity

ContextLedger is a **universal context layer and skill versioning platform** for AI interfaces.
Two modes: Second Brain (zero-config memory across AI sessions) and Skill Versioning (fork/merge skill profiles with semantic conflict resolution).

- **Language**: Python 3.11+, type-hinted, Protocol-based
- **Testing**: pytest, interface-first (test against protocols, not implementations)
- **Packaging**: pyproject.toml, CLI entry point is `ctx`
- **Key principle**: Interface contracts before implementations. Always.

---

## Current State

### What Exists
- `contextledger-architecture.md` — full architecture document (the spec, do NOT modify without explicit instruction)
- `PLAN.md` — phased build order, tech stack, module map
- `tasks.json` — task queue for tracking implementation work
- `contextledger/` — full source tree scaffolded with docstring-only placeholder modules
- `tests/` — full test tree scaffolded, mirrors source structure 1:1 + integration tests
- `pyproject.toml` — packaging config with `ctx` CLI entry point
- `.gitignore` — standard Python ignores

### What Does NOT Exist Yet
- No actual implementation code (all modules are docstring stubs)
- No initial git commit (repo initialized but empty history)
- No dependencies installed
- No CI/CD pipeline

---

## Architecture Quick Reference

```
User Interfaces (Claude Code, Chat, Cursor, OpenAI, Perplexity)
    ↓ MCP
Ingestion Layer → Signal Extraction
    ↓
Context Management (CMV DAG + Three-Tier Memory)
    ↓
Skill Profile Layer (YAML profiles, DAG executor, fork/merge)
    ↓
Pluggable Backends (Storage, Embedding, Registry — all Protocol-based)
```

### Three Backend Protocols (the foundation)
1. **StorageBackend** — write/read/search/traverse/delete/list_by_profile
2. **EmbeddingBackend** — encode/encode_batch/similarity
3. **RegistryBackend** — list_profiles/get_profile/save_profile/fork_profile/list_versions/get_diff

### Core Data Types
- `MemoryUnit` — single unit of stored context
- `SkillBundle` — directory bundle (profile.yaml + tools + refs + tests)
- `ProfileMetadata` — name, version, parent, timestamps
- `ProfileDiff` — semantic diff between two profiles

### Three-Tier Memory
- **Immediate**: verbatim last N turns (in-memory/SQLite)
- **Synthesis**: compressed findings from recent window (semantic index)
- **Archival**: full history with embeddings (full StorageBackend)

### CMV (Contextual Memory Virtualisation)
- DAG-based session history with snapshot/branch/trim primitives
- Three-pass lossless trimming (strips tool bloat, keeps user/assistant messages)
- 20-86% token reduction

### Conflict Resolution Tiers
- **Tier 1**: Auto-merge (non-overlapping changes)
- **Tier 2**: Semantic evaluation (run both versions, score, recommend)
- **Tier 3**: Manual override (block merge, require human resolution)

---

## Build Order (Phases)

| Phase | Focus | Status |
|-------|-------|--------|
| 1 | Interface contracts (types.py, protocols.py, stubs) | NOT STARTED |
| 2 | CMV session layer (DAG engine, trimmer) | NOT STARTED |
| 3 | Default backends (SQLite, Jina, Git local) | NOT STARTED |
| 4 | Skill profile layer (parser, DAG executor, fork) | NOT STARTED |
| 5 | MCP ingestion server | NOT STARTED |
| 6 | CLI (`ctx` commands) | NOT STARTED |
| 7 | Conflict resolution (evaluation harness) | NOT STARTED |
| 8 | Additional backends (Postgres, OpenAI, GitHub) | NOT STARTED |

**Current phase**: Phase 1 — Interface Contracts

---

## What Worked

- Scaffolding the full source + test tree upfront avoids structural churn later
- Architecture doc as single source of truth prevents drift between sessions
- Protocol-first design (from the architecture doc) is the right call — test against interfaces, swap implementations freely
- tasks.json as a structured queue keeps work trackable across sessions
- Mirroring test structure 1:1 with source makes it obvious where tests go

## What Didn't Work / Watch Out For

- Nothing has failed yet (project just scaffolded), but these are known risks:
  - **Do NOT start implementing backends before protocols are locked** — the architecture doc is explicit about this
  - **Do NOT copy files in forks** — inheritance by reference only, copy-on-write when modified
  - **Do NOT auto-merge tier 3 conflicts** — always block and require human resolution
  - **Do NOT skip the evaluation harness** — it's the key differentiator, must exist from day one
  - **Do NOT hardcode any backend** — even SQLite default must go through the StorageBackend protocol

## Important Decisions Already Made

1. Git is the versioning backbone — do not reinvent versioning
2. Jina embeddings v3 is the default embedding backend (local, free, performant)
3. Skill profiles are directory bundles, not single files
4. Fork inheritance is copy-on-write with content-addressable references
5. MCP is the universal integration protocol — one server, all AI interfaces
6. CMV is always-on by default (cmv_enabled: true in profile.yaml)
7. Second brain mode requires zero configuration to deliver value
8. profile.yaml is machine-executable; skill.md is human docs only — never parse skill.md

## Coding Conventions

- All backend interfaces are Python `Protocol` classes
- Data types use `dataclass` or `NamedTuple` (prefer dataclass for mutability)
- Tests are written against interfaces first, then run against real implementations
- No hardcoded backends — always go through protocol interface
- CLI uses `click` library
- Use `pytest` fixtures for backend injection (same test suite, different backends)
- Keep modules separated — ingestion, memory, skill, merge layers do NOT import each other's internals

## Key Files to Read

| File | Purpose |
|------|---------|
| `CLAUDE.md` | This file. Start here. |
| `PLAN.md` | Build order, tech stack, module map |
| `contextledger-architecture.md` | Full spec. The source of truth for all design decisions. |
| `tasks.json` | Current task queue. Check before starting work. |
| `contextledger/core/protocols.py` | Backend interfaces (implement these first) |
| `contextledger/core/types.py` | Data types (implement these first) |
| `tests/conftest.py` | Shared fixtures |

---

## Session Checklist

When starting a new session:
1. Read this file
2. Check `tasks.json` for the current queue
3. Check `PLAN.md` for which phase is active
4. Check git status / recent commits for what changed since last session
5. Pick up the next task or ask the user what to focus on
