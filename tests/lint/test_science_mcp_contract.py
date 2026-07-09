"""R558 (SDD-070) — Science-tools MCP surface contract lint.

The science module's MCP surface is exposed via the R286 aggregator
(scripts/interop/mcp-aggregate.py LOCAL_TOOLS registry) as two read-only tool
entries — each delegates to a `sovereign-osctl science <verb> --json` invocation.

Two discrete tools (list / status). `run` is execution-shaped (launches a sim)
and is intentionally NOT exposed at the MCP surface per operator §17; `info`
takes a runtime `<id>` argument and LOCAL_TOOLS uses fixed argv, so it is not
exposed either. This keeps the science MCP surface read-only.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MCP_AGGREGATE = REPO_ROOT / "scripts" / "interop" / "mcp-aggregate.py"

REQUIRED_TOOLS = {"science-list", "science-status"}


def _manifest() -> dict:
    result = subprocess.run(
        ["python3", str(MCP_AGGREGATE), "manifest", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, (
        f"mcp-aggregate manifest failed: {result.stderr[:300]}"
    )
    return json.loads(result.stdout)


def _tools_by_name(manifest: dict) -> dict:
    return {t["name"]: t for t in manifest.get("tools", [])}


def test_mcp_surface_lists_science_tools():
    """The science MCP surface MUST advertise both read-only inspection verbs."""
    tools = _tools_by_name(_manifest())
    missing = REQUIRED_TOOLS - set(tools.keys())
    assert not missing, f"MCP manifest missing science tools: {sorted(missing)}"


def test_mcp_science_tools_have_science_category():
    tools = _tools_by_name(_manifest())
    for name in REQUIRED_TOOLS:
        cats = tools[name].get("categories", [])
        assert "science" in cats, f"MCP tool {name!r} missing 'science' category"
        assert "simulation" in cats, f"MCP tool {name!r} missing 'simulation' category"


def test_mcp_science_tools_invoke_via_osctl_with_json():
    """Each tool MUST invoke `sovereign-osctl science <verb> --json` — the
    load-bearing wire contract."""
    tools = _tools_by_name(_manifest())
    verb_for = {"science-list": "list", "science-status": "status"}
    for name, verb in verb_for.items():
        argv = tools[name].get("argv") or []
        assert argv[:2] == ["sovereign-osctl", "science"], (
            f"MCP tool {name!r} argv must start with sovereign-osctl science; got {argv}"
        )
        assert verb in argv, f"MCP tool {name!r} argv missing verb {verb!r}: {argv}"
        assert "--json" in argv, f"MCP tool {name!r} argv missing --json flag: {argv}"


def test_mcp_science_tools_are_read_only():
    """`run` (execution) and `info <id>` (runtime arg) are intentionally NOT on
    the MCP surface — the science MCP surface stays read-only + fixed-argv."""
    tools = _tools_by_name(_manifest())
    assert "science-run" not in tools, "science `run` must NOT be MCP-exposed (execution-shaped, §17)"
    assert "science-info" not in tools, "science `info` must NOT be MCP-exposed (takes a runtime <id> arg)"
