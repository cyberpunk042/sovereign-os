"""MCP-aggregate tool ⇄ osctl dispatch coverage (E7.M5 P4).

Every `LOCAL_TOOLS` entry in scripts/interop/mcp-aggregate.py invokes a
`sovereign-osctl <verb>` via its `argv`. If that verb isn't actually
dispatched by `scripts/sovereign-osctl`, the MCP tool is DANGLING — an
operator (or an upstream AI agent calling the aggregated MCP surface) that
invokes it gets `unknown command: <verb>` mid-task. This lint caught the
`hardware` tool pointing at a non-existent verb (the real verb is
`inventory`). Lock LOCAL_TOOLS verb ⇄ osctl dispatch so a dangling tool
can't ship again.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MCP_AGG = REPO_ROOT / "scripts" / "interop" / "mcp-aggregate.py"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"

_ARGV_VERB = re.compile(
    r'"argv":\s*\[\s*"sovereign-osctl"\s*,\s*"([a-z0-9-]+)"'
)


def _tool_verbs() -> set[str]:
    return set(_ARGV_VERB.findall(MCP_AGG.read_text(encoding="utf-8")))


def _dispatched_verbs() -> set[str]:
    # Top-level dispatch cases in the sovereign-osctl `case "$cmd" in`
    # block render as `  <verb>)`.
    body = OSCTL.read_text(encoding="utf-8")
    return set(re.findall(r"^\s+([a-z][a-z0-9-]+)\)", body, re.M))


def test_mcp_aggregate_has_tool_verbs():
    verbs = _tool_verbs()
    assert len(verbs) >= 20, (
        f"only parsed {len(verbs)} LOCAL_TOOLS argv verbs — parser may be "
        f"broken or the registry shrank unexpectedly"
    )


def test_every_local_tool_verb_dispatches():
    verbs = _tool_verbs()
    dispatched = _dispatched_verbs()
    dangling = sorted(v for v in verbs if v not in dispatched)
    assert not dangling, (
        f"mcp-aggregate LOCAL_TOOLS exposes MCP tool(s) whose "
        f"`sovereign-osctl <verb>` is NOT dispatched: {dangling}. An "
        f"operator/AI invoking these gets `unknown command`. Point the "
        f"tool's argv at a real osctl verb (or remove the tool)."
    )
