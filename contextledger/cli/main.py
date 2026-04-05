"""CLI entry point for ContextLedger.

Commands: init, new, checkout, fork, diff, merge,
query, status, connect, list.
"""

import os
import click


@click.group()
@click.pass_context
def cli(ctx):
    """ContextLedger — universal context layer and skill versioning."""
    ctx.ensure_object(dict)
    ctx_home = os.environ.get("CTX_HOME", os.path.expanduser("~/.contextledger"))
    ctx.obj["CTX_HOME"] = ctx_home


@cli.command()
@click.pass_context
def init(ctx):
    """Initialize a ContextLedger registry."""
    import subprocess
    home = ctx.obj["CTX_HOME"]
    os.makedirs(home, exist_ok=True)
    os.makedirs(os.path.join(home, "skills"), exist_ok=True)

    git_dir = os.path.join(home, ".git")
    if not os.path.exists(git_dir):
        subprocess.run(["git", "init", home], capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "contextledger@local"],
            cwd=home, capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "ContextLedger"],
            cwd=home, capture_output=True,
        )
        gitignore = os.path.join(home, ".gitignore")
        with open(gitignore, "w") as f:
            f.write("*.db\n*.db-shm\n*.db-wal\n")
        subprocess.run(["git", "add", ".gitignore"], cwd=home, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initialize ContextLedger registry"],
            cwd=home, capture_output=True,
        )
        click.echo("Git repository initialized.")

    click.echo(f"ContextLedger registry initialized at {home}")


@cli.command("new")
@click.argument("name")
@click.pass_context
def new_profile(ctx, name):
    """Create a new skill profile."""
    home = ctx.obj["CTX_HOME"]
    source = click.prompt("Data source", default="filesystem")
    entities = click.prompt("Entity types (comma-separated)", default="finding")
    domain = click.prompt("Domain", default="general")

    entity_lines = "\n".join(f"    - {e.strip()}" for e in entities.split(","))
    profile_yaml = (
        f"name: {name}\n"
        f"version: 1.0.0\n"
        f"parent: null\n"
        f"extraction:\n"
        f"  entities:\n"
        f"{entity_lines}\n"
        f"  sources:\n"
        f"    - {source}\n"
        f"session_context:\n"
        f"  mode: skill_versioning\n"
        f"  cmv_enabled: true\n"
    )

    skill_dir = os.path.join(home, "skills", name)
    os.makedirs(skill_dir, exist_ok=True)
    with open(os.path.join(skill_dir, "profile.yaml"), "w") as f:
        f.write(profile_yaml)
    click.echo(f"Created profile: {name}")


@cli.command("list")
@click.pass_context
def list_profiles(ctx):
    """List all skill profiles."""
    home = ctx.obj["CTX_HOME"]
    skills_dir = os.path.join(home, "skills")
    if not os.path.exists(skills_dir):
        click.echo("No profiles found. Run `ctx init` first.")
        return
    profiles = [
        d
        for d in os.listdir(skills_dir)
        if os.path.isdir(os.path.join(skills_dir, d))
    ]
    if not profiles:
        click.echo("No profiles found.")
    for p in profiles:
        click.echo(f"  {p}")


@cli.command()
@click.argument("name")
@click.pass_context
def checkout(ctx, name):
    """Checkout a skill profile (name[@version])."""
    home = ctx.obj["CTX_HOME"]
    version = None
    if "@" in name:
        name, version = name.rsplit("@", 1)
    # Persist active profile
    active_file = os.path.join(home, "active_profile")
    with open(active_file, "w") as f:
        f.write(name + (f"@{version}" if version else ""))
    click.echo(f"Checked out: {name}" + (f"@{version}" if version else ""))


@cli.command()
@click.argument("parent")
@click.argument("child")
@click.pass_context
def fork(ctx, parent, child):
    """Fork a skill profile."""
    home = ctx.obj["CTX_HOME"]
    parent_dir = os.path.join(home, "skills", parent)
    if not os.path.exists(parent_dir):
        click.echo(f"Parent profile '{parent}' not found.")
        return
    child_dir = os.path.join(home, "skills", child)
    os.makedirs(child_dir, exist_ok=True)
    fork_yaml = f"name: {child}\nversion: 1.0.0-fork-1\nparent: {parent}\n"
    with open(os.path.join(child_dir, "profile.yaml"), "w") as f:
        f.write(fork_yaml)
    click.echo(f"Forked {parent} -> {child}")


@cli.command()
@click.argument("a")
@click.argument("b")
@click.pass_context
def diff(ctx, a, b):
    """Diff two skill profiles."""
    home = ctx.obj["CTX_HOME"]
    click.echo(f"Diff: {a} vs {b}")
    profiles = {}
    for name in [a, b]:
        path = os.path.join(home, "skills", name, "profile.yaml")
        if os.path.exists(path):
            with open(path) as f:
                profiles[name] = f.read()
            click.echo(f"  {name}: found")
        else:
            click.echo(f"  {name}: not found")
            return
    # Parse and compare
    from contextledger.skill.parser import ProfileParser
    parser = ProfileParser()
    pa = parser.parse(profiles[a])
    pb = parser.parse(profiles[b])
    for key in sorted(set(list(pa.keys()) + list(pb.keys()))):
        if pa.get(key) != pb.get(key):
            click.echo(f"  changed: {key}")


@cli.command()
@click.argument("fork_name")
@click.argument("parent_name")
@click.pass_context
def merge(ctx, fork_name, parent_name):
    """Merge a fork back into parent."""
    home = ctx.obj["CTX_HOME"]
    from contextledger.skill.parser import ProfileParser
    from contextledger.merge.resolver import ConflictResolver
    parser = ProfileParser()
    resolver = ConflictResolver()
    profiles = {}
    for name in [fork_name, parent_name]:
        path = os.path.join(home, "skills", name, "profile.yaml")
        if not os.path.exists(path):
            click.echo(f"Profile '{name}' not found.")
            return
        with open(path) as f:
            profiles[name] = parser.parse(f.read())
    result = resolver.merge(profiles[parent_name], profiles[fork_name])
    click.echo(f"Merge status: {result['status']}")

    if result["status"] == "merged":
        import yaml
        merged = result["merged"]
        parent_path = os.path.join(home, "skills", parent_name, "profile.yaml")
        with open(parent_path, "w") as f:
            yaml.dump(merged, f, default_flow_style=False, sort_keys=False)
        click.echo(f"Merged successfully. '{parent_name}' profile updated.")

    elif result["status"] == "evaluation_needed":
        click.echo("Tier 2 conflicts detected — evaluation needed:")
        for c in result.get("conflicts", []):
            click.echo(f"  - {c['section']} (tier {c['tier']})")
        click.echo(
            "\nRun with --llm-eval to use LLM-backed scoring, "
            "or resolve manually and re-run merge."
        )

    else:
        click.echo("Merge BLOCKED — tier 3 conflicts require manual resolution:")
        for c in result.get("conflicts", []):
            click.echo(f"  - {c['section']} (tier {c['tier']})")
        click.echo(
            f"\nOpen both profiles side by side:\n"
            f"  {os.path.join(home, 'skills', parent_name, 'profile.yaml')}\n"
            f"  {os.path.join(home, 'skills', fork_name, 'profile.yaml')}"
        )


@cli.command()
@click.argument("text")
@click.pass_context
def query(ctx, text):
    """Query context."""
    from contextledger.backends.embedding.factory import get_embedding_backend, EmbeddingBackendNotAvailable
    from contextledger.backends.storage.sqlite import SQLiteStorageBackend

    try:
        embedding = get_embedding_backend()
    except EmbeddingBackendNotAvailable as e:
        click.echo(str(e), err=True)
        return

    home = ctx.obj["CTX_HOME"]
    db_path = os.path.join(home, "memory.db")
    storage = SQLiteStorageBackend(db_path)

    query_embedding = embedding.encode(text)
    results = storage.search(query_embedding, limit=10)

    if not results:
        click.echo("No results found. Ingest some sessions first.")
        return
    for r in results:
        content = r.get("content", "")
        click.echo(f"  - {content[:120]}")


@cli.command()
@click.pass_context
def status(ctx):
    """Show current status."""
    home = ctx.obj["CTX_HOME"]
    skills_dir = os.path.join(home, "skills")
    count = 0
    if os.path.exists(skills_dir):
        count = len(
            [
                d
                for d in os.listdir(skills_dir)
                if os.path.isdir(os.path.join(skills_dir, d))
            ]
        )
    active = None
    active_file = os.path.join(home, "active_profile")
    if os.path.exists(active_file):
        with open(active_file) as f:
            active = f.read().strip()
    click.echo("ContextLedger status")
    click.echo(f"  Home: {home}")
    click.echo(f"  Profiles: {count}")
    click.echo(f"  Active: {active or 'none'}")


@cli.command()
@click.argument("interface")
@click.pass_context
def connect(ctx, interface):
    """Connect to an AI interface."""
    click.echo(f"Connected to {interface}")


@cli.command("extract")
@click.option("--from", "from_file", required=True, help="Python file to extract from")
@click.option("--output", default=None, help="Output path (default: stdout)")
@click.pass_context
def extract_cmd(ctx, from_file, output):
    """Generate a profile.yaml from existing Python code."""
    from contextledger.skill.extractor import PythonExtractor
    extractor = PythonExtractor()
    try:
        result = extractor.extract(from_file)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        return
    if output:
        with open(output, "w") as f:
            f.write(result)
        click.echo(f"Profile written to {output}")
    else:
        click.echo(result)


@cli.command("import")
@click.option("--from", "from_file", required=True, help="SKILL.md file to import")
@click.option("--output", default=None, help="Output path (default: stdout)")
@click.pass_context
def import_cmd(ctx, from_file, output):
    """Import a Claude Code skill as a ContextLedger profile."""
    from contextledger.skill.extractor import ClaudeSkillImporter
    from contextledger.backends.llm.claude import ClaudeLLMClient
    try:
        llm = ClaudeLLMClient()
    except RuntimeError as e:
        click.echo(str(e), err=True)
        return
    importer = ClaudeSkillImporter(llm)
    try:
        result = importer.import_skill(from_file)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        return
    if output:
        with open(output, "w") as f:
            f.write(result)
        click.echo(f"Profile written to {output}")
    else:
        click.echo(result)


@cli.command()
@click.option("--port", default=7432, help="Port number")
@click.option("--no-browser", is_flag=True, help="Don't open browser")
@click.pass_context
def editor(ctx, port, no_browser):
    """Launch visual skill editor in browser."""
    try:
        from contextledger.editor.server import run_editor
    except RuntimeError as e:
        click.echo(str(e), err=True)
        click.echo("Install: pip install fastapi uvicorn")
        return
    click.echo(f"Starting editor on http://localhost:{port}")
    run_editor(port=port, no_browser=no_browser)


# ---------------------------------------------------------------------------
# Project subcommands (Phase 2)
# ---------------------------------------------------------------------------

@cli.group()
@click.pass_context
def project(ctx):
    """Multi-skill project commands."""
    pass


@project.command("init")
@click.pass_context
def project_init(ctx):
    """Initialize a multi-skill project."""
    home = ctx.obj["CTX_HOME"]
    project_dir = os.path.join(os.getcwd(), ".contextledger")
    os.makedirs(project_dir, exist_ok=True)

    name = click.prompt("Project name", default=os.path.basename(os.getcwd()))
    skills_input = click.prompt("Skills (comma-separated)", default="default-skill")
    skills = [s.strip() for s in skills_input.split(",") if s.strip()]
    default = click.prompt("Default skill", default=skills[0] if skills else "default-skill")

    import yaml
    manifest = {
        "name": name,
        "version": "1.0.0",
        "skills": skills,
        "default_skill": default,
        "fusion_enabled": True,
        "routes": [],
    }

    auto_routes = click.confirm("Auto-generate routes from skill names?", default=True)
    if auto_routes:
        for skill in skills:
            dir_name = skill.replace("-skill", "").replace("_skill", "")
            manifest["routes"].append({
                "skill": skill,
                "directories": [f"{dir_name}/"],
                "keywords": [dir_name],
            })

    manifest_path = os.path.join(project_dir, "project.yaml")
    with open(manifest_path, "w") as f:
        yaml.dump(manifest, f, default_flow_style=False, sort_keys=False)
    click.echo(f"Project initialized: {manifest_path}")


@project.command("status")
@click.pass_context
def project_status(ctx):
    """Show project status."""
    from contextledger.project.manager import ProjectManager
    mgr = ProjectManager()
    try:
        manifest = mgr.load()
    except FileNotFoundError as e:
        click.echo(str(e))
        return

    click.echo(f"Project: {manifest.name} v{manifest.version}")
    click.echo(f"Skills: {', '.join(manifest.skills)}")
    click.echo(f"Default: {manifest.default_skill or 'none'}")
    click.echo(f"Fusion: {'enabled' if manifest.fusion_enabled else 'disabled'}")

    skill_name, reason = mgr.route()
    click.echo(f"Current routing: {skill_name} ({reason})")


@project.command("query")
@click.argument("text")
@click.option("--all", "query_all", is_flag=True, help="Query all skills")
@click.option("--profile", default=None, help="Override routing")
@click.pass_context
def project_query(ctx, text, query_all, profile):
    """Query context in a multi-skill project."""
    from contextledger.project.manager import ProjectManager
    from contextledger.backends.embedding.factory import get_embedding_backend, EmbeddingBackendNotAvailable
    from contextledger.backends.storage.sqlite import SQLiteStorageBackend

    try:
        embedding = get_embedding_backend()
    except EmbeddingBackendNotAvailable as e:
        click.echo(str(e), err=True)
        return

    home = ctx.obj["CTX_HOME"]
    db_path = os.path.join(home, "memory.db")
    storage = SQLiteStorageBackend(db_path)

    class _MemoryAdapter:
        def __init__(self, storage, embedding):
            self._storage = storage
            self._embedding = embedding
        def query(self, query, profile_name=None, limit=10):
            emb = self._embedding.encode(query)
            results = self._storage.search(emb, limit=limit)
            if profile_name:
                results = [r for r in results if r.get("profile_name") == profile_name]
            return results

    mgr = ProjectManager(memory_system=_MemoryAdapter(storage, embedding))
    try:
        mgr.load()
    except FileNotFoundError as e:
        click.echo(str(e))
        return

    if query_all:
        result = mgr.query_all(text)
    else:
        result = mgr.query_routed(text, explicit_profile=profile)

    click.echo(f"Routed to: {result.active_skill} ({result.routing_reason})")
    for item in result.fused_results:
        content = item.get("content", "") if isinstance(item, dict) else getattr(item, "content", "")
        click.echo(f"  - {content[:100]}")


@project.command("route")
@click.option("--query", default=None)
@click.option("--dir", "directory", default=None)
@click.option("--file", "file_path", default=None)
@click.pass_context
def project_route(ctx, query, directory, file_path):
    """Dry-run routing — show which skill would be selected."""
    from contextledger.project.manager import ProjectManager
    mgr = ProjectManager()
    try:
        mgr.load()
    except FileNotFoundError as e:
        click.echo(str(e))
        return

    skill, reason = mgr.route(query=query, current_dir=directory, file_path=file_path)
    click.echo(f"{skill} ({reason})")


@project.command("add-skill")
@click.argument("skill_name")
@click.option("--directories", default=None, help="Comma-separated directories")
@click.option("--keywords", default=None, help="Comma-separated keywords")
@click.pass_context
def project_add_skill(ctx, skill_name, directories, keywords):
    """Add a skill to the project manifest."""
    from contextledger.project.manifest import ManifestParser, ManifestLocator, MANIFEST_DIR, MANIFEST_FILENAME
    import yaml

    locator = ManifestLocator()
    path = locator.find()
    if not path:
        click.echo("No project manifest found. Run `ctx project init` first.")
        return

    with open(path) as f:
        data = yaml.safe_load(f.read())

    if skill_name in data.get("skills", []):
        click.echo(f"Skill '{skill_name}' already in project.")
        return

    data.setdefault("skills", []).append(skill_name)

    route = {"skill": skill_name}
    if directories:
        route["directories"] = [d.strip() for d in directories.split(",")]
    if keywords:
        route["keywords"] = [k.strip() for k in keywords.split(",")]
    if directories or keywords:
        data.setdefault("routes", []).append(route)

    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    click.echo(f"Added skill '{skill_name}' to project.")


@project.command("remove-skill")
@click.argument("skill_name")
@click.pass_context
def project_remove_skill(ctx, skill_name):
    """Remove a skill from the project manifest."""
    from contextledger.project.manifest import ManifestLocator
    import yaml

    locator = ManifestLocator()
    path = locator.find()
    if not path:
        click.echo("No project manifest found.")
        return

    with open(path) as f:
        data = yaml.safe_load(f.read())

    skills = data.get("skills", [])
    if skill_name not in skills:
        click.echo(f"Skill '{skill_name}' not in project.")
        return

    skills.remove(skill_name)
    data["routes"] = [r for r in data.get("routes", []) if r.get("skill") != skill_name]
    if data.get("default_skill") == skill_name:
        data["default_skill"] = skills[0] if skills else None

    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    click.echo(f"Removed skill '{skill_name}' from project.")
