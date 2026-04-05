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
    home = ctx.obj["CTX_HOME"]
    os.makedirs(home, exist_ok=True)
    os.makedirs(os.path.join(home, "skills"), exist_ok=True)
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
        click.echo("Auto-merged successfully (tier 1).")
    elif result["status"] == "evaluation_needed":
        click.echo("Tier 2 conflicts detected — evaluation needed:")
        for c in result.get("conflicts", []):
            click.echo(f"  - {c['section']} (tier {c['tier']})")
    else:
        click.echo("Merge BLOCKED — tier 3 conflicts require manual resolution:")
        for c in result.get("conflicts", []):
            click.echo(f"  - {c['section']} (tier {c['tier']})")


@cli.command()
@click.argument("text")
@click.pass_context
def query(ctx, text):
    """Query context."""
    from contextledger.mcp.server import ContextLedgerMCP

    server = ContextLedgerMCP()
    results = server.ctx_query(text)
    for r in results:
        click.echo(f"  - {r}")


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
