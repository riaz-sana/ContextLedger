---
name: contextledger-setup
description: Set up ContextLedger for any project — install, configure backends, discover skills, create project manifest, wire MCP. Use this whenever the user mentions ContextLedger setup, initialisation, configuring backends, connecting MCP, discovering skills, setting up the registry, or asks how to get ContextLedger working. Also trigger when they say things like "set up context tracking", "configure skill versioning", "connect my AI tools", or "I want to version my workflows".
---

You're setting up ContextLedger — a skill versioning and context synthesis tool. The goal is to get from zero to a working setup where sessions are captured, skills are registered, and MCP is connected. Work through these steps in order, reporting what you did after each one. The user shouldn't need to do busywork — handle the commands yourself and only ask them questions that require a decision (like which embedding backend to use).

## Step 1 — Verify Installation

```bash
python -m contextledger --help
```

If this fails, the package isn't installed. Ask where they cloned ContextLedger and run `pip install -e <path>`. If that fails, try creating a venv first (`python -m venv .venv`, activate it, then install). On Windows activation is `.venv\Scripts\activate`, on macOS/Linux it's `source .venv/bin/activate`.

Proceed once `python -m contextledger --help` prints the command list.

## Step 2 — Embedding Backend

This is a privacy decision that affects what data leaves the user's machine. Present all three options clearly and let them choose:

- **Local (recommended)** — `pip install sentence-transformers`. Private, offline, all data stays local. Needs Python 3.11-3.13 (no 3.14 wheel yet).
- **Jina API** — `pip install httpx` + set `JINA_API_KEY` in `.env`. Works on Python 3.14 but sends query text and finding summaries to Jina's servers. Free key at https://jina.ai/api-dashboard/key-manager.
- **OpenAI API** — `pip install openai` + set `OPENAI_API_KEY` in `.env`. Same privacy trade-off as Jina — text goes to OpenAI.

After installing their choice, verify it works:
```bash
python -c "from contextledger.backends.embedding.factory import get_embedding_backend; print(type(get_embedding_backend()).__name__)"
```

If using an API backend, make sure `python-dotenv` is installed (`pip install python-dotenv`) and the API key is in `.env`.

## Step 3 — Initialise Registry

Check if already set up:
```bash
python -m contextledger status
```

If it shows "Home:" and "Profiles:", skip to Step 5.

Otherwise, ask one question: **shared findings or local only?**
- **sqlite** (default) — no setup, works immediately, findings stay local
- **supabase** — team-shareable findings via hosted Postgres. If they choose this, read `references/supabase-setup.md` for the SQL they need to run in the Supabase dashboard, and have them add `SUPABASE_URL` and `SUPABASE_ANON_KEY` to `.env`.

Then run:
```bash
python -m contextledger init
```
Select the chosen backend at the prompt.

## Step 4 — Discover Skills

Look for existing skill definitions in the project:
```bash
find . -path ./.venv -prune -o -name "SKILL.md" -print 2>/dev/null
ls .claude/skills/ 2>/dev/null
```
(On Windows use `dir /s /b SKILL.md` and `dir .claude\skills\`)

Report what you found: "I found N skills: [names]". Extract the skill name from each directory path (e.g. `.claude/skills/code-review/SKILL.md` → `code-review`).

If nothing found, create a starter: `python -m contextledger new default-skill`

## Step 5 — Project Manifest

```bash
python -m contextledger project init
```

Use the current directory name as project name, the discovered skills as the skill list, the first skill as default, and auto-generate routes. Then verify:
```bash
python -m contextledger project status
```

## Step 6 — MCP for Claude Code

Read the current `.claude/settings.local.json` (if it exists). Detect whether a venv is in use by checking for `.venv/` in the project.

Add a `contextledger` entry to `mcpServers` — use the absolute path to the venv python if one exists, otherwise use `python`. The args are `["-m", "contextledger.mcp.mcp_server"]` and env should include `CTX_HOME` pointing to `~/.contextledger`.

Merge into existing settings — never overwrite other MCP server entries.

## Step 7 — Verify API Keys

Check `.env` for required keys:
- `ANTHROPIC_API_KEY` — always needed (DAG execution, Tier 2 merge evaluation)
- `JINA_API_KEY` — only if Jina API was chosen in Step 2
- `OPENAI_API_KEY` — only if OpenAI was chosen in Step 2
- `SUPABASE_URL` + `SUPABASE_ANON_KEY` — only if Supabase was chosen in Step 3

Report which are present and which are missing. For missing ones, tell the user exactly what to add to `.env`.

## Step 8 — Final Check

```bash
python -m contextledger status
python -m contextledger project status
python -m contextledger list
```

Summarise what was set up:
- Registry location
- Skills registered (list them)
- Embedding backend (local/jina-api/openai) with privacy note
- Findings backend (sqlite/supabase)
- MCP status

Then tell them:
1. Restart Claude Code so MCP connects
2. Sessions are captured automatically after that
3. Quick commands: `python -m contextledger query "..."`, `python -m contextledger fork ...`, `python -m contextledger editor`

## Error Recovery

- **git errors on init** — run `git init ~/.contextledger` first
- **Supabase connection fails** — `python -m contextledger configure-findings` to switch to sqlite
- **sentence-transformers won't install** — they're on Python 3.14, offer Jina API or OpenAI instead
- **"EmbeddingBackendNotAvailable"** — Step 2 was skipped, go back
- **MCP not connecting** — test with `python -m contextledger.mcp.mcp_server` directly
