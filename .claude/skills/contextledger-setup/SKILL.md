---
name: contextledger-setup
description: Set up ContextLedger for any project — install, configure backends, discover skills, create project manifest, wire MCP. Use this whenever the user mentions ContextLedger setup, initialisation, configuring backends, connecting MCP, discovering skills, setting up the registry, or asks how to get ContextLedger working. Also trigger when they say things like "set up context tracking", "configure skill versioning", "connect my AI tools", or "I want to version my workflows".
---

You're setting up ContextLedger — a skill versioning and context synthesis tool. The goal is to get from zero to a working setup where sessions are captured, skills are registered, and MCP is connected. Work through these steps in order, reporting what you did after each one. The user shouldn't need to do busywork — handle the commands yourself and only ask them questions that require a decision.

## Step 1 — Verify Installation

```bash
python -m contextledger --help
```

If this fails, the package isn't installed. Ask where they cloned ContextLedger and run `pip install -e <path>`. If that fails, try creating a venv first (`python -m venv .venv`, activate it, then install). On Windows activation is `.venv\Scripts\activate`, on macOS/Linux it's `source .venv/bin/activate`.

Proceed once `python -m contextledger --help` prints the command list.

## Step 2 — Embedding Backend

This is a privacy decision that affects what data leaves the user's machine. Present all four options clearly and let them choose:

- **Local (recommended)** — `pip install sentence-transformers`. Private, offline, all data stays local. Needs Python 3.11-3.13 (no 3.14 wheel yet).
- **Jina API** — `pip install httpx` + set `JINA_API_KEY` in `.env`. Works on Python 3.14 but sends query text and finding summaries to Jina's servers. Free key at https://jina.ai/api-dashboard/key-manager.
- **OpenAI API** — `pip install openai` + set `OPENAI_API_KEY` in `.env`. Text goes to OpenAI.
- **OpenRouter** — `pip install openai` + set `OPENROUTER_API_KEY` in `.env`. Routes to any model via OpenRouter. Optionally set `OPENROUTER_EMBEDDING_MODEL` (default: `openai/text-embedding-3-small`).

After installing their choice, verify it works:
```bash
python -c "from contextledger.backends.embedding.factory import get_embedding_backend; print(type(get_embedding_backend()).__name__)"
```

If using an API backend, make sure `python-dotenv` is installed (`pip install python-dotenv`) and the API key is in the project's `.env` file.

## Step 3 — Storage Backends

ContextLedger uses two separate databases — this matters for privacy and team sharing. Ask the user about BOTH:

### Memory database (personal sessions)

"Where should ContextLedger store your raw session memory? This contains your actual conversations — it should stay private.

- **sqlite (recommended)** — local file at `~/.contextledger/memory.db`. Private, no setup.
- **postgres** — remote Postgres. Only if you have a specific reason."

Almost everyone should pick sqlite here. This data is personal and should not be shared.

### Findings database (synthesised outputs)

"Where should ContextLedger store structured findings? Findings are privacy-safe summaries extracted from your sessions — no raw conversation content. These CAN be shared with your team.

- **sqlite (default)** — local file at `~/.contextledger/findings.db`. Private, no setup needed. Good for solo use.
- **supabase** — hosted Postgres with semantic search. Findings sync across your team. Free tier available. Good for teams.
- **turso** — hosted SQLite (libSQL). Alternative to Supabase."

**If they choose sqlite for findings:** no extra setup needed.

**If they choose supabase:**
1. Tell them to create a free project at https://supabase.com
2. Read `references/supabase-setup.md` and give them the SQL to run in their Supabase SQL editor
3. Have them add `SUPABASE_URL` and `SUPABASE_ANON_KEY` to `.env`

**If they choose turso:**
Have them add `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN` to `.env`.

Then initialise the registry with their choices:
```bash
python -m contextledger init
```
Select the chosen findings backend at the prompt.

## Step 4 — Choose Mode

ContextLedger has two modes that can run simultaneously. Ask the user:

"How do you want to use ContextLedger?

**Second Brain (zero config)** — captures context from all your AI sessions automatically. Query across everything you've discussed in Claude Code, Chat, Cursor, etc. No skill profile needed — just connect MCP and go.

**Skill Versioning** — define extraction rules, synthesis DAGs, and reasoning pipelines for your domain. Fork them per use case, iterate independently, merge improvements back with semantic conflict resolution. This is for when you have a repeatable workflow you want to version and evolve.

**Both (recommended)** — second brain runs in the background capturing everything, while skill versioning gives you structured extraction on top. Most users want both."

- If **second brain only**: skip Step 5 (skill discovery) and Step 6 (project manifest). They just need MCP connected and they're done.
- If **skill versioning** or **both**: continue with Step 5 to discover/create skills.
- Record their choice — you'll reference it in the final summary.

## Step 5 — Discover Skills

**Important:** If you're running inside the ContextLedger repo itself (check for `contextledger/core/protocols.py` in cwd), STOP here. ContextLedger's own repo is not a user project — don't create a project manifest or register skills for it. Tell the user: "You're inside the ContextLedger source repo. To use ContextLedger, cd into your actual project and run this skill there."

Look for existing skill definitions in the project:
```bash
find . -path ./.venv -prune -o -name "SKILL.md" -print 2>/dev/null
ls .claude/skills/ 2>/dev/null
```
(On Windows use `dir /s /b SKILL.md` and `dir .claude\skills\`)

Report what you found: "I found N skills: [names]". Extract the skill name from each directory path (e.g. `.claude/skills/code-review/SKILL.md` → `code-review`).

If nothing found, create a starter: `python -m contextledger new default-skill`

## Step 6 — Project Manifest

Skip this step if user chose "second brain only" in Step 4, or if you're inside the ContextLedger source repo itself.

```bash
python -m contextledger project init
```

Use the current directory name as project name, the discovered skills as the skill list, the first skill as default, and auto-generate routes. Then verify:
```bash
python -m contextledger project status
```

## Step 7 — MCP for Claude Code

Read the current `.claude/settings.local.json` (if it exists). Detect whether a venv is in use by checking for `.venv/` in the project.

Add a `contextledger` entry to `mcpServers` — use the absolute path to the venv python if one exists, otherwise use `python`. The args are `["-m", "contextledger.mcp.mcp_server"]` and env should include `CTX_HOME` pointing to `~/.contextledger`.

Merge into existing settings — never overwrite other MCP server entries.

## Step 8 — Session Capture

`ctx setup` automatically adds two things that enable session capture:

1. **CLAUDE.md instructions** — tells Claude to call `ctx_ingest` at the end of every conversation and to use `ctx_query` when the user asks about previous work. Check that CLAUDE.md contains the `<!-- contextledger:auto-capture -->` marker.

2. **Stop hook** — a reminder in `.claude/settings.local.json` that fires after each response.

If the user ran `ctx setup`, these should already be in place. Verify:
```bash
grep "contextledger:auto-capture" CLAUDE.md 2>/dev/null && echo "CLAUDE.md: OK" || echo "CLAUDE.md: MISSING"
```

If missing, re-run `python -m contextledger setup` — it adds them idempotently.

## Step 9 — Verify API Keys

Check `.env` for required keys:
- `ANTHROPIC_API_KEY` — always needed (DAG execution, Tier 2 merge evaluation)
- `JINA_API_KEY` — only if Jina API was chosen in Step 2
- `OPENAI_API_KEY` — only if OpenAI was chosen in Step 2
- `OPENROUTER_API_KEY` — only if OpenRouter was chosen in Step 2
- `SUPABASE_URL` + `SUPABASE_ANON_KEY` — only if Supabase was chosen in Step 3
- `TURSO_DATABASE_URL` + `TURSO_AUTH_TOKEN` — only if Turso was chosen in Step 3

Report which are present and which are missing. For missing ones, tell the user exactly what to add to `.env`.

## Step 10 — Final Check and Next Steps

```bash
python -m contextledger status
python -m contextledger project status
python -m contextledger list
```

Summarise what was set up:
- Mode: [second brain / skill versioning / both]
- Registry location
- Skills registered (list them, or "none — second brain only")
- Embedding backend (local/jina-api/openai/openrouter) with privacy note
- Memory backend (sqlite — always local, never shared)
- Findings backend (sqlite/supabase/turso) with sharing note
- MCP status

Then give the user concrete next steps based on their MODE and situation:

---

**ContextLedger is ready.** Here's what to do next:

**Restart Claude Code** so the MCP server connects. After restart, sessions are captured automatically.

### If using Second Brain mode:
You're done — just work normally. Every AI session is captured via MCP.
```bash
# Query across all your sessions:
python -m contextledger query "what did I find about the auth bypass"

# Search for specific patterns:
python -m contextledger query "rate limiting decisions from last week"

# Check what's been captured:
python -m contextledger status
```

### If using Skill Versioning — new project:
```bash
# Create your first skill profile:
python -m contextledger new my-skill
# The wizard asks what you're extracting and from where

# Fork it for a different domain:
python -m contextledger fork my-skill my-domain-variant

# Iterate on the fork, then merge improvements back:
python -m contextledger merge my-domain-variant my-skill
```

### If using Skill Versioning — existing project:
```bash
# Import existing Python workflows as skill profiles:
python -m contextledger extract --from my_pipeline.py --output profile.yaml

# Or import an existing Claude Code skill:
python -m contextledger import --from .claude/skills/my-skill/SKILL.md

# Fork for a new domain and iterate:
python -m contextledger fork my-skill my-domain-variant
python -m contextledger diff my-domain-variant my-skill
python -m contextledger merge my-domain-variant my-skill
```

### If using Both modes:
Second brain captures everything in the background. Skill versioning gives you
structured extraction on top. Use `ctx query` for broad context search and
`ctx project query` for skill-aware routing.

### Useful commands:
| Command | What it does |
|---|---|
| `python -m contextledger query "..."` | Search across all your sessions |
| `python -m contextledger fork <parent> <child>` | Fork a skill for a new domain |
| `python -m contextledger merge <fork> <parent>` | Merge improvements back with conflict resolution |
| `python -m contextledger diff <a> <b>` | Compare two skill profiles |
| `python -m contextledger project query "..."` | Query with auto-routing in multi-skill projects |
| `python -m contextledger editor` | Open visual profile editor in browser |
| `python -m contextledger status` | Check registry and memory stats |

---

### Using ContextLedger across multiple projects

After this first-time setup, adding ContextLedger to any other project is one command:

```bash
cd ~/another-project
python -m contextledger setup
```

That's it. It discovers skills, creates the project manifest, and wires MCP.
No re-install, no re-configuring backends or API keys — those are global.

You only need this skill (`/contextledger-setup`) for the first-ever installation.
After that, `python -m contextledger setup` handles everything per project.

---

## Error Recovery

- **git errors on init** — run `git init ~/.contextledger` first
- **Supabase connection fails** — `python -m contextledger configure-findings` to switch to sqlite
- **sentence-transformers won't install** — they're on Python 3.14, offer Jina API or OpenAI/OpenRouter instead
- **"EmbeddingBackendNotAvailable"** — Step 2 was skipped, go back
- **MCP not connecting** — test with `python -m contextledger.mcp.mcp_server` directly
