"""R520 (E5++) — Compliance dashboard MCP surface contract lint.

Closes the compliance mcp:FUTURE waiver. Raises the compliance
surface count from 4 → 5 shipped surfaces (core / cli / dashboard /
tui / mcp). Second commit in the compliance tier-3 surface-expansion
arc; R521 (api + webapp) will close the compliance ladder to the
§1g ceiling — same shape as the trinity R513-R515 triple and the
router R516-R518 triple just completed.

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

The MCP surface is exposed via the R286 aggregator (scripts/interop/
mcp-aggregate.py LOCAL_TOOLS registry) as three read-only tool
entries — each tool delegates to a `sovereign-osctl compliance
<verb> --json` invocation, backed by the R458 4-instrument
compliance dashboard aggregator.

Three discrete tools (status / worst / history). The `module` verb
takes a runtime `<name>` argument and is intentionally NOT exposed
via MCP — LOCAL_TOOLS uses fixed argv. The `snapshot` verb is
mutation-shaped (triple-gated) and is intentionally NOT exposed at
the MCP surface per operator §17. The R519 `watch` refresh-loop
TUI is intentionally NOT exposed — loop tools are an MCP
anti-pattern.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MCP_AGGREGATE = REPO_ROOT / "scripts" / "interop" / "mcp-aggregate.py"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
SURFACE_MAP = REPO_ROOT / "scripts" / "operator" / "surface-map.py"


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
    "compliance-status",
    "compliance-worst",
    "compliance-history",
}


def test_mcp_surface_lists_compliance_tools():
    """R520 MCP surface MUST advertise ALL 3 read-only compliance
    inspection verbs."""
    tools = _tools_by_name(_manifest())
    missing = REQUIRED_TOOLS - set(tools.keys())
    assert not missing, (
        f"MCP manifest missing compliance tools: {sorted(missing)}"
    )


def test_mcp_compliance_tools_have_operator_g_category():
    tools = _tools_by_name(_manifest())
    for name in REQUIRED_TOOLS:
        t = tools[name]
        cats = t.get("categories", [])
        assert "operator-§1g" in cats, (
            f"MCP tool {name!r} missing 'operator-§1g' category"
        )
        assert "operator-§1h" in cats, (
            f"MCP tool {name!r} missing 'operator-§1h' category"
        )
        assert "compliance" in cats, (
            f"MCP tool {name!r} missing 'compliance' category"
        )


def test_mcp_compliance_tools_invoke_via_osctl_with_json():
    """Each R520 tool MUST invoke `sovereign-osctl compliance <verb>
    --json` — load-bearing wire contract."""
    tools = _tools_by_name(_manifest())
    verb_for = {
        "compliance-status":  "status",
        "compliance-worst":   "worst",
        "compliance-history": "history",
    }
    for name, verb in verb_for.items():
        argv = tools[name].get("argv") or []
        assert argv[:2] == ["sovereign-osctl", "compliance"], (
            f"MCP tool {name!r} argv must start with sovereign-osctl "
            f"compliance; got {argv}"
        )
        assert verb in argv, (
            f"MCP tool {name!r} argv missing verb {verb!r}: {argv}"
        )
        assert "--json" in argv, (
            f"MCP tool {name!r} argv missing --json flag: {argv}"
        )


def test_mcp_compliance_tools_are_read_only():
    """Inspection is the surface; mutation lives at the CLI-only
    `compliance snapshot` triple-gated verb. No mutation-shaped
    verbs at the MCP surface (operator §17 sovereignty boundary)."""
    tools = _tools_by_name(_manifest())
    forbidden = {
        "compliance-snapshot",
        "compliance-set",
        "compliance-apply",
        "compliance-mutate",
        "compliance-install",
        "compliance-clear",
    }
    leaked = forbidden & set(tools.keys())
    assert not leaked, (
        f"MCP manifest leaks mutation verbs: {sorted(leaked)}"
    )


def test_mcp_compliance_module_is_not_exposed_via_mcp():
    """The `module` verb takes a runtime <name> argument; LOCAL_TOOLS
    uses fixed argv, so module stays CLI-only (same reason `router
    classify` and `trinity profile switch` stay CLI-only)."""
    tools = _tools_by_name(_manifest())
    assert "compliance-module" not in tools, (
        "compliance-module must NOT be exposed via MCP — it takes a "
        "runtime <name> argument incompatible with the LOCAL_TOOLS "
        "fixed-argv contract"
    )


def test_mcp_compliance_watch_is_not_exposed_via_mcp():
    """The R519 `watch` refresh-loop TUI verb is intentionally NOT
    exposed via MCP — loop tools are an MCP anti-pattern."""
    tools = _tools_by_name(_manifest())
    assert "compliance-watch" not in tools, (
        "compliance-watch must NOT be exposed via MCP — refresh-loop "
        "TUI"
    )


def test_mcp_compliance_tools_have_descriptive_summaries():
    tools = _tools_by_name(_manifest())
    for name in REQUIRED_TOOLS:
        summary = tools[name].get("summary", "")
        assert summary, f"MCP tool {name!r} has empty summary"
        assert len(summary) >= 30, (
            f"MCP tool {name!r} summary too short ({len(summary)} "
            f"chars); operator-§1g rule: descriptive"
        )
        low = summary.lower()
        assert "compliance" in low, (
            f"MCP tool {name!r} summary must mention compliance: "
            f"{summary!r}"
        )


def test_osctl_compliance_json_emits_parseable_json():
    """Each of the 3 R520-exposed verbs MUST emit parseable JSON when
    invoked via osctl — load-bearing wire contract for the MCP
    tools."""
    env = {"PATH": "/usr/bin:/bin", "HOME": "/tmp"}
    for verb in ("status", "worst", "history"):
        cp = subprocess.run(
            ["bash", str(OSCTL), "compliance", verb, "--json"],
            capture_output=True, text=True, timeout=60, env=env,
        )
        assert cp.returncode == 0, (
            f"compliance {verb} --json exit nonzero: "
            f"{cp.stderr[:300]}"
        )
        data = json.loads(cp.stdout)
        assert isinstance(data, dict), (
            f"compliance {verb} --json must emit a JSON object; "
            f"got {type(data).__name__}"
        )


def test_compliance_surface_map_extended_to_mcp():
    """R520 extends compliance surface-map to 5 shipped surfaces —
    mcp MUST appear as shipped, NOT as a FUTURE waiver."""
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module",
         "compliance", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr[:300]
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    assert entry.get("surface_count", 0) >= 5, (
        f"compliance must be at >=5 surfaces post-R520; got {entry}"
    )
    matrix = entry.get("matrix", [])
    mcp_row = next(
        (r for r in matrix if r.get("surface") == "mcp"), None
    )
    assert mcp_row is not None, (
        "compliance coverage matrix missing 'mcp' row"
    )
    assert mcp_row.get("state") == "shipped", (
        f"compliance mcp surface must be shipped; got {mcp_row}"
    )
