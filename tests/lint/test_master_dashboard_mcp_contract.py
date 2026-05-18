"""R499 (E11.M2++) — master-dashboard MCP surface contract lint.

Closes the master-dashboard mcp:FUTURE waiver. Raises the master-
dashboard surface count from 5 → 6 shipped surfaces (core / cli / tui /
service / api / mcp). Second commit in the tier-3 surface-expansion arc
for the §1g-named modules.

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

The MCP surface is exposed via the existing R286 aggregator
(scripts/interop/mcp-aggregate.py LOCAL_TOOLS registry) as read-only
tool entries. Each tool delegates to a `sovereign-osctl master-dashboard
<verb> --json` invocation. Mutation verbs (render / install) stay
CLI-only — operator §17 sacrosanct sovereignty boundary, matching the
read-only stance the rest of LOCAL_TOOLS takes.
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
    out = {}
    for t in manifest.get("tools", []):
        out[t["name"]] = t
    return out


def test_mcp_aggregate_present():
    assert MCP_AGGREGATE.is_file(), (
        f"mcp-aggregate script missing: {MCP_AGGREGATE}"
    )


def test_mcp_manifest_is_emittable():
    manifest = _manifest()
    assert "tools" in manifest
    assert isinstance(manifest["tools"], list)
    assert len(manifest["tools"]) > 0


def test_mcp_surface_lists_master_dashboard_tools():
    """R499 MCP surface MUST advertise the 5 read-only master-dashboard
    verbs (list / routes / collisions / health / discover)."""
    tools = _tools_by_name(_manifest())
    required = {
        "master-dashboard-list",
        "master-dashboard-routes",
        "master-dashboard-collisions",
        "master-dashboard-health",
        "master-dashboard-discover",
    }
    missing = required - set(tools.keys())
    assert not missing, (
        f"MCP manifest missing master-dashboard tools: {sorted(missing)}"
    )


def test_mcp_master_dashboard_tools_have_operator_g_category():
    """Every R499 master-dashboard MCP tool MUST carry the
    'operator-§1g' category tag so MCP clients can filter on §1g
    surfaces. Catches drift where a future entry is added without
    the standing-rule tag."""
    tools = _tools_by_name(_manifest())
    for name in ("master-dashboard-list", "master-dashboard-routes",
                 "master-dashboard-collisions",
                 "master-dashboard-health", "master-dashboard-discover"):
        t = tools[name]
        assert "operator-§1g" in t.get("categories", []), (
            f"MCP tool {name!r} missing 'operator-§1g' category"
        )


def test_mcp_master_dashboard_tools_invoke_via_osctl():
    """Each R499 tool MUST invoke `sovereign-osctl master-dashboard
    <verb> --json` — that's the load-bearing wire contract."""
    tools = _tools_by_name(_manifest())
    verb_for = {
        "master-dashboard-list":       "list",
        "master-dashboard-routes":     "routes",
        "master-dashboard-collisions": "collisions",
        "master-dashboard-health":     "health",
        "master-dashboard-discover":   "discover",
    }
    for name, verb in verb_for.items():
        argv = tools[name].get("argv") or []
        assert argv[:2] == ["sovereign-osctl", "master-dashboard"], (
            f"MCP tool {name!r} argv must start with sovereign-osctl "
            f"master-dashboard; got {argv}"
        )
        assert verb in argv, (
            f"MCP tool {name!r} argv missing verb {verb!r}: {argv}"
        )
        assert "--json" in argv, (
            f"MCP tool {name!r} argv missing --json flag: {argv}"
        )


def test_mcp_master_dashboard_tools_are_read_only():
    """Mutation verbs (render / install) MUST NOT appear as MCP tools —
    operator §17 sacrosanct sovereignty boundary. The MCP aggregator
    intentionally excludes mutating verbs."""
    tools = _tools_by_name(_manifest())
    forbidden = {
        "master-dashboard-render",
        "master-dashboard-install",
        "master-dashboard-apply",
    }
    leaked = forbidden & set(tools.keys())
    assert not leaked, (
        f"MCP manifest leaks mutation verbs (§17 boundary violation): "
        f"{sorted(leaked)}"
    )


def test_master_dashboard_surface_map_extended_to_mcp():
    """R499 extends master-dashboard surface-map to 6 shipped surfaces —
    mcp MUST appear as shipped, NOT as a FUTURE waiver."""
    sm_path = REPO_ROOT / "scripts" / "operator" / "surface-map.py"
    result = subprocess.run(
        ["python3", str(sm_path), "coverage", "--module",
         "master-dashboard", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, (
        f"surface-map coverage master-dashboard failed: "
        f"{result.stderr[:300]}"
    )
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    surface_count = entry.get("surface_count", 0)
    assert surface_count >= 6, (
        f"master-dashboard must be at >=6 surfaces post-R499; "
        f"got {surface_count}"
    )
    matrix = entry.get("matrix", [])
    mcp_row = next(
        (r for r in matrix if r.get("surface") == "mcp"), None
    )
    assert mcp_row is not None, (
        "master-dashboard coverage matrix missing 'mcp' row"
    )
    assert mcp_row.get("state") == "shipped", (
        f"master-dashboard mcp surface must be shipped; got {mcp_row}"
    )
