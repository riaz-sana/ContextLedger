"""ContextLedger MCP server — real MCP protocol implementation.

Run with:
    python -m contextledger.mcp.mcp_server

Or add to Claude Code settings:
    "mcpServers": {
        "contextledger": {
            "command": "python",
            "args": ["-m", "contextledger.mcp.mcp_server"]
        }
    }
"""

import json
from mcp.server.fastmcp import FastMCP

from contextledger.mcp.server import ContextLedgerMCP
from contextledger.backends.embedding.factory import get_embedding_backend, EmbeddingBackendNotAvailable

# Create MCP server
mcp = FastMCP(
    "ContextLedger",
    instructions="Universal context layer and skill versioning for AI interfaces",
)

# Shared instance — persists across tool calls within a session
try:
    _embedding = get_embedding_backend()
except EmbeddingBackendNotAvailable as e:
    import sys
    print(str(e), file=sys.stderr)
    sys.exit(1)

_engine = ContextLedgerMCP(embedding_backend=_embedding)


@mcp.tool()
def ctx_ingest(session_log: str) -> str:
    """Ingest a session log into ContextLedger memory.

    Captures assistant findings into three-tier memory (immediate, synthesis, archival).
    Applies CMV lossless trimming to compress heavy sessions.

    Args:
        session_log: JSON string of session log with "session_id" and "messages"
                     (list of {"role": "user"|"assistant", "content": "..."}).
    """
    try:
        data = json.loads(session_log)
    except (json.JSONDecodeError, TypeError):
        return json.dumps({"status": "error", "message": "Invalid JSON"})
    result = _engine.ctx_ingest(data)
    return json.dumps(result)


@mcp.tool()
def ctx_query(query: str, profile: str = "") -> str:
    """Query across all ContextLedger memory tiers.

    Routes to appropriate tier based on query intent:
    - Recent queries → immediate tier (verbatim last N turns)
    - Temporal queries → synthesis tier (compressed recent findings)
    - Historical queries → archival tier (full semantic history)

    Args:
        query: Natural language query.
        profile: Optional profile name to filter by.
    """
    results = _engine.ctx_query(query, profile=profile or None)
    # Serialize results — each is a dict with "content" and possibly other fields
    serialized = []
    for r in results:
        if isinstance(r, dict):
            serialized.append(r.get("content", str(r)))
        else:
            serialized.append(str(r))
    return json.dumps({"results": serialized, "count": len(serialized)})


@mcp.tool()
def ctx_grep(pattern: str) -> str:
    """Search all captured findings by pattern (case-insensitive substring match).

    Args:
        pattern: Text pattern to search for in findings.
    """
    results = _engine.ctx_grep(pattern)
    serialized = [r.get("content", str(r)) if isinstance(r, dict) else str(r) for r in results]
    return json.dumps({"results": serialized, "count": len(serialized)})


@mcp.tool()
def ctx_status() -> str:
    """Show current ContextLedger status.

    Returns active profile, number of sessions ingested, total memory units,
    and number of immediate turns in buffer.
    """
    return json.dumps(_engine.ctx_status())


@mcp.tool()
def skill_checkout(name: str, version: str = "") -> str:
    """Switch the active skill profile.

    Args:
        name: Profile name to activate.
        version: Optional specific version (default: latest).
    """
    result = _engine.skill_checkout(name, version=version or None)
    return json.dumps(result)


if __name__ == "__main__":
    mcp.run()
