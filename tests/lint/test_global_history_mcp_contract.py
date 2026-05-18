"""R511 (E11.M5++) — global-history MCP surface contract lint.

Closes the global-history mcp:FUTURE waiver. Raises the global-
history surface count from 6 → 7 shipped surfaces (core / cli / tui
/ dashboard / api / service / mcp). Second commit in the global-
history tier-3 surface-expansion arc.

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

The MCP surface is exposed via the R286 aggregator
(scripts/interop/mcp-aggregate.py LOCAL_TOOLS registry) as read-only
tool entries. Each tool delegates to a `sovereign-osctl global-
history <verb> --json` invocation. global-history has no mutation
verbs at any surface — operator §17 sacrosanct sovereignty boundary;
the 6 underlying source logs (apt / dpkg / shell / osctl / events /
modules) are mutated by their owning processes, outside this surface.

Per operator §1g "We do not minimize anything." — the 4 CLI verbs
(recent / summary / sources / delta) are exposed as FOUR discrete
MCP tools, not collapsed into a single bundle.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MCP_AGGREGATE = REPO_ROOT / "scripts" / "interop" / "mcp-aggregate.py"


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


REQUIRED_TOOLS = {
    "global-history-recent",
    "global-history-summary",
    "global-history-sources",
    "global-history-delta",
}


def test_mcp_surface_lists_global_history_tools():
    """R511 MCP surface MUST advertise ALL 4 read-only global-history
    verbs — operator §1g rule: full ladder visible, not minimized."""
    tools = _tools_by_name(_manifest())
    missing = REQUIRED_TOOLS - set(tools.keys())
    assert not missing, (
        f"MCP manifest missing global-history tools: {sorted(missing)}"
    )


def test_mcp_global_history_tools_have_operator_g_category():
    """Every R511 global-history MCP tool MUST carry the 'operator-§1g'
    + 'global-history' category tags so MCP clients can filter on §1g
    surfaces."""
    tools = _tools_by_name(_manifest())
    for name in REQUIRED_TOOLS:
        t = tools[name]
        assert "operator-§1g" in t.get("categories", []), (
            f"MCP tool {name!r} missing 'operator-§1g' category"
        )
        assert "global-history" in t.get("categories", []), (
            f"MCP tool {name!r} missing 'global-history' category"
        )


def test_mcp_global_history_tools_invoke_via_osctl():
    """Each R511 tool MUST invoke `sovereign-osctl global-history
    <verb> --json` — that's the load-bearing wire contract."""
    tools = _tools_by_name(_manifest())
    verb_for = {
        "global-history-recent":   "recent",
        "global-history-summary":  "summary",
        "global-history-sources":  "sources",
        "global-history-delta":    "delta",
    }
    for name, verb in verb_for.items():
        argv = tools[name].get("argv") or []
        assert argv[:2] == ["sovereign-osctl", "global-history"], (
            f"MCP tool {name!r} argv must start with sovereign-osctl "
            f"global-history; got {argv}"
        )
        assert verb in argv, (
            f"MCP tool {name!r} argv missing verb {verb!r}: {argv}"
        )
        assert "--json" in argv, (
            f"MCP tool {name!r} argv missing --json flag: {argv}"
        )


def test_mcp_global_history_tools_are_read_only():
    """global-history has no mutation verbs at any surface — operator
    §17 sacrosanct sovereignty boundary; the 6 underlying source logs
    are mutated by their owning processes, outside the sovereign-os
    boundary."""
    tools = _tools_by_name(_manifest())
    forbidden = {
        "global-history-set",
        "global-history-apply",
        "global-history-mutate",
        "global-history-write",
        "global-history-delete",
        "global-history-clear",
    }
    leaked = forbidden & set(tools.keys())
    assert not leaked, (
        f"MCP manifest leaks mutation verbs (§17 boundary violation): "
        f"{sorted(leaked)}"
    )


def test_mcp_global_history_tools_have_descriptive_summaries():
    """Every R511 global-history MCP tool MUST carry a non-empty
    summary that mentions global-history or one of its 6 source logs
    so MCP-client tool-pickers see useful descriptions —
    operator-§1g rule: descriptive."""
    tools = _tools_by_name(_manifest())
    for name in REQUIRED_TOOLS:
        summary = tools[name].get("summary", "")
        assert summary, f"MCP tool {name!r} has empty summary"
        assert len(summary) >= 30, (
            f"MCP tool {name!r} summary too short ({len(summary)} "
            f"chars); operator-§1g rule: descriptive"
        )
        low = summary.lower()
        assert "global-history" in low or "history" in low or \
            "source" in low or "event" in low, (
            f"MCP tool {name!r} summary must mention global-history "
            f"or its domain: {summary!r}"
        )


def test_global_history_surface_map_extended_to_mcp():
    """R511 extends global-history surface-map to 7 shipped surfaces
    — mcp MUST appear as shipped, NOT as a FUTURE waiver."""
    sm_path = REPO_ROOT / "scripts" / "operator" / "surface-map.py"
    result = subprocess.run(
        ["python3", str(sm_path), "coverage", "--module",
         "global-history", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, (
        f"surface-map coverage global-history failed: "
        f"{result.stderr[:300]}"
    )
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    surface_count = entry.get("surface_count", 0)
    assert surface_count >= 7, (
        f"global-history must be at >=7 surfaces post-R511; got "
        f"{surface_count}"
    )
    matrix = entry.get("matrix", [])
    mcp_row = next(
        (r for r in matrix if r.get("surface") == "mcp"), None
    )
    assert mcp_row is not None, (
        "global-history coverage matrix missing 'mcp' row"
    )
    assert mcp_row.get("state") == "shipped", (
        f"global-history mcp surface must be shipped; got {mcp_row}"
    )
