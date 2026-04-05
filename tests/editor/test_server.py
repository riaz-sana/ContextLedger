"""Tests for visual editor FastAPI server.

Task: TASK-046 — Visual editor backend
"""

import os
import pytest

try:
    from fastapi.testclient import TestClient
    from contextledger.editor.server import app
    _has_fastapi = True
except ImportError:
    _has_fastapi = False


def _setup_skills(tmp_path):
    """Create a test skills directory with two profiles."""
    skills = tmp_path / "skills"
    for name, parent in [("skill-a", None), ("skill-b", "skill-a")]:
        d = skills / name
        d.mkdir(parents=True)
        parent_line = f"parent: {parent}" if parent else "parent: null"
        (d / "profile.yaml").write_text(
            f"name: {name}\nversion: 1.0.0\n{parent_line}\n"
            f"extraction:\n  entities: [finding]\n  sources: [test]\n"
            f"synthesis:\n  dag:\n    nodes:\n"
            f"      - id: extract\n        type: extraction\n        depends_on: []\n"
            f"      - id: synth\n        type: synthesis\n        depends_on: [extract]\n"
        )
    return str(tmp_path)


@pytest.fixture
def client(tmp_path, monkeypatch):
    if not _has_fastapi:
        pytest.skip("fastapi not installed")
    home = _setup_skills(tmp_path)
    monkeypatch.setenv("CTX_HOME", home)
    return TestClient(app)


class TestEditorAPI:
    def test_list_profiles(self, client):
        r = client.get("/api/profiles")
        assert r.status_code == 200
        names = [p["name"] for p in r.json()["profiles"]]
        assert "skill-a" in names
        assert "skill-b" in names

    def test_get_profile(self, client):
        r = client.get("/api/profiles/skill-a")
        assert r.status_code == 200
        assert r.json()["name"] == "skill-a"

    def test_get_profile_not_found(self, client):
        r = client.get("/api/profiles/nonexistent")
        assert r.status_code == 404

    def test_save_profile(self, client):
        body = {"name": "new-skill", "version": "1.0.0", "extraction": {"entities": ["x"]}}
        r = client.post("/api/profiles/new-skill", json=body)
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        # Verify it was persisted
        r2 = client.get("/api/profiles/new-skill")
        assert r2.status_code == 200

    def test_dag_endpoint(self, client):
        r = client.get("/api/profiles/skill-a/dag")
        assert r.status_code == 200
        data = r.json()
        assert len(data["nodes"]) == 2
        assert len(data["edges"]) == 1
        assert data["edges"][0]["source"] == "extract"
        assert data["edges"][0]["target"] == "synth"

    def test_diff_endpoint(self, client):
        r = client.get("/api/diff/skill-a/skill-b")
        assert r.status_code == 200
        sections = r.json()["sections"]
        assert any(s["section"] == "parent" for s in sections)

    def test_merge_endpoint(self, client):
        r = client.post("/api/merge/skill-b/skill-a")
        assert r.status_code == 200
        assert "status" in r.json()

    def test_status_endpoint(self, client):
        r = client.get("/api/status")
        assert r.status_code == 200
        assert r.json()["total_profiles"] >= 2

    def test_index_html(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "ContextLedger" in r.text
