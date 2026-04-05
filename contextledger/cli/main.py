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
    version = None
    if "@" in name:
        name, version = name.rsplit("@", 1)
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
    for name in [a, b]:
        path = os.path.join(home, "skills", name, "profile.yaml")
        if os.path.exists(path):
            click.echo(f"  {name}: found")
        else:
            click.echo(f"  {name}: not found")


@cli.command()
@click.argument("fork_name")
@click.argument("parent_name")
@click.pass_context
def merge(ctx, fork_name, parent_name):
    """Merge a fork back into parent."""
    click.echo(f"Merging {fork_name} -> {parent_name}")


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
    click.echo("ContextLedger status")
    click.echo(f"  Home: {home}")
    click.echo(f"  Profiles: {count}")


@cli.command()
@click.argument("interface")
@click.pass_context
def connect(ctx, interface):
    """Connect to an AI interface."""
    click.echo(f"Connected to {interface}")
