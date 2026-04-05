"""Tests for findings backend factory."""

import pytest

from contextledger.backends.findings.factory import (
    FindingsBackendNotConfigured,
    get_findings_backend,
)
from contextledger.backends.findings.sqlite import SQLiteFindingsBackend


class TestFindingsFactory:
    def test_factory_returns_sqlite_when_no_config(self, tmp_path):
        db_path = str(tmp_path / "default.db")
        backend = get_findings_backend({"db_path": db_path})
        assert isinstance(backend, SQLiteFindingsBackend)

    def test_factory_returns_sqlite_as_default(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CONTEXTLEDGER_FINDINGS_BACKEND", raising=False)
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
        monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)
        monkeypatch.delenv("TURSO_AUTH_TOKEN", raising=False)

        db_path = str(tmp_path / "fallback.db")
        backend = get_findings_backend({"db_path": db_path})
        assert isinstance(backend, SQLiteFindingsBackend)

    def test_factory_raises_for_supabase_without_credentials(self, monkeypatch):
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)

        with pytest.raises(FindingsBackendNotConfigured):
            get_findings_backend({"backend": "supabase"})

    def test_factory_raises_for_turso_without_credentials(self, monkeypatch):
        monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)
        monkeypatch.delenv("TURSO_AUTH_TOKEN", raising=False)

        with pytest.raises(FindingsBackendNotConfigured):
            get_findings_backend({"backend": "turso"})
