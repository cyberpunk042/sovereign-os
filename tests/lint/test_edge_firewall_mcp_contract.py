"""R505 (E11.M9++) — edge-firewall MCP surface contract lint.

Closes the edge-firewall mcp:FUTURE waiver. Raises the edge-firewall
surface count from 6 → 7 shipped surfaces (core / cli / tui /
dashboard / api / service / mcp). Second commit in the edge-firewall
tier-3 surface-expansion arc.

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

The MCP surface is exposed via the existing R286 aggregator
(scripts/interop/mcp-aggregate.py LOCAL_TOOLS registry) as read-only
tool entries. Each tool delegates to a `sovereign-osctl edge-firewall
<verb> --json` invocation. Mutation verb `install` and interactive
`wizard` stay CLI-only — operator §17 sacrosanct sovereignty
boundary, matching the read-only stance the rest of LOCAL_TOOLS
takes.
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


def test_mcp_surface_lists_edge_firewall_tools():
    """R505 MCP surface MUST advertise the 4 read-only edge-firewall
    verbs (state / candidates / recommend / install-plan)."""
    tools = _tools_by_name(_manifest())
    required = {
        "edge-firewall-state",
        "edge-firewall-candidates",
        "edge-firewall-recommend",
        "edge-firewall-install-plan",
    }
    missing = required - set(tools.keys())
    assert not missing, (
        f"MCP manifest missing edge-firewall tools: {sorted(missing)}"
    )


def test_mcp_edge_firewall_tools_have_operator_g_category():
    """Every R505 edge-firewall MCP tool MUST carry the 'operator-§1g'
    + 'edge-firewall' category tags so MCP clients can filter on §1g
    surfaces. Catches drift where a future entry is added without the
    standing-rule tag."""
    tools = _tools_by_name(_manifest())
    for name in ("edge-firewall-state", "edge-firewall-candidates",
                 "edge-firewall-recommend", "edge-firewall-install-plan"):
        t = tools[name]
        assert "operator-§1g" in t.get("categories", []), (
            f"MCP tool {name!r} missing 'operator-§1g' category"
        )
        assert "edge-firewall" in t.get("categories", []), (
            f"MCP tool {name!r} missing 'edge-firewall' category"
        )


def test_mcp_edge_firewall_tools_invoke_via_osctl():
    """Each R505 tool MUST invoke `sovereign-osctl edge-firewall
    <verb> --json` — that's the load-bearing wire contract."""
    tools = _tools_by_name(_manifest())
    verb_for = {
        "edge-firewall-state":        "state",
        "edge-firewall-candidates":   "candidates",
        "edge-firewall-recommend":    "recommend",
        "edge-firewall-install-plan": "install-plan",
    }
    for name, verb in verb_for.items():
        argv = tools[name].get("argv") or []
        assert argv[:2] == ["sovereign-osctl", "edge-firewall"], (
            f"MCP tool {name!r} argv must start with sovereign-osctl "
            f"edge-firewall; got {argv}"
        )
        assert verb in argv, (
            f"MCP tool {name!r} argv missing verb {verb!r}: {argv}"
        )
        assert "--json" in argv, (
            f"MCP tool {name!r} argv missing --json flag: {argv}"
        )


def test_mcp_edge_firewall_tools_are_read_only():
    """Mutation verb `install` and interactive `wizard` MUST NOT appear
    as MCP tools — operator §17 sacrosanct sovereignty boundary. Actual
    firewall changes require --apply --confirm-install on the CLI."""
    tools = _tools_by_name(_manifest())
    forbidden = {
        "edge-firewall-install",
        "edge-firewall-wizard",
        "edge-firewall-apply",
        "edge-firewall-mutate",
        "edge-firewall-uninstall",
    }
    leaked = forbidden & set(tools.keys())
    assert not leaked, (
        f"MCP manifest leaks mutation verbs (§17 boundary violation): "
        f"{sorted(leaked)}"
    )


def test_mcp_edge_firewall_tools_have_descriptive_summaries():
    """Every R505 edge-firewall MCP tool MUST carry a non-empty summary
    that mentions edge-firewall so MCP-client tool-pickers see useful
    descriptions, not bare names — operator-§1g rule: descriptive,
    not minimized."""
    tools = _tools_by_name(_manifest())
    for name in ("edge-firewall-state", "edge-firewall-candidates",
                 "edge-firewall-recommend", "edge-firewall-install-plan"):
        summary = tools[name].get("summary", "")
        assert summary, f"MCP tool {name!r} has empty summary"
        assert len(summary) >= 30, (
            f"MCP tool {name!r} summary too short ({len(summary)} chars); "
            f"operator-§1g rule: descriptive, not minimized"
        )
        assert "edge-firewall" in summary.lower() or \
            "firewall" in summary.lower(), (
            f"MCP tool {name!r} summary must mention edge-firewall: "
            f"{summary!r}"
        )


def test_edge_firewall_surface_map_extended_to_mcp():
    """R505 extends edge-firewall surface-map to 7 shipped surfaces —
    mcp MUST appear as shipped, NOT as a FUTURE waiver."""
    sm_path = REPO_ROOT / "scripts" / "operator" / "surface-map.py"
    result = subprocess.run(
        ["python3", str(sm_path), "coverage", "--module",
         "edge-firewall", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, (
        f"surface-map coverage edge-firewall failed: {result.stderr[:300]}"
    )
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    surface_count = entry.get("surface_count", 0)
    assert surface_count >= 7, (
        f"edge-firewall must be at >=7 surfaces post-R505; got "
        f"{surface_count}"
    )
    matrix = entry.get("matrix", [])
    mcp_row = next(
        (r for r in matrix if r.get("surface") == "mcp"), None
    )
    assert mcp_row is not None, (
        "edge-firewall coverage matrix missing 'mcp' row"
    )
    assert mcp_row.get("state") == "shipped", (
        f"edge-firewall mcp surface must be shipped; got {mcp_row}"
    )
