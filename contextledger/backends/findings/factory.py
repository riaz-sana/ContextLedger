"""Factory for obtaining a FindingsBackend instance based on configuration."""

import os
from typing import Any, Dict, Optional


class FindingsBackendNotConfigured(Exception):
    """Raised when a requested findings backend cannot be configured."""


def get_findings_backend(config: Optional[Dict[str, Any]] = None):
    """Return a FindingsBackend instance based on config or environment.

    Resolution order:
    1. config dict with "backend" key ("sqlite", "supabase", "turso")
    2. CONTEXTLEDGER_FINDINGS_BACKEND environment variable
    3. Default: SQLite (with a notice printed, not an error)

    Raises FindingsBackendNotConfigured if supabase/turso is requested
    but the required credentials are missing.
    """
    backend_name = None
    if config:
        backend_name = config.get("backend") or config.get("findings_backend")
    if not backend_name:
        backend_name = os.environ.get("CONTEXTLEDGER_FINDINGS_BACKEND")

    if not backend_name:
        print("[ContextLedger] No findings backend configured. Using SQLite as default.")
        backend_name = "sqlite"

    backend_name = backend_name.lower().strip()

    if backend_name == "supabase":
        url = (config or {}).get("url") or (config or {}).get("supabase_url") or os.environ.get("SUPABASE_URL")
        key = (config or {}).get("key") or (config or {}).get("supabase_key") or os.environ.get("SUPABASE_ANON_KEY")
        if not url or not key:
            raise FindingsBackendNotConfigured(
                "Supabase backend requested but SUPABASE_URL and/or "
                "SUPABASE_ANON_KEY are not set."
            )
        from contextledger.backends.findings.supabase import SupabaseFindingsBackend

        return SupabaseFindingsBackend(url=url, key=key)

    if backend_name == "turso":
        url = (config or {}).get("url") or os.environ.get("TURSO_DATABASE_URL")
        token = (config or {}).get("token") or os.environ.get("TURSO_AUTH_TOKEN")
        if not url or not token:
            raise FindingsBackendNotConfigured(
                "Turso backend requested but TURSO_DATABASE_URL and/or "
                "TURSO_AUTH_TOKEN are not set."
            )
        from contextledger.backends.findings.turso import TursoFindingsBackend

        return TursoFindingsBackend(url=url, token=token)

    # Default: SQLite in CTX_HOME
    ctx_home = os.environ.get("CTX_HOME", os.path.expanduser("~/.contextledger"))
    default_db = os.path.join(ctx_home, "findings.db")
    db_path = (config or {}).get("db_path", default_db)
    from contextledger.backends.findings.sqlite import SQLiteFindingsBackend

    return SQLiteFindingsBackend(db_path=db_path)
