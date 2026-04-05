"""Visual skill editor — FastAPI local server.

Run with: ctx editor [--port 7432]
Or: python -m contextledger.editor.server
"""

import os
from pathlib import Path
from typing import Optional

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, FileResponse
    from fastapi.staticfiles import StaticFiles
    import uvicorn
except ImportError:
    raise RuntimeError(
        "FastAPI is required for the visual editor.\n"
        "Install: pip install fastapi uvicorn"
    )

import yaml

from contextledger.skill.parser import ProfileParser
from contextledger.merge.resolver import ConflictResolver

app = FastAPI(title="ContextLedger Editor", version="0.1.0")
parser = ProfileParser()
resolver = ConflictResolver()

UI_DIR = Path(__file__).parent / "ui"


def _ctx_home() -> str:
    return os.environ.get("CTX_HOME", os.path.expanduser("~/.contextledger"))


def _skills_dir() -> str:
    return os.path.join(_ctx_home(), "skills")


def _list_skill_names() -> list[str]:
    sd = _skills_dir()
    if not os.path.isdir(sd):
        return []
    return [d for d in os.listdir(sd) if os.path.isdir(os.path.join(sd, d))]


def _read_profile(name: str) -> dict:
    path = os.path.join(_skills_dir(), name, "profile.yaml")
    if not os.path.exists(path):
        raise HTTPException(404, f"Profile '{name}' not found")
    with open(path) as f:
        return parser.parse(f.read())


@app.get("/", response_class=HTMLResponse)
def index():
    """Serve the single-page editor UI."""
    index_path = UI_DIR / "index.html"
    if not index_path.exists():
        return HTMLResponse("<h1>ContextLedger Editor</h1><p>UI not found.</p>")
    return FileResponse(str(index_path))


@app.get("/api/profiles")
def list_profiles():
    """List all skill profiles."""
    names = _list_skill_names()
    profiles = []
    for name in names:
        try:
            p = _read_profile(name)
            profiles.append({
                "name": p.get("name", name),
                "version": p.get("version", "?"),
                "parent": p.get("parent"),
            })
        except Exception:
            profiles.append({"name": name, "version": "?", "parent": None})
    return {"profiles": profiles}


@app.get("/api/profiles/{name}")
def get_profile(name: str):
    """Get a parsed profile by name."""
    return _read_profile(name)


@app.post("/api/profiles/{name}")
def save_profile(name: str, body: dict):
    """Save a profile (write YAML to disk)."""
    skill_dir = os.path.join(_skills_dir(), name)
    os.makedirs(skill_dir, exist_ok=True)
    path = os.path.join(skill_dir, "profile.yaml")
    with open(path, "w") as f:
        yaml.dump(body, f, default_flow_style=False, sort_keys=False)
    return {"status": "ok", "name": name}


@app.get("/api/profiles/{name}/dag")
def get_dag(name: str):
    """Get DAG as nodes and edges for visualization."""
    profile = _read_profile(name)
    dag = profile.get("synthesis", {}).get("dag", {})
    nodes_raw = dag.get("nodes", [])

    nodes = []
    edges = []
    for n in nodes_raw:
        nodes.append({
            "id": n["id"],
            "type": n.get("type", "extraction"),
            "label": n["id"],
        })
        for dep in n.get("depends_on", []):
            edges.append({"source": dep, "target": n["id"]})

    return {"nodes": nodes, "edges": edges}


@app.get("/api/diff/{name_a}/{name_b}")
def get_diff(name_a: str, name_b: str):
    """Section-by-section diff between two profiles."""
    pa = _read_profile(name_a)
    pb = _read_profile(name_b)

    all_keys = sorted(set(list(pa.keys()) + list(pb.keys())))
    sections = []
    for key in all_keys:
        va = pa.get(key)
        vb = pb.get(key)
        if va == vb:
            sections.append({"section": key, "status": "unchanged"})
        elif va is None:
            sections.append({"section": key, "status": "added", "value": vb})
        elif vb is None:
            sections.append({"section": key, "status": "removed", "value": va})
        else:
            sections.append({
                "section": key, "status": "changed",
                "value_a": va, "value_b": vb,
            })

    return {"profile_a": name_a, "profile_b": name_b, "sections": sections}


@app.post("/api/merge/{fork_name}/{parent_name}")
def merge_profiles(fork_name: str, parent_name: str):
    """Trigger merge and return tier result."""
    parent = _read_profile(parent_name)
    fork = _read_profile(fork_name)
    result = resolver.merge(parent, fork)
    return result


@app.get("/api/status")
def get_status():
    """Registry stats."""
    names = _list_skill_names()
    return {
        "ctx_home": _ctx_home(),
        "total_profiles": len(names),
        "profiles": names,
    }


def run_editor(port: int = 7432, no_browser: bool = False):
    """Start the editor server."""
    if not no_browser:
        import webbrowser
        import threading
        threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    run_editor()
