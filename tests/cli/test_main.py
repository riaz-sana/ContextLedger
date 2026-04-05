"""Tests for CLI commands.

Tests all `ctx` subcommands using Click's test runner.

Task: TASK-016 — Implement CLI commands
"""

import pytest


class TestCLIInit:
    """Test `ctx init` command."""

    def test_init_creates_registry(self, tmp_path):
        from click.testing import CliRunner
        from contextledger.cli.main import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["init"], catch_exceptions=False, env={"CTX_HOME": str(tmp_path)})
        assert result.exit_code == 0
        assert "initialized" in result.output.lower() or "created" in result.output.lower()


class TestCLINew:
    """Test `ctx new` command."""

    def test_new_creates_profile(self, tmp_path):
        from click.testing import CliRunner
        from contextledger.cli.main import cli
        runner = CliRunner()
        runner.invoke(cli, ["init"], env={"CTX_HOME": str(tmp_path)})
        result = runner.invoke(cli, ["new", "test-skill"], input="filesystem\nfinding\n\n",
                              env={"CTX_HOME": str(tmp_path)})
        assert result.exit_code == 0


class TestCLIList:
    """Test `ctx list` command."""

    def test_list_empty(self, tmp_path):
        from click.testing import CliRunner
        from contextledger.cli.main import cli
        runner = CliRunner()
        runner.invoke(cli, ["init"], env={"CTX_HOME": str(tmp_path)})
        result = runner.invoke(cli, ["list"], env={"CTX_HOME": str(tmp_path)})
        assert result.exit_code == 0


class TestCLIFork:
    """Test `ctx fork` command."""

    def test_fork_creates_child(self, tmp_path):
        from click.testing import CliRunner
        from contextledger.cli.main import cli
        runner = CliRunner()
        runner.invoke(cli, ["init"], env={"CTX_HOME": str(tmp_path)})
        runner.invoke(cli, ["new", "parent-skill"], input="db\nfinding\n\n",
                     env={"CTX_HOME": str(tmp_path)})
        result = runner.invoke(cli, ["fork", "parent-skill", "child-skill"],
                              env={"CTX_HOME": str(tmp_path)})
        assert result.exit_code == 0


class TestCLIDiff:
    """Test `ctx diff` command."""

    def test_diff_two_profiles(self, tmp_path):
        from click.testing import CliRunner
        from contextledger.cli.main import cli
        runner = CliRunner()
        runner.invoke(cli, ["init"], env={"CTX_HOME": str(tmp_path)})
        runner.invoke(cli, ["new", "a"], input="db\nfinding\n\n", env={"CTX_HOME": str(tmp_path)})
        runner.invoke(cli, ["new", "b"], input="fs\nfile\n\n", env={"CTX_HOME": str(tmp_path)})
        result = runner.invoke(cli, ["diff", "a", "b"], env={"CTX_HOME": str(tmp_path)})
        assert result.exit_code == 0


class TestCLIStatus:
    """Test `ctx status` command."""

    def test_status_shows_info(self, tmp_path):
        from click.testing import CliRunner
        from contextledger.cli.main import cli
        runner = CliRunner()
        runner.invoke(cli, ["init"], env={"CTX_HOME": str(tmp_path)})
        result = runner.invoke(cli, ["status"], env={"CTX_HOME": str(tmp_path)})
        assert result.exit_code == 0
