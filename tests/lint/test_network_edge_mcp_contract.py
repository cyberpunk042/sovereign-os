"""R508 (E11.M8++) — network-edge MCP surface contract lint.

Closes the network-edge mcp:FUTURE waiver. Raises the network-edge
surface count from 6 → 7 shipped surfaces (core / cli / tui /
dashboard / api / service / mcp). Second commit in the network-edge
tier-3 surface-expansion arc.

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

The MCP surface is exposed via the existing R286 aggregator
(scripts/interop/mcp-aggregate.py LOCAL_TOOLS registry) as read-only
tool entries. Each tool delegates to a `sovereign-osctl network-edge
<verb> --json` invocation. network-edge has no mutation verbs at any
surface — operator §17 sacrosanct sovereignty boundary; OPNsense
config changes are operator-driven via OPNsense UI/API directly,
outside the sovereign-os boundary.

The R449 detection-bundle is exposed across FIVE MCP tools (detect /
interfaces / nat-chain / opnsense-status / opnsense-capabilities) —
operator §1g rule: full ladder visible, not minimized.
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
    "network-edge-detect",
    "network-edge-interfaces",
    "network-edge-nat-chain",
    "network-edge-opnsense-status",
    "network-edge-opnsense-capabilities",
}


def test_mcp_surface_lists_network_edge_tools():
    """R508 MCP surface MUST advertise ALL 5 read-only network-edge
    verbs — operator §1g rule: full ladder visible, not minimized."""
    tools = _tools_by_name(_manifest())
    missing = REQUIRED_TOOLS - set(tools.keys())
    assert not missing, (
        f"MCP manifest missing network-edge tools: {sorted(missing)}"
    )


def test_mcp_network_edge_tools_have_operator_g_category():
    """Every R508 network-edge MCP tool MUST carry the 'operator-§1g'
    + 'network-edge' category tags so MCP clients can filter on §1g
    surfaces."""
    tools = _tools_by_name(_manifest())
    for name in REQUIRED_TOOLS:
        t = tools[name]
        assert "operator-§1g" in t.get("categories", []), (
            f"MCP tool {name!r} missing 'operator-§1g' category"
        )
        assert "network-edge" in t.get("categories", []), (
            f"MCP tool {name!r} missing 'network-edge' category"
        )


def test_mcp_network_edge_tools_invoke_via_osctl():
    """Each R508 tool MUST invoke `sovereign-osctl network-edge
    <verb> --json` — that's the load-bearing wire contract. The two
    opnsense tools carry the `opnsense` sub-verb."""
    tools = _tools_by_name(_manifest())
    verb_for = {
        "network-edge-detect":               ["detect"],
        "network-edge-interfaces":           ["interfaces"],
        "network-edge-nat-chain":            ["nat-chain"],
        "network-edge-opnsense-status":      ["opnsense", "status"],
        "network-edge-opnsense-capabilities":
            ["opnsense", "capabilities"],
    }
    for name, verbs in verb_for.items():
        argv = tools[name].get("argv") or []
        assert argv[:2] == ["sovereign-osctl", "network-edge"], (
            f"MCP tool {name!r} argv must start with sovereign-osctl "
            f"network-edge; got {argv}"
        )
        for v in verbs:
            assert v in argv, (
                f"MCP tool {name!r} argv missing verb {v!r}: {argv}"
            )
        assert "--json" in argv, (
            f"MCP tool {name!r} argv missing --json flag: {argv}"
        )


def test_mcp_network_edge_tools_are_read_only():
    """network-edge has no mutation verbs at any surface — operator
    §17 sacrosanct sovereignty boundary; OPNsense config changes are
    operator-driven via OPNsense UI/API directly, outside the
    sovereign-os boundary."""
    tools = _tools_by_name(_manifest())
    forbidden = {
        "network-edge-set",
        "network-edge-apply",
        "network-edge-install",
        "network-edge-mutate",
        "network-edge-configure",
        "network-edge-opnsense-set",
        "network-edge-opnsense-apply",
        "network-edge-opnsense-configure",
    }
    leaked = forbidden & set(tools.keys())
    assert not leaked, (
        f"MCP manifest leaks mutation verbs (§17 boundary violation): "
        f"{sorted(leaked)}"
    )


def test_mcp_network_edge_tools_have_descriptive_summaries():
    """Every R508 network-edge MCP tool MUST carry a non-empty summary
    that mentions network-edge or OPNsense so MCP-client tool-pickers
    see useful descriptions — operator-§1g rule: descriptive."""
    tools = _tools_by_name(_manifest())
    for name in REQUIRED_TOOLS:
        summary = tools[name].get("summary", "")
        assert summary, f"MCP tool {name!r} has empty summary"
        assert len(summary) >= 30, (
            f"MCP tool {name!r} summary too short ({len(summary)} "
            f"chars); operator-§1g rule: descriptive"
        )
        low = summary.lower()
        assert "network-edge" in low or "opnsense" in low or \
            "nat" in low or "interface" in low, (
            f"MCP tool {name!r} summary must mention "
            f"network-edge/opnsense: {summary!r}"
        )


def test_network_edge_surface_map_extended_to_mcp():
    """R508 extends network-edge surface-map to 7 shipped surfaces —
    mcp MUST appear as shipped, NOT as a FUTURE waiver."""
    sm_path = REPO_ROOT / "scripts" / "operator" / "surface-map.py"
    result = subprocess.run(
        ["python3", str(sm_path), "coverage", "--module",
         "network-edge", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, (
        f"surface-map coverage network-edge failed: "
        f"{result.stderr[:300]}"
    )
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    surface_count = entry.get("surface_count", 0)
    assert surface_count >= 7, (
        f"network-edge must be at >=7 surfaces post-R508; got "
        f"{surface_count}"
    )
    matrix = entry.get("matrix", [])
    mcp_row = next(
        (r for r in matrix if r.get("surface") == "mcp"), None
    )
    assert mcp_row is not None, (
        "network-edge coverage matrix missing 'mcp' row"
    )
    assert mcp_row.get("state") == "shipped", (
        f"network-edge mcp surface must be shipped; got {mcp_row}"
    )
