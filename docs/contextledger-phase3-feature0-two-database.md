# ContextLedger — Phase 3, Feature 0: Two-Database Architecture & Shared Findings Backend

**For Claude Code. Implement this BEFORE any other Phase 3 features.**
**This is the prerequisite for meaningful multi-user skill versioning.**

---

## What This Adds

Currently ContextLedger has one local `memory.db` storing everything.
This feature splits storage into two databases with different concerns,
privacy properties, and sharing semantics:

| | `memory.db` | `findings.db` |
|---|---|---|
| **Contains** | Raw sessions, embeddings, full message history, all tiers | Structured findings only — outputs of synthesis pipeline |
| **Privacy** | Personal. Contains your actual conversations. Never shared. | Safe to share. No raw session content. No PII. |
| **Default backend** | Local SQLite | Supabase (hosted Postgres + pgvector) |
| **User can change to** | Any StorageBackend plugin | Any FindingsBackend plugin |
| **Multi-user** | No — stays local | Yes — team syncs to shared backend |
| **Used for** | Querying your own context | Tier 2 evaluation across team findings |

---

## New Protocol: `FindingsBackend`

Add to `contextledger/core/protocols.py`:

```python
@runtime_checkable
class FindingsBackend(Protocol):
    """Protocol for the shared findings store.

    Stores structured, privacy-safe findings extracted by the synthesis pipeline.
    Used for Tier 2 evaluation, cross-user skill improvement, and team analytics.
    Never stores raw session content or user messages.
    """

    def write_finding(self, finding: dict) -> str:
        """Write a structured finding. Returns finding ID.

        finding must contain:
            id: str
            skill_profile: str
            skill_version: str
            finding_type: str
            summary: str
            confidence: float (0-1)
            domain: str
            timestamp: str (ISO 8601)
            evaluation_eligible: bool
            embedding: List[float]  # embedding of summary, for semantic search
        finding must NOT contain:
            raw session content
            user messages
            personal identifiers
        """
        ...

    def get_findings_for_profile(
        self,
        profile_name: str,
        limit: int = 50,
        min_confidence: float = 0.5,
    ) -> List[dict]:
        """Get findings for a skill profile, ordered by recency.

        Used by Tier 2 evaluator to get held-out findings.
        """
        ...

    def search_findings(
        self,
        query_embedding: List[float],
        profile_name: Optional[str] = None,
        limit: int = 10,
    ) -> List[dict]:
        """Semantic search across findings using embedding similarity.

        If profile_name is None, searches across all profiles.
        """
        ...

    def list_domains(self, profile_name: str) -> List[str]:
        """List all domains that have findings for this profile.

        Used to check if a domain fork already exists with data.
        """
        ...

    def count(self, profile_name: Optional[str] = None) -> int:
        """Count total findings, optionally filtered by profile."""
        ...
```

---

## New Data Type: `Finding`

Add to `contextledger/core/types.py`:

```python
@dataclass
class Finding:
    """A structured, privacy-safe finding from the synthesis pipeline.

    This is what gets written to findings.db and shared between users.
    It contains NO raw session content, NO user messages, NO personal data.
    Only the structured output of the synthesis DAG.
    """
    id: str
    skill_profile: str
    skill_version: str
    finding_type: str                           # e.g. "vulnerability", "pattern", "decision"
    summary: str                                # synthesised summary, safe to share
    confidence: float                           # 0.0 - 1.0
    domain: str                                 # e.g. "hr_systems", "telco", "filesystem"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    evaluation_eligible: bool = True            # whether to use in Tier 2 evaluation
    embedding: List[float] = field(default_factory=list)  # embedding of summary
    tags: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)  # non-PII metadata only
    # NEVER include: session_id, user_id, raw_content, message_history
```

---

## New Directory: `contextledger/backends/findings/`

### `contextledger/backends/findings/__init__.py`
Empty.

### `contextledger/backends/findings/supabase.py`

```python
"""Supabase FindingsBackend — default shared findings store.

Uses Supabase Postgres + pgvector for native semantic search.
Requires: pip install supabase

Auto-configured during ctx init if SUPABASE_URL and SUPABASE_ANON_KEY are provided.
"""

import json
import math
import os
from datetime import datetime, timezone
from typing import List, Optional


FINDINGS_TABLE = "contextledger_findings"


class SupabaseFindingsBackend:
    """FindingsBackend using Supabase (Postgres + pgvector).

    Schema (auto-created on first use):
        id TEXT PRIMARY KEY
        skill_profile TEXT
        skill_version TEXT
        finding_type TEXT
        summary TEXT
        confidence FLOAT
        domain TEXT
        timestamp TIMESTAMPTZ
        evaluation_eligible BOOLEAN
        embedding VECTOR(1536)   -- or TEXT fallback if pgvector not enabled
        tags JSONB
        metadata JSONB
    """

    def __init__(self, url: str = None, key: str = None):
        self._url = url or os.environ.get("SUPABASE_URL")
        self._key = key or os.environ.get("SUPABASE_ANON_KEY")
        if not self._url or not self._key:
            raise ValueError(
                "\nSupabase credentials not configured.\n"
                "Set SUPABASE_URL and SUPABASE_ANON_KEY, or run:\n"
                "  ctx configure-findings\n"
                "to set up your findings backend."
            )
        try:
            from supabase import create_client
            self._client = create_client(self._url, self._key)
        except ImportError:
            raise RuntimeError(
                "supabase package not installed. Run: pip install supabase"
            )
        self._ensure_table()

    def _ensure_table(self):
        """Create the findings table if it doesn't exist.

        Runs as a raw SQL query via Supabase's rpc endpoint.
        Falls back gracefully if the table already exists.
        """
        # Supabase auto-creates tables via the dashboard or migrations.
        # We use the REST API directly — table must be created via Supabase dashboard
        # or migration. Document this in setup instructions.
        pass

    def write_finding(self, finding: dict) -> str:
        uid = finding["id"]
        data = {
            "id": uid,
            "skill_profile": finding["skill_profile"],
            "skill_version": finding.get("skill_version", "unknown"),
            "finding_type": finding.get("finding_type", "general"),
            "summary": finding["summary"],
            "confidence": finding.get("confidence", 0.0),
            "domain": finding.get("domain", "unknown"),
            "timestamp": finding.get("timestamp", datetime.now(timezone.utc).isoformat()),
            "evaluation_eligible": finding.get("evaluation_eligible", True),
            "embedding": finding.get("embedding", []),
            "tags": finding.get("tags", []),
            "metadata": finding.get("metadata", {}),
        }
        self._client.table(FINDINGS_TABLE).upsert(data).execute()
        return uid

    def get_findings_for_profile(
        self,
        profile_name: str,
        limit: int = 50,
        min_confidence: float = 0.5,
    ) -> List[dict]:
        response = (
            self._client.table(FINDINGS_TABLE)
            .select("*")
            .eq("skill_profile", profile_name)
            .eq("evaluation_eligible", True)
            .gte("confidence", min_confidence)
            .order("timestamp", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data or []

    def search_findings(
        self,
        query_embedding: List[float],
        profile_name: Optional[str] = None,
        limit: int = 10,
    ) -> List[dict]:
        """Semantic search. Falls back to Python-side similarity if pgvector unavailable."""
        # Try pgvector first via rpc
        try:
            params = {
                "query_embedding": query_embedding,
                "match_count": limit,
            }
            if profile_name:
                params["profile_filter"] = profile_name
            response = self._client.rpc("match_findings", params).execute()
            if response.data:
                return response.data
        except Exception:
            pass

        # Fallback: fetch all and compute similarity in Python
        query = self._client.table(FINDINGS_TABLE).select("*")
        if profile_name:
            query = query.eq("skill_profile", profile_name)
        response = query.execute()
        rows = response.data or []

        scored = []
        for row in rows:
            emb = row.get("embedding", [])
            if emb:
                sim = self._cosine_similarity(query_embedding, emb)
                scored.append((sim, row))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [row for _, row in scored[:limit]]

    def list_domains(self, profile_name: str) -> List[str]:
        response = (
            self._client.table(FINDINGS_TABLE)
            .select("domain")
            .eq("skill_profile", profile_name)
            .execute()
        )
        return list({row["domain"] for row in (response.data or [])})

    def count(self, profile_name: Optional[str] = None) -> int:
        query = self._client.table(FINDINGS_TABLE).select("id", count="exact")
        if profile_name:
            query = query.eq("skill_profile", profile_name)
        response = query.execute()
        return response.count or 0

    @staticmethod
    def _cosine_similarity(a, b):
        if len(a) != len(b) or not a:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(x * x for x in b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)
```

### `contextledger/backends/findings/sqlite.py`

```python
"""SQLite FindingsBackend — local fallback and solo-user option.

Same schema as Supabase version. Works offline, zero config.
Not shareable between users without manual file transfer.
"""

import json
import math
import sqlite3
from datetime import datetime, timezone
from typing import List, Optional


class SQLiteFindingsBackend:
    """Local SQLite findings store. Used when no shared backend configured."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS findings (
                id TEXT PRIMARY KEY,
                skill_profile TEXT,
                skill_version TEXT,
                finding_type TEXT,
                summary TEXT,
                confidence REAL,
                domain TEXT,
                timestamp TEXT,
                evaluation_eligible INTEGER,
                embedding TEXT,
                tags TEXT,
                metadata TEXT
            )
        """)
        self._conn.commit()

    def write_finding(self, finding: dict) -> str:
        uid = finding["id"]
        self._conn.execute(
            "INSERT OR REPLACE INTO findings VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                uid,
                finding["skill_profile"],
                finding.get("skill_version", "unknown"),
                finding.get("finding_type", "general"),
                finding["summary"],
                finding.get("confidence", 0.0),
                finding.get("domain", "unknown"),
                finding.get("timestamp", datetime.now(timezone.utc).isoformat()),
                int(finding.get("evaluation_eligible", True)),
                json.dumps(finding.get("embedding", [])),
                json.dumps(finding.get("tags", [])),
                json.dumps(finding.get("metadata", {})),
            ),
        )
        self._conn.commit()
        return uid

    def get_findings_for_profile(
        self, profile_name: str, limit: int = 50, min_confidence: float = 0.5
    ) -> List[dict]:
        rows = self._conn.execute(
            """SELECT * FROM findings
               WHERE skill_profile=? AND evaluation_eligible=1 AND confidence>=?
               ORDER BY timestamp DESC LIMIT ?""",
            (profile_name, min_confidence, limit),
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def search_findings(
        self,
        query_embedding: List[float],
        profile_name: Optional[str] = None,
        limit: int = 10,
    ) -> List[dict]:
        if profile_name:
            rows = self._conn.execute(
                "SELECT * FROM findings WHERE skill_profile=?", (profile_name,)
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT * FROM findings").fetchall()

        scored = []
        for row in rows:
            d = self._row_to_dict(row)
            emb = d.get("embedding", [])
            if emb:
                sim = self._cosine_similarity(query_embedding, emb)
                scored.append((sim, d))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [d for _, d in scored[:limit]]

    def list_domains(self, profile_name: str) -> List[str]:
        rows = self._conn.execute(
            "SELECT DISTINCT domain FROM findings WHERE skill_profile=?",
            (profile_name,),
        ).fetchall()
        return [r["domain"] for r in rows]

    def count(self, profile_name: Optional[str] = None) -> int:
        if profile_name:
            row = self._conn.execute(
                "SELECT COUNT(*) as c FROM findings WHERE skill_profile=?",
                (profile_name,),
            ).fetchone()
        else:
            row = self._conn.execute("SELECT COUNT(*) as c FROM findings").fetchone()
        return row["c"] if row else 0

    def _row_to_dict(self, row) -> dict:
        return {
            "id": row["id"],
            "skill_profile": row["skill_profile"],
            "skill_version": row["skill_version"],
            "finding_type": row["finding_type"],
            "summary": row["summary"],
            "confidence": row["confidence"],
            "domain": row["domain"],
            "timestamp": row["timestamp"],
            "evaluation_eligible": bool(row["evaluation_eligible"]),
            "embedding": json.loads(row["embedding"]) if row["embedding"] else [],
            "tags": json.loads(row["tags"]) if row["tags"] else [],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
        }

    @staticmethod
    def _cosine_similarity(a, b):
        if len(a) != len(b) or not a:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(x * x for x in b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)
```

### `contextledger/backends/findings/turso.py`

```python
"""Turso FindingsBackend — libSQL hosted SQLite.

Drop-in replacement for SQLite with remote sync.
Requires: pip install libsql-client

Configure with TURSO_DATABASE_URL and TURSO_AUTH_TOKEN.
"""

import json
import math
import os
from datetime import datetime, timezone
from typing import List, Optional


class TursoFindingsBackend:
    """FindingsBackend using Turso (hosted libSQL / SQLite-compatible)."""

    def __init__(self, url: str = None, token: str = None):
        self._url = url or os.environ.get("TURSO_DATABASE_URL")
        self._token = token or os.environ.get("TURSO_AUTH_TOKEN")
        if not self._url:
            raise ValueError(
                "TURSO_DATABASE_URL not set.\n"
                "Run: ctx configure-findings --backend turso"
            )
        try:
            import libsql_client
            self._client = libsql_client.create_client_sync(
                url=self._url,
                auth_token=self._token,
            )
        except ImportError:
            raise RuntimeError(
                "libsql-client not installed. Run: pip install libsql-client"
            )
        self._create_tables()

    def _create_tables(self):
        self._client.execute("""
            CREATE TABLE IF NOT EXISTS findings (
                id TEXT PRIMARY KEY,
                skill_profile TEXT,
                skill_version TEXT,
                finding_type TEXT,
                summary TEXT,
                confidence REAL,
                domain TEXT,
                timestamp TEXT,
                evaluation_eligible INTEGER,
                embedding TEXT,
                tags TEXT,
                metadata TEXT
            )
        """)

    def write_finding(self, finding: dict) -> str:
        uid = finding["id"]
        self._client.execute(
            "INSERT OR REPLACE INTO findings VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                uid,
                finding["skill_profile"],
                finding.get("skill_version", "unknown"),
                finding.get("finding_type", "general"),
                finding["summary"],
                finding.get("confidence", 0.0),
                finding.get("domain", "unknown"),
                finding.get("timestamp", datetime.now(timezone.utc).isoformat()),
                int(finding.get("evaluation_eligible", True)),
                json.dumps(finding.get("embedding", [])),
                json.dumps(finding.get("tags", [])),
                json.dumps(finding.get("metadata", {})),
            ],
        )
        return uid

    def get_findings_for_profile(
        self, profile_name: str, limit: int = 50, min_confidence: float = 0.5
    ) -> List[dict]:
        result = self._client.execute(
            """SELECT * FROM findings
               WHERE skill_profile=? AND evaluation_eligible=1 AND confidence>=?
               ORDER BY timestamp DESC LIMIT ?""",
            [profile_name, min_confidence, limit],
        )
        return [self._row_to_dict(r) for r in result.rows]

    def search_findings(
        self,
        query_embedding: List[float],
        profile_name: Optional[str] = None,
        limit: int = 10,
    ) -> List[dict]:
        if profile_name:
            result = self._client.execute(
                "SELECT * FROM findings WHERE skill_profile=?", [profile_name]
            )
        else:
            result = self._client.execute("SELECT * FROM findings")

        scored = []
        for row in result.rows:
            d = self._row_to_dict(row)
            emb = d.get("embedding", [])
            if emb:
                sim = self._cosine_similarity(query_embedding, emb)
                scored.append((sim, d))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [d for _, d in scored[:limit]]

    def list_domains(self, profile_name: str) -> List[str]:
        result = self._client.execute(
            "SELECT DISTINCT domain FROM findings WHERE skill_profile=?",
            [profile_name],
        )
        return [r[0] for r in result.rows]

    def count(self, profile_name: Optional[str] = None) -> int:
        if profile_name:
            result = self._client.execute(
                "SELECT COUNT(*) FROM findings WHERE skill_profile=?", [profile_name]
            )
        else:
            result = self._client.execute("SELECT COUNT(*) FROM findings")
        return result.rows[0][0] if result.rows else 0

    def _row_to_dict(self, row) -> dict:
        return {
            "id": row[0], "skill_profile": row[1], "skill_version": row[2],
            "finding_type": row[3], "summary": row[4], "confidence": row[5],
            "domain": row[6], "timestamp": row[7],
            "evaluation_eligible": bool(row[8]),
            "embedding": json.loads(row[9]) if row[9] else [],
            "tags": json.loads(row[10]) if row[10] else [],
            "metadata": json.loads(row[11]) if row[11] else {},
        }

    @staticmethod
    def _cosine_similarity(a, b):
        if len(a) != len(b) or not a:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(x * x for x in b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)
```

### `contextledger/backends/findings/stub.py`

```python
"""Stub FindingsBackend for testing."""

from datetime import datetime, timezone
from typing import List, Optional


class StubFindingsBackend:
    """In-memory findings store for testing. Never use in production."""

    def __init__(self):
        self._findings = {}

    def write_finding(self, finding: dict) -> str:
        uid = finding["id"]
        self._findings[uid] = dict(finding)
        return uid

    def get_findings_for_profile(
        self, profile_name: str, limit: int = 50, min_confidence: float = 0.5
    ) -> List[dict]:
        results = [
            f for f in self._findings.values()
            if f.get("skill_profile") == profile_name
            and f.get("evaluation_eligible", True)
            and f.get("confidence", 0.0) >= min_confidence
        ]
        return sorted(results, key=lambda f: f.get("timestamp", ""), reverse=True)[:limit]

    def search_findings(
        self,
        query_embedding: List[float],
        profile_name: Optional[str] = None,
        limit: int = 10,
    ) -> List[dict]:
        findings = list(self._findings.values())
        if profile_name:
            findings = [f for f in findings if f.get("skill_profile") == profile_name]
        return findings[:limit]

    def list_domains(self, profile_name: str) -> List[str]:
        return list({
            f["domain"] for f in self._findings.values()
            if f.get("skill_profile") == profile_name
        })

    def count(self, profile_name: Optional[str] = None) -> int:
        if profile_name:
            return sum(1 for f in self._findings.values() if f.get("skill_profile") == profile_name)
        return len(self._findings)
```

### `contextledger/backends/findings/factory.py`

```python
"""FindingsBackend factory.

Loads the configured findings backend. Priority:
  1. Supabase (default shared backend, auto-configured during ctx init)
  2. Turso (alternative shared backend)
  3. SQLite (local fallback, no sharing)

Never silently falls back — tells user clearly what's happening.
"""

import os


class FindingsBackendNotConfigured(RuntimeError):
    pass


def get_findings_backend(config: dict = None):
    """Load the configured findings backend.

    Reads from config dict or environment variables.
    Falls back to local SQLite with a clear notice (not an error —
    local SQLite is a valid choice for solo users).
    """
    config = config or {}
    backend_type = config.get("findings_backend") or os.environ.get(
        "CONTEXTLEDGER_FINDINGS_BACKEND", "sqlite"
    )

    if backend_type == "supabase":
        from contextledger.backends.findings.supabase import SupabaseFindingsBackend
        return SupabaseFindingsBackend(
            url=config.get("supabase_url"),
            key=config.get("supabase_key"),
        )

    elif backend_type == "turso":
        from contextledger.backends.findings.turso import TursoFindingsBackend
        return TursoFindingsBackend(
            url=config.get("turso_url"),
            token=config.get("turso_token"),
        )

    else:
        # Local SQLite — valid for solo use, not shareable
        import os
        ctx_home = config.get("ctx_home") or os.environ.get(
            "CTX_HOME", os.path.expanduser("~/.contextledger")
        )
        db_path = os.path.join(ctx_home, "findings.db")
        print(
            f"[ContextLedger] Using local findings store at {db_path}.\n"
            f"Findings are not shared between users.\n"
            f"Run 'ctx configure-findings' to set up a shared backend."
        )
        from contextledger.backends.findings.sqlite import SQLiteFindingsBackend
        return SQLiteFindingsBackend(db_path)
```

---

## Config File: `~/.contextledger/config.yaml`

Auto-created by `ctx init`. Stores backend configuration.

```yaml
# ContextLedger configuration
# Generated by ctx init

# Session memory — personal, never shared
memory_backend: sqlite                    # sqlite | postgres | custom
memory_db_path: ~/.contextledger/memory.db

# Findings — shareable structured outputs of synthesis pipeline
findings_backend: supabase               # supabase | turso | sqlite | custom
supabase_url: https://xxx.supabase.co
supabase_key: eyJ...

# Registry — skill profiles and versioning
registry_backend: git_local              # git_local | github | custom
```

---

## Updated `ctx init` — Auto-Configuration Flow

Replace the current `ctx init` with this full flow:

```python
@cli.command()
@click.pass_context
def init(ctx):
    """Initialize a ContextLedger registry."""
    import subprocess
    import yaml

    home = ctx.obj["CTX_HOME"]
    os.makedirs(home, exist_ok=True)
    os.makedirs(os.path.join(home, "skills"), exist_ok=True)

    # --- Git init ---
    git_dir = os.path.join(home, ".git")
    if not os.path.exists(git_dir):
        subprocess.run(["git", "init", home], capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "contextledger@local"], cwd=home, capture_output=True)
        subprocess.run(["git", "config", "user.name", "ContextLedger"], cwd=home, capture_output=True)
        gitignore = os.path.join(home, ".gitignore")
        with open(gitignore, "w") as f:
            f.write("*.db\n*.db-shm\n*.db-wal\n")
        subprocess.run(["git", "add", ".gitignore"], cwd=home, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initialize ContextLedger registry"], cwd=home, capture_output=True)
        click.echo("Git repository initialized.")

    # --- Findings backend configuration ---
    click.echo("\n--- Findings Backend (shared, team-accessible) ---")
    click.echo("Default: Supabase (free tier, hosted Postgres + pgvector)")
    click.echo("Alternatives: turso, sqlite (local only)")
    backend = click.prompt(
        "Findings backend",
        default="supabase",
        type=click.Choice(["supabase", "turso", "sqlite"], case_sensitive=False),
    )

    config = {
        "memory_backend": "sqlite",
        "memory_db_path": os.path.join(home, "memory.db"),
        "findings_backend": backend,
        "registry_backend": "git_local",
    }

    if backend == "supabase":
        click.echo("\nCreate a free Supabase project at https://supabase.com")
        click.echo("Then find your project URL and anon key in Settings → API")
        supabase_url = click.prompt("Supabase URL (or press Enter to skip)", default="")
        supabase_key = click.prompt("Supabase anon key (or press Enter to skip)", default="", hide_input=True)
        if supabase_url and supabase_key:
            config["supabase_url"] = supabase_url
            config["supabase_key"] = supabase_key
            click.echo("Supabase configured. Findings will sync automatically.")
        else:
            config["findings_backend"] = "sqlite"
            click.echo(
                "Supabase skipped. Using local SQLite for findings.\n"
                "Run 'ctx configure-findings' later to add shared storage."
            )

    elif backend == "turso":
        turso_url = click.prompt("Turso database URL (libsql://...)")
        turso_token = click.prompt("Turso auth token", hide_input=True)
        config["turso_url"] = turso_url
        config["turso_token"] = turso_token
        click.echo("Turso configured.")

    else:
        click.echo(f"Using local SQLite. Findings stored at {os.path.join(home, 'findings.db')}")

    # --- Optional: memory backend configuration ---
    click.echo("\n--- Memory Backend (personal, local by default) ---")
    move_memory = click.confirm(
        "Move memory store to a remote backend? (recommended: no for privacy)",
        default=False,
    )
    if move_memory:
        mem_backend = click.prompt(
            "Memory backend",
            default="sqlite",
            type=click.Choice(["supabase", "turso", "sqlite"], case_sensitive=False),
        )
        if mem_backend == "supabase":
            click.echo("Using same Supabase project for memory (separate table).")
            config["memory_backend"] = "supabase"
        elif mem_backend == "turso":
            mem_turso_url = click.prompt("Turso URL for memory (can be same as findings)")
            config["memory_backend"] = "turso"
            config["memory_turso_url"] = mem_turso_url

    # --- Write config ---
    config_path = os.path.join(home, "config.yaml")
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    click.echo(f"\nContextLedger initialized at {home}")
    click.echo(f"Config: {config_path}")
    click.echo(f"Memory: {config['memory_backend']} ({config.get('memory_db_path', 'remote')})")
    click.echo(f"Findings: {config['findings_backend']}")
```

---

## New CLI Command: `ctx configure-findings`

For users who skipped Supabase during init or want to switch backends later:

```python
@cli.command("configure-findings")
@click.pass_context
def configure_findings(ctx):
    """Configure or change the findings backend."""
    import yaml

    home = ctx.obj["CTX_HOME"]
    config_path = os.path.join(home, "config.yaml")

    config = {}
    if os.path.exists(config_path):
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}

    backend = click.prompt(
        "Findings backend",
        default=config.get("findings_backend", "sqlite"),
        type=click.Choice(["supabase", "turso", "sqlite"], case_sensitive=False),
    )

    if backend == "supabase":
        config["supabase_url"] = click.prompt(
            "Supabase URL", default=config.get("supabase_url", "")
        )
        config["supabase_key"] = click.prompt(
            "Supabase anon key", hide_input=True, default=""
        )
    elif backend == "turso":
        config["turso_url"] = click.prompt("Turso database URL")
        config["turso_token"] = click.prompt("Turso auth token", hide_input=True)

    config["findings_backend"] = backend
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    click.echo(f"Findings backend updated to: {backend}")

    # Test connection
    try:
        from contextledger.backends.findings.factory import get_findings_backend
        backend_instance = get_findings_backend(config)
        count = backend_instance.count()
        click.echo(f"Connection successful. {count} findings in store.")
    except Exception as e:
        click.echo(f"Warning: could not connect to findings backend: {e}")
```

---

## Privacy Gate: `FindingsExtractor`

This is the component that sits between the synthesis pipeline and `findings.db`.
It enforces the privacy boundary — nothing that contains raw session content
can pass through.

**New file: `contextledger/merge/findings_extractor.py`**

```python
"""FindingsExtractor — privacy gate between synthesis pipeline and findings.db.

Transforms DAG synthesis outputs into privacy-safe Finding objects.
Enforces: no raw session content, no user messages, no personal identifiers.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional


# Fields that are never allowed in a Finding
_FORBIDDEN_FIELDS = {
    "raw_content", "user_message", "session_log", "messages",
    "conversation", "prompt", "user_input", "personal_data",
}


class FindingsExtractor:
    """Extracts structured, privacy-safe findings from DAG synthesis outputs."""

    def __init__(self, embedding_backend, findings_backend):
        self._embedding = embedding_backend
        self._findings = findings_backend

    def extract_and_store(
        self,
        synthesis_outputs: dict,
        skill_profile: str,
        skill_version: str,
        domain: str,
        min_confidence: float = 0.5,
    ) -> List[dict]:
        """Extract findings from synthesis outputs and write to findings.db.

        Args:
            synthesis_outputs: Output dict from DAGExecutor.execute()
            skill_profile: Name of the active skill profile
            skill_version: Version of the active skill profile
            domain: Domain context (e.g. "hr_systems", "telco")
            min_confidence: Minimum confidence threshold for storage

        Returns:
            List of Finding dicts that were stored.
        """
        stored = []
        raw_findings = self._collect_findings(synthesis_outputs)

        for raw in raw_findings:
            if raw.get("confidence", 0.0) < min_confidence:
                continue

            # Enforce privacy — check for forbidden fields
            self._check_privacy(raw)

            summary = raw.get("content") or raw.get("summary") or raw.get("finding", "")
            if not summary:
                continue

            finding = {
                "id": str(uuid.uuid4()),
                "skill_profile": skill_profile,
                "skill_version": skill_version,
                "finding_type": raw.get("type", "general"),
                "summary": summary,
                "confidence": raw.get("confidence", 0.7),
                "domain": domain,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "evaluation_eligible": True,
                "embedding": self._embedding.encode(summary),
                "tags": raw.get("tags", []),
                "metadata": {
                    k: v for k, v in raw.items()
                    if k not in _FORBIDDEN_FIELDS
                    and k not in {"content", "summary", "finding", "type", "confidence", "tags"}
                },
            }

            self._findings.write_finding(finding)
            stored.append(finding)

        return stored

    def _collect_findings(self, synthesis_outputs: dict) -> List[dict]:
        """Pull findings from all synthesis and filter node outputs."""
        findings = []
        for node_id, output in synthesis_outputs.items():
            if isinstance(output, dict):
                if "findings" in output:
                    findings.extend(output["findings"])
                elif "filtered_findings" in output:
                    findings.extend(output["filtered_findings"])
        return findings

    def _check_privacy(self, finding: dict):
        """Raise if finding contains forbidden fields."""
        violations = set(finding.keys()) & _FORBIDDEN_FIELDS
        if violations:
            raise ValueError(
                f"Finding contains forbidden fields: {violations}. "
                f"These fields cannot be stored in findings.db."
            )
```

---

## Wire FindingsExtractor into MCP Server

Update `contextledger/mcp/server.py` — add findings extraction after ingestion:

```python
# In ctx_ingest(), after DAG runs (when DAG node handlers are live):

from contextledger.merge.findings_extractor import FindingsExtractor

# After CMV snapshot + signal extraction:
if self._findings_backend and self._dag_executor and self._active_profile:
    extractor = FindingsExtractor(self._embedding, self._findings_backend)
    extractor.extract_and_store(
        synthesis_outputs=dag_outputs,
        skill_profile=self._active_profile,
        skill_version=self._active_version or "unknown",
        domain=session_log.get("domain", "unknown"),
    )
```

---

## Updated Project Structure

```
contextledger/
├── backends/
│   ├── findings/              # NEW
│   │   ├── __init__.py
│   │   ├── supabase.py        # Default shared backend
│   │   ├── turso.py           # Alternative shared backend
│   │   ├── sqlite.py          # Local fallback
│   │   ├── stub.py            # Tests only
│   │   └── factory.py         # Auto-selects backend from config
│   ├── storage/               # Existing (memory.db backends)
│   ├── embedding/             # Existing
│   └── registry/              # Existing
├── merge/
│   ├── findings_extractor.py  # NEW — privacy gate
│   ├── evaluator.py           # Updated — uses findings.db
│   ├── resolver.py            # Unchanged
│   └── scorer.py              # Unchanged
└── ...
```

---

## Tests Required

### `tests/backends/findings/test_sqlite_findings.py`

```
- test_write_and_retrieve_finding
- test_get_findings_for_profile_filters_by_profile
- test_get_findings_respects_min_confidence
- test_search_findings_returns_by_similarity
- test_list_domains_returns_unique_domains
- test_count_all_and_by_profile
```

### `tests/backends/findings/test_factory.py`

```
- test_factory_returns_sqlite_when_no_config
- test_factory_returns_supabase_when_configured
- test_factory_returns_turso_when_configured
- test_factory_prints_notice_for_local_sqlite
```

### `tests/merge/test_findings_extractor.py`

```
- test_extracts_findings_from_synthesis_output
- test_skips_findings_below_min_confidence
- test_raises_on_forbidden_fields
- test_generates_embedding_for_summary
- test_stores_to_findings_backend
- test_empty_synthesis_output_returns_empty_list
```

### `tests/integration/test_two_database_architecture.py`

```
- test_memory_db_and_findings_db_are_separate_files
- test_findings_do_not_contain_raw_session_content
- test_evaluator_uses_findings_db_not_memory_db
- test_full_flow_ingest_to_findings_to_evaluation
```

---

## Supabase Table Setup (Run Once in Supabase Dashboard)

Include this in the documentation. Users run this SQL once in their Supabase SQL editor:

```sql
CREATE TABLE IF NOT EXISTS contextledger_findings (
    id TEXT PRIMARY KEY,
    skill_profile TEXT NOT NULL,
    skill_version TEXT,
    finding_type TEXT,
    summary TEXT NOT NULL,
    confidence FLOAT DEFAULT 0.0,
    domain TEXT DEFAULT 'unknown',
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    evaluation_eligible BOOLEAN DEFAULT TRUE,
    embedding VECTOR(1536),   -- requires pgvector extension
    tags JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}'
);

-- Enable pgvector (if not already enabled)
CREATE EXTENSION IF NOT EXISTS vector;

-- Index for fast profile lookups
CREATE INDEX IF NOT EXISTS idx_findings_profile
    ON contextledger_findings(skill_profile);

-- Index for semantic search
CREATE INDEX IF NOT EXISTS idx_findings_embedding
    ON contextledger_findings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- RPC function for semantic search (used by SupabaseFindingsBackend)
CREATE OR REPLACE FUNCTION match_findings(
    query_embedding VECTOR(1536),
    match_count INT,
    profile_filter TEXT DEFAULT NULL
)
RETURNS TABLE (
    id TEXT, skill_profile TEXT, summary TEXT,
    confidence FLOAT, domain TEXT, timestamp TIMESTAMPTZ,
    similarity FLOAT
)
LANGUAGE SQL STABLE AS $$
    SELECT
        id, skill_profile, summary, confidence, domain, timestamp,
        1 - (embedding <=> query_embedding) AS similarity
    FROM contextledger_findings
    WHERE (profile_filter IS NULL OR skill_profile = profile_filter)
      AND evaluation_eligible = TRUE
    ORDER BY embedding <=> query_embedding
    LIMIT match_count;
$$;
```

---

## Build Order

1. `core/types.py` — add `Finding` dataclass (15 min)
2. `core/protocols.py` — add `FindingsBackend` Protocol (15 min)
3. `backends/findings/stub.py` — in-memory stub for tests (20 min)
4. `backends/findings/sqlite.py` — local SQLite implementation (30 min)
5. `backends/findings/supabase.py` — Supabase implementation (45 min)
6. `backends/findings/turso.py` — Turso implementation (30 min)
7. `backends/findings/factory.py` — auto-selection factory (20 min)
8. `merge/findings_extractor.py` — privacy gate (30 min)
9. Update `cli/main.py` — new `ctx init` flow + `ctx configure-findings` (45 min)
10. Tests for all new components (1 hour)
11. Wire `FindingsExtractor` into `mcp/server.py` (30 min)
12. Integration test — full flow from ingest to findings to Tier 2 evaluation (30 min)

**Estimated total: 5-6 hours.**

---

## Design Decisions Confirmed

- **Supabase default, not required**: If user skips during init, local SQLite is used with a clear notice. No silent failure.
- **Privacy gate is mandatory**: `FindingsExtractor` enforces privacy — forbidden fields raise immediately, never silently dropped.
- **memory.db and findings.db are separate files/tables always**: Even if both use Supabase, they use different tables. The separation is structural, not just by convention.
- **Stub backend for tests**: Tests never touch Supabase or Turso. StubFindingsBackend is the only findings backend used in the test suite.
- **No automatic migration from memory.db to findings.db**: Findings are only written via `FindingsExtractor` after the synthesis pipeline runs. Retroactive import is not supported — it would require re-running synthesis on historical sessions, which is a future feature.

---

*Companion to: contextledger-architecture.md, contextledger-phase2-plan.md,
contextledger-phase3-plan.md, contextledger-remaining-work.md, contextledger-fixes.md*
