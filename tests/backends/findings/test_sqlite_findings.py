"""Tests for SQLiteFindingsBackend."""

import os
import tempfile

import pytest

from contextledger.backends.findings.sqlite import SQLiteFindingsBackend


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_findings.db")


@pytest.fixture
def backend(db_path):
    return SQLiteFindingsBackend(db_path=db_path)


def _make_finding(profile="test-profile", **overrides):
    base = {
        "skill_profile": profile,
        "skill_version": "1.0.0",
        "finding_type": "pattern",
        "summary": "Test finding",
        "confidence": 0.8,
        "domain": "testing",
        "evaluation_eligible": True,
        "embedding": [],
        "tags": ["test"],
        "metadata": {},
    }
    base.update(overrides)
    return base


class TestSQLiteFindingsBackend:
    def test_write_and_retrieve_finding(self, backend):
        finding = _make_finding(summary="important discovery")
        fid = backend.write_finding(finding)

        results = backend.get_findings_for_profile("test-profile")
        assert len(results) == 1
        assert results[0]["id"] == fid
        assert results[0]["summary"] == "important discovery"
        assert results[0]["skill_profile"] == "test-profile"
        assert results[0]["confidence"] == 0.8
        assert results[0]["tags"] == ["test"]

    def test_get_findings_for_profile_filters_by_profile(self, backend):
        backend.write_finding(_make_finding(profile="alpha"))
        backend.write_finding(_make_finding(profile="alpha"))
        backend.write_finding(_make_finding(profile="beta"))

        alpha_results = backend.get_findings_for_profile("alpha")
        beta_results = backend.get_findings_for_profile("beta")

        assert len(alpha_results) == 2
        assert len(beta_results) == 1
        assert all(r["skill_profile"] == "alpha" for r in alpha_results)

    def test_get_findings_respects_min_confidence(self, backend):
        backend.write_finding(_make_finding(confidence=0.9))
        backend.write_finding(_make_finding(confidence=0.3))
        backend.write_finding(_make_finding(confidence=0.7))

        results_high = backend.get_findings_for_profile("test-profile", min_confidence=0.8)
        results_mid = backend.get_findings_for_profile("test-profile", min_confidence=0.5)

        assert len(results_high) == 1
        assert results_high[0]["confidence"] == 0.9
        assert len(results_mid) == 2

    def test_search_findings_returns_by_similarity(self, backend):
        # Embedding [1, 0, 0] is most similar to query [1, 0, 0]
        backend.write_finding(_make_finding(
            summary="exact match", embedding=[1.0, 0.0, 0.0]
        ))
        backend.write_finding(_make_finding(
            summary="partial match", embedding=[0.5, 0.5, 0.0]
        ))
        backend.write_finding(_make_finding(
            summary="no match", embedding=[0.0, 0.0, 1.0]
        ))

        results = backend.search_findings([1.0, 0.0, 0.0], limit=3)
        assert len(results) == 3
        assert results[0]["summary"] == "exact match"
        assert results[-1]["summary"] == "no match"

    def test_list_domains_returns_unique_domains(self, backend):
        backend.write_finding(_make_finding(domain="python"))
        backend.write_finding(_make_finding(domain="python"))
        backend.write_finding(_make_finding(domain="rust"))
        backend.write_finding(_make_finding(domain="testing"))
        # Different profile should not appear
        backend.write_finding(_make_finding(profile="other", domain="java"))

        domains = backend.list_domains("test-profile")
        assert domains == ["python", "rust", "testing"]

    def test_count_all_and_by_profile(self, backend):
        backend.write_finding(_make_finding(profile="alpha"))
        backend.write_finding(_make_finding(profile="alpha"))
        backend.write_finding(_make_finding(profile="beta"))

        assert backend.count() == 3
        assert backend.count("alpha") == 2
        assert backend.count("beta") == 1
        assert backend.count("nonexistent") == 0

    def test_persistence_across_instances(self, db_path):
        backend1 = SQLiteFindingsBackend(db_path=db_path)
        backend1.write_finding(_make_finding(summary="persisted finding"))
        del backend1

        backend2 = SQLiteFindingsBackend(db_path=db_path)
        results = backend2.get_findings_for_profile("test-profile")
        assert len(results) == 1
        assert results[0]["summary"] == "persisted finding"
