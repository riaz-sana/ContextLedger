# ContextLedger — Positioning & README Opening

Two things in this file:
1. Tightened README opening (replace the current one in README.md)
2. Positioning document (for pitching to people, teams, investors)

---

## Part 1: New README Opening

Replace everything from the top of README.md down to "## The Problem" with this:

---

# ContextLedger

You iterate AI workflows across multiple domains.
Each domain needs different extraction rules, different synthesis logic, different tools.
You want to merge improvements back without losing reproducibility.
No existing tool handles this.

**ContextLedger does.**

```bash
pip install contextledger
```

---

### Skill Versioning

Fork a workflow for a new domain. Iterate independently. Merge back with
semantic conflict resolution that scores whether your changes actually
improve findings — not just whether the text differs.

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

## Part 2: Positioning Document

**For pitching ContextLedger to people, teams, or investors.**
This is not for the README. It's for conversations, decks, and emails.

---

### The One-Sentence Pitch

> ContextLedger is the missing infrastructure layer for AI engineers who
> iterate research workflows across multiple domains and need reproducibility,
> version control, and semantic merge — not just logging and tracing.

---

### The Problem (Two Minutes)

**Problem 1: Workflow iteration without reproducibility**

AI engineers build workflows — extraction pipelines, reasoning chains,
synthesis templates — then iterate them across different domains.
A security researcher runs the same investigation workflow against
telco targets, healthcare systems, and financial infrastructure.
An ML engineer tests the same RAG retrieval strategy across
medical literature, legal documents, and news articles.

Every iteration is a fork. Every improvement discovered in one domain
potentially applies to others. But today there's no infrastructure for
managing this. Teams either maintain parallel copies with no clear lineage,
or they conflate domains into one monolithic workflow and lose the ability
to specialize.

**Problem 2: Context fragmentation**

The same engineer works across Claude Code, Claude Chat, Cursor, and
custom tooling. Findings from a Monday Code session are invisible
on Tuesday in Chat. Decisions made in one interface don't surface in another.
Context is rebuilt from scratch constantly.

These aren't separate problems. They're the same problem:
**your work doesn't persist across iterations and interfaces.**

---

### The Market Gap

Look at what exists:

| Tool | What it solves | What it misses |
|---|---|---|
| PromptLayer / Langfuse / MLflow | Prompt versioning | Can't fork/merge workflow logic. No semantic evaluation of changes. |
| Mem0 / Zep / Supermemory | Persistent memory | No workflow versioning. No domain-specific synthesis. No pluggable backends. |
| LangGraph / CrewAI | Agent orchestration | Orchestrates execution, not configuration. No versioned iteration. |
| Notion / Obsidian | Personal knowledge | Manual capture. No MCP integration. No semantic merge. |
| Git alone | Code versioning | Doesn't understand skill semantics. Can't evaluate whether a merge improves findings. |

Spring AI's documentation (January 2026) explicitly states:
*"Limited Skill Versioning — there's currently no built-in versioning system
for skills. If you update a skill's behavior, all applications using that
skill will immediately use the new version."*

Nobody has built the combination of:
- DAG-based workflow configuration that is versionable and forkable
- Git as the versioning backbone with semantic understanding on top
- Semantic merge evaluation (does this change actually improve findings?)
- Universal context ingestion across all AI interfaces via MCP
- Pluggable backends for any storage, embedding, or registry system

ContextLedger is that combination.

---

### Who This Is For

**Primary: Research engineers and ML teams**
- Security researchers running investigation workflows across different target types
- ML engineers iterating RAG strategies, extraction pipelines, and analysis workflows per domain
- AI safety researchers running evaluation workflows with reproducibility requirements
- Data engineers building extraction pipelines that need different rules per data source

**Secondary: Development teams with multi-component AI projects**
- Teams with multiple Claude Code skills (one per component) who need unified context and version control
- Consulting practices delivering AI workflow assessments across industry verticals
- Research labs needing reproducible, versioned AI research workflows

**Not for:**
- Casual AI users who just want a better memory for chat
- Teams building simple single-domain pipelines with no iteration needs
- Enterprise knowledge management (wrong scale, wrong problem)

---

### The Differentiators (Ranked)

**1. Semantic merge evaluation (hardest to replicate)**
When you merge a fork back to parent, ContextLedger doesn't just diff text.
It runs both versions of your synthesis templates against real held-out findings
and scores them: precision, recall, novelty. You see a report before you merge.
No other tool does this. It's technically non-trivial because it requires
running DAG pipelines with real LLM execution against stored findings.

**2. Skill versioning with inheritance**
Forks inherit everything from parent by reference. Only overrides are stored.
This is Git's content-addressable model applied to workflow bundles.
A fork that changes one extraction rule stores only that rule — not the entire profile.

**3. Universal context via MCP**
One MCP server, all AI interfaces. Claude Code, Chat, Cursor, OpenAI, Perplexity —
any interface that supports MCP feeds into one memory. No per-interface integration.

**4. Protocol-based pluggable backends**
Every backend is a Python Protocol. Storage, embedding, registry — all swappable
without touching other code. SQLite for dev, Postgres for production, Git local
or GitHub remote for the registry.

**5. Multi-skill project manifests (Phase 2)**
Declare all skills in a project, define routing rules, query across all skills
simultaneously with automatic profile switching based on working directory.

---

### Real Use Cases

**Agent Prober (security research)**
Running 146 semantic privilege escalation tests across multiple target types
(HR agents, Perplexity, Shopify Sidekick). Each target type needs different
extraction rules, different synthesis templates. ContextLedger forks the
base Agent Prober skill per target type, lets each fork iterate independently,
and surfaces findings across all forks when querying for patterns.

**GenOpt (LLM workflow optimization)**
Five components: SDK, analyzer, API, dashboard, config. Each has different
domain knowledge. ContextLedger's project manifest auto-routes context queries
to the right component skill. A developer asking "how does retry waste detection
work" gets an answer from analyzer-skill, not sdk-skill.

**Veritas (adversarial verification)**
Five parallel verification agents per research question. Each agent has its
own extraction profile. ContextLedger versions each profile independently,
merges improvements back to the base verification profile with semantic scoring.

---

### Traction / Status

- Core framework: fully implemented, 214 tests passing
- Phase 2 (multi-skill project manifests): in development
- Phase 3 (onboarding, visual editor, VS Code extension): planned
- Real-world test case: GenOpt (multi-component LLM workflow optimizer)
- Built on solid research foundations: CMV (arXiv:2602.22402), PlugMem, GCC

---

### Adoption Path

**Open source → team tier → enterprise:**

1. **Open source (now):** `pip install contextledger`. Free, self-hosted,
   SQLite + local Git registry. For individual engineers and small teams.

2. **Team tier (Phase 3+):** Hosted registry, shared skill profiles across
   team members, GitHub-backed registry, VS Code extension.
   $X/month per team.

3. **Enterprise (future):** RBAC, audit trails, SSO, compliance features,
   Postgres-backed registry, private cloud deployment.

---

### Where This Goes

This positioning document is not for the README.

**Use it for:**
- Pitching to potential early users / beta testers
- Writing a blog post announcing ContextLedger
- Preparing a product demo
- Writing a YC / investor one-pager if you go that route
- Briefing people who ask "what is this?"

**For the README:** Use the tightened opening in Part 1 of this file.
The README should be technical and concrete. The positioning doc is strategic.

---

*Document version 1.0. Companion to: contextledger-architecture.md,
contextledger-phase2-plan.md, contextledger-phase3-plan.md,
contextledger-remaining-work.md*
