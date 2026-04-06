"""CLI entry point for ContextLedger.

Commands: init, new, checkout, fork, diff, merge,
query, status, connect, list.
"""

import os
import click

# Load global .env from ~/.contextledger/.env (shared across all projects)
# Then load project-local .env if it exists (overrides global)
try:
    from dotenv import load_dotenv
    _global_env = os.path.join(os.path.expanduser("~/.contextledger"), ".env")
    if os.path.exists(_global_env):
        load_dotenv(_global_env)
    load_dotenv()  # project-local .env overrides
except ImportError:
    pass


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
    click.echo("Options: supabase (hosted), turso (hosted), sqlite (local only)")
    backend = click.prompt(
        "Findings backend",
        default="sqlite",
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
        click.echo("Then find your URL and anon key in Settings > API")
        supabase_url = click.prompt("Supabase URL (or Enter to skip)", default="")
        supabase_key = click.prompt("Supabase anon key (or Enter to skip)", default="", hide_input=True)
        if supabase_url and supabase_key:
            config["supabase_url"] = supabase_url
            config["supabase_key"] = supabase_key
            click.echo("Supabase configured.")
        else:
            config["findings_backend"] = "sqlite"
            click.echo("Supabase skipped. Using local SQLite. Run 'ctx configure-findings' later.")
    elif backend == "turso":
        config["turso_url"] = click.prompt("Turso database URL (libsql://...)")
        config["turso_token"] = click.prompt("Turso auth token", hide_input=True)
        click.echo("Turso configured.")
    else:
        click.echo(f"Using local SQLite. Findings at {os.path.join(home, 'findings.db')}")

    config_path = os.path.join(home, "config.yaml")
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    # --- Create global .env template ---
    env_path = os.path.join(home, ".env")
    if not os.path.exists(env_path):
        env_template = (
            "# ContextLedger API keys — loaded globally for all projects\n"
            "# This file is at ~/.contextledger/.env\n"
            "#\n"
            "# Required:\n"
            "ANTHROPIC_API_KEY=\n"
            "#\n"
            "# Embedding backend (pick one):\n"
            "# JINA_API_KEY=           # for Jina API embeddings\n"
            "# OPENAI_API_KEY=         # for OpenAI embeddings\n"
            "# OPENROUTER_API_KEY=     # for OpenRouter embeddings\n"
            "#\n"
            "# Findings backend (if using Supabase):\n"
            "# SUPABASE_URL=\n"
            "# SUPABASE_ANON_KEY=\n"
            "#\n"
            "# Findings backend (if using Turso):\n"
            "# TURSO_DATABASE_URL=\n"
            "# TURSO_AUTH_TOKEN=\n"
        )
        # Pre-fill from current environment if keys exist
        for key in ["ANTHROPIC_API_KEY", "JINA_API_KEY", "OPENAI_API_KEY",
                     "OPENROUTER_API_KEY", "SUPABASE_URL", "SUPABASE_ANON_KEY"]:
            val = os.environ.get(key, "")
            if val:
                env_template = env_template.replace(f"{key}=\n", f"{key}={val}\n")
                env_template = env_template.replace(f"# {key}=\n", f"{key}={val}\n")

        with open(env_path, "w") as f:
            f.write(env_template)
        # Add .env to gitignore
        gitignore_path = os.path.join(home, ".gitignore")
        if os.path.exists(gitignore_path):
            with open(gitignore_path) as f:
                content = f.read()
            if ".env" not in content:
                with open(gitignore_path, "a") as f:
                    f.write("\n.env\n")
        click.echo(f"API key template created: {env_path}")
        click.echo("Edit this file to add your API keys. They're loaded for all projects.")
    else:
        click.echo(f"Global .env exists: {env_path}")

    click.echo(f"\nContextLedger initialized at {home}")
    click.echo(f"Memory: {config['memory_backend']} ({config.get('memory_db_path', 'remote')})")
    click.echo(f"Findings: {config['findings_backend']}")


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
        config["supabase_url"] = click.prompt("Supabase URL", default=config.get("supabase_url", ""))
        config["supabase_key"] = click.prompt("Supabase anon key", hide_input=True, default="")
    elif backend == "turso":
        config["turso_url"] = click.prompt("Turso database URL")
        config["turso_token"] = click.prompt("Turso auth token", hide_input=True)

    config["findings_backend"] = backend
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    click.echo(f"Findings backend updated to: {backend}")

    try:
        from contextledger.backends.findings.factory import get_findings_backend
        fb = get_findings_backend(config)
        count = fb.count()
        click.echo(f"Connection successful. {count} findings in store.")
    except Exception as e:
        click.echo(f"Warning: could not connect to findings backend: {e}")


@cli.command("new")
@click.argument("name")
@click.pass_context
def new_profile(ctx, name):
    """Create a new skill profile."""
    home = ctx.obj["CTX_HOME"]
    source = click.prompt("Data source", default="filesystem")
    entities = click.prompt("Entity types (comma-separated)", default="finding")
    domain = click.prompt("Domain", default="general")

    import yaml as _yaml
    entity_list = [e.strip() for e in entities.split(",") if e.strip()]
    profile_data = {
        "name": name,
        "version": "1.0.0",
        "parent": None,
        "extraction": {
            "entities": entity_list,
            "sources": [source],
            "rules": [],
        },
        "synthesis": {
            "dag": {
                "nodes": [
                    {"id": "extract_entities", "type": "extraction", "depends_on": []},
                    {"id": "build_relationships", "type": "reasoning", "depends_on": ["extract_entities"]},
                    {"id": "synthesise_findings", "type": "synthesis", "depends_on": ["build_relationships"]},
                ]
            }
        },
        "session_context": {
            "mode": "skill_versioning",
            "cmv_enabled": True,
        },
    }
    profile_yaml = _yaml.dump(profile_data, default_flow_style=False, sort_keys=False)

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


@cli.command()
@click.option("--no-mcp", is_flag=True, help="Skip MCP setup")
@click.pass_context
def setup(ctx, no_mcp):
    """Set up ContextLedger for the current project.

    Run this once per project. Safe to re-run — skips what's already done.

    Second brain mode is always active (MCP captures sessions automatically).
    Skill versioning activates when you have skills — add them anytime with:
        python -m contextledger new my-skill
        python -m contextledger extract --from pipeline.py

    Example:
        cd ~/my-project
        python -m contextledger setup
    """
    import yaml

    home = ctx.obj["CTX_HOME"]

    # --- 1. Ensure global registry exists ---
    if not os.path.exists(os.path.join(home, "skills")):
        click.echo("First time setup — initialising global registry...")
        ctx.invoke(init)
    else:
        click.echo(f"Registry: {home}")

    # --- 2. Discover skills ---
    skills_found = []
    claude_skills_dir = os.path.join(os.getcwd(), ".claude", "skills")
    if os.path.isdir(claude_skills_dir):
        for entry in os.listdir(claude_skills_dir):
            skill_path = os.path.join(claude_skills_dir, entry, "SKILL.md")
            if os.path.isfile(skill_path):
                # Skip the contextledger-setup skill itself
                if entry == "contextledger-setup":
                    continue
                skills_found.append(entry)

    if skills_found:
        click.echo(f"Found {len(skills_found)} skills: {', '.join(skills_found)}")
    else:
        click.echo("No skills found (second brain mode is still active).")
        click.echo("Add skills anytime with: python -m contextledger new <name>")

    # --- 3. Register discovered skills in the registry ---
    if skills_found:
        skills_dir = os.path.join(home, "skills")
        registered = 0
        for skill_name in skills_found:
            skill_reg_dir = os.path.join(skills_dir, skill_name)
            if os.path.exists(os.path.join(skill_reg_dir, "profile.yaml")):
                continue  # already registered
            # Check if there's a SKILL.md to import
            skill_md = os.path.join(claude_skills_dir, skill_name, "SKILL.md")
            if os.path.isfile(skill_md):
                # Create a basic profile in the registry
                os.makedirs(skill_reg_dir, exist_ok=True)
                import yaml as _yaml
                profile = {
                    "name": skill_name,
                    "version": "1.0.0",
                    "parent": None,
                    "extraction": {
                        "entities": ["finding"],
                        "sources": ["session"],
                        "rules": [],
                    },
                    "synthesis": {
                        "dag": {
                            "nodes": [
                                {"id": "extract_entities", "type": "extraction", "depends_on": []},
                                {"id": "build_relationships", "type": "reasoning", "depends_on": ["extract_entities"]},
                                {"id": "synthesise_findings", "type": "synthesis", "depends_on": ["build_relationships"]},
                            ]
                        }
                    },
                    "session_context": {"mode": "skill_versioning", "cmv_enabled": True},
                }
                with open(os.path.join(skill_reg_dir, "profile.yaml"), "w") as f:
                    _yaml.dump(profile, f, default_flow_style=False, sort_keys=False)
                # Copy SKILL.md as a reference doc
                refs_dir = os.path.join(skill_reg_dir, "refs")
                os.makedirs(refs_dir, exist_ok=True)
                import shutil
                shutil.copy2(skill_md, os.path.join(refs_dir, "SKILL.md"))
                registered += 1
        if registered:
            click.echo(f"Registered {registered} new skills in registry at {skills_dir}")

    # --- 4. Create/update project manifest ---
    project_dir = os.path.join(os.getcwd(), ".contextledger")
    manifest_path = os.path.join(project_dir, "project.yaml")

    if os.path.exists(manifest_path):
        # Update existing manifest with any new skills
        with open(manifest_path) as f:
            manifest = yaml.safe_load(f.read()) or {}
        existing_skills = set(manifest.get("skills", []))
        new_skills = [s for s in skills_found if s not in existing_skills]
        if new_skills:
            manifest.setdefault("skills", []).extend(new_skills)
            for skill in new_skills:
                dir_name = skill.replace("-skill", "").replace("_skill", "")
                manifest.setdefault("routes", []).append({
                    "skill": skill,
                    "directories": [f"{dir_name}/"],
                    "keywords": [dir_name],
                })
            with open(manifest_path, "w") as f:
                yaml.dump(manifest, f, default_flow_style=False, sort_keys=False)
            click.echo(f"Added {len(new_skills)} new skills to manifest: {', '.join(new_skills)}")
        else:
            click.echo(f"Project manifest up to date: {manifest_path}")
    elif skills_found:
        os.makedirs(project_dir, exist_ok=True)
        project_name = os.path.basename(os.getcwd())
        manifest = {
            "name": project_name,
            "version": "1.0.0",
            "skills": skills_found,
            "default_skill": skills_found[0],
            "fusion_enabled": True,
            "routes": [],
        }
        for skill in skills_found:
            dir_name = skill.replace("-skill", "").replace("_skill", "")
            manifest["routes"].append({
                "skill": skill,
                "directories": [f"{dir_name}/"],
                "keywords": [dir_name],
            })
        with open(manifest_path, "w") as f:
            yaml.dump(manifest, f, default_flow_style=False, sort_keys=False)
        click.echo(f"Project manifest created: {manifest_path}")

    # --- 4. Wire MCP ---
    if not no_mcp:
        settings_path = os.path.join(os.getcwd(), ".claude", "settings.local.json")
        import json

        settings = {}
        if os.path.exists(settings_path):
            with open(settings_path) as f:
                try:
                    settings = json.load(f)
                except json.JSONDecodeError:
                    settings = {}

        mcp_servers = settings.setdefault("mcpServers", {})
        if "contextledger" in mcp_servers:
            click.echo("MCP already configured.")
        else:
            import sys
            python_path = sys.executable
            mcp_servers["contextledger"] = {
                "command": python_path,
                "args": ["-m", "contextledger.mcp.mcp_server"],
                "env": {"CTX_HOME": home},
            }
            os.makedirs(os.path.dirname(settings_path), exist_ok=True)
            with open(settings_path, "w") as f:
                json.dump(settings, f, indent=2)
            click.echo(f"MCP configured in {settings_path}")

    # --- Summary ---
    click.echo("")
    click.echo("--- Setup complete ---")
    click.echo(f"  Registry: {home}")
    click.echo(f"  Second brain: active (MCP captures all sessions)")
    if skills_found:
        click.echo(f"  Skill versioning: active ({len(skills_found)} skills)")
        click.echo(f"  Skills: {', '.join(skills_found)}")
    else:
        click.echo(f"  Skill versioning: not active (no skills yet)")
    if not no_mcp:
        click.echo("  MCP: configured (restart Claude Code to connect)")
    click.echo("")
    click.echo("Next steps:")
    click.echo("  1. Restart Claude Code (MCP connects on restart)")
    click.echo("  2. python -m contextledger query \"...\"        # search context")
    if not skills_found:
        click.echo("  3. python -m contextledger new my-skill        # add skill versioning")
        click.echo("  4. python -m contextledger extract --from X.py # import from code")
    else:
        click.echo("  3. python -m contextledger fork <skill> <new>  # fork for new domain")
        click.echo("  4. python -m contextledger editor              # visual editor")


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
