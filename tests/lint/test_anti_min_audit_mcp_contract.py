"""R523 (E5++) — anti-minimization-audit MCP surface contract lint.

Closes the anti-minimization-audit mcp:FUTURE waiver. Raises the
anti-min surface count from 4 → 5 shipped surfaces (core / cli /
dashboard / tui / mcp). Second commit in the anti-min tier-3 surface-
expansion arc; R524 (api + webapp + service) will close the anti-min
ladder to the §1g ceiling — same shape as the compliance R519-R521
triple just completed.

Per operator §1g STANDING RULE verbatim (sacrosanct, R456-anchored):

  "If you think something is really already done, ask yourself if
   you covered all angles and levels and layers and even if then
   improve it. Do not minimize or settle for less."

The MCP surface is exposed via the R286 aggregator (scripts/interop/
mcp-aggregate.py LOCAL_TOOLS registry) as three read-only tool
entries — each tool delegates to a
`sovereign-osctl anti-minimization-audit <verb> --json` invocation,
backed by the R456 8-pattern audit.

Three discrete tools (patterns / report / waivers). The `scan` verb
takes a runtime `--pattern <p>` argument and is intentionally NOT
exposed via MCP — LOCAL_TOOLS uses fixed argv. The `module <n>` and
`cross-module --threshold N` verbs are likewise runtime-argument
shaped and stay CLI-only. The `selfdef` verb is a discovery-
availability axis already covered indirectly via compliance-status
and is not exposed as its own MCP entry to keep the MCP surface
narrow. The R522 `watch` refresh-loop TUI is NOT exposed — loop
tools are an MCP anti-pattern.
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
    "anti-minimization-audit-patterns",
    "anti-minimization-audit-report",
    "anti-minimization-audit-waivers",
}


def test_mcp_surface_lists_anti_min_tools():
    """R523 MCP surface MUST advertise ALL 3 read-only anti-min
    inspection verbs."""
    tools = _tools_by_name(_manifest())
    missing = REQUIRED_TOOLS - set(tools.keys())
    assert not missing, (
        f"MCP manifest missing anti-min tools: {sorted(missing)}"
    )


def test_mcp_anti_min_tools_have_operator_g_category():
    tools = _tools_by_name(_manifest())
    for name in REQUIRED_TOOLS:
        t = tools[name]
        cats = t.get("categories", [])
        assert "operator-§1g" in cats, (
            f"MCP tool {name!r} missing 'operator-§1g' category"
        )
        assert "anti-minimization-audit" in cats, (
            f"MCP tool {name!r} missing 'anti-minimization-audit' "
            f"category"
        )


def test_mcp_anti_min_tools_invoke_via_osctl_with_json():
    """Each R523 tool MUST invoke
    `sovereign-osctl anti-minimization-audit <verb> --json` —
    load-bearing wire contract."""
    tools = _tools_by_name(_manifest())
    verb_for = {
        "anti-minimization-audit-patterns": "patterns",
        "anti-minimization-audit-report":   "report",
        "anti-minimization-audit-waivers":  "waivers",
    }
    for name, verb in verb_for.items():
        argv = tools[name].get("argv") or []
        assert argv[:2] == ["sovereign-osctl",
                            "anti-minimization-audit"], (
            f"MCP tool {name!r} argv must start with sovereign-osctl "
            f"anti-minimization-audit; got {argv}"
        )
        assert verb in argv, (
            f"MCP tool {name!r} argv missing verb {verb!r}: {argv}"
        )
        assert "--json" in argv, (
            f"MCP tool {name!r} argv missing --json flag: {argv}"
        )


def test_mcp_anti_min_tools_are_read_only():
    """Inspection is the surface; anti-min has no mutation verbs
    period (the R474 `anti-min-waiver:` annotations are operator-
    authored in-source markers, NOT something the agent toggles).
    No mutation-shaped verbs at the MCP surface (operator §17
    sovereignty boundary)."""
    tools = _tools_by_name(_manifest())
    forbidden = {
        "anti-minimization-audit-set",
        "anti-minimization-audit-apply",
        "anti-minimization-audit-mutate",
        "anti-minimization-audit-install",
        "anti-minimization-audit-clear",
        "anti-minimization-audit-waiver-add",
        "anti-minimization-audit-waiver-remove",
    }
    leaked = forbidden & set(tools.keys())
    assert not leaked, (
        f"MCP manifest leaks mutation verbs: {sorted(leaked)}"
    )


def test_mcp_anti_min_runtime_arg_verbs_not_exposed():
    """The runtime-argument-shaped verbs (`scan --pattern <p>`,
    `module <n>`, `cross-module --threshold N`) MUST NOT be exposed
    via MCP — LOCAL_TOOLS uses fixed argv (same reason `router
    classify`, `trinity profile switch`, `compliance module` stay
    CLI-only)."""
    tools = _tools_by_name(_manifest())
    for name in (
        "anti-minimization-audit-scan",
        "anti-minimization-audit-module",
        "anti-minimization-audit-cross-module",
    ):
        assert name not in tools, (
            f"{name!r} must NOT be exposed via MCP — runtime-"
            f"argument-shaped, incompatible with LOCAL_TOOLS fixed-"
            f"argv contract"
        )


def test_mcp_anti_min_watch_not_exposed_via_mcp():
    """The R522 `watch` refresh-loop TUI verb is intentionally NOT
    exposed via MCP — loop tools are an MCP anti-pattern."""
    tools = _tools_by_name(_manifest())
    assert "anti-minimization-audit-watch" not in tools, (
        "anti-minimization-audit-watch must NOT be exposed via MCP "
        "— refresh-loop TUI"
    )


def test_mcp_anti_min_tools_have_descriptive_summaries():
    tools = _tools_by_name(_manifest())
    for name in REQUIRED_TOOLS:
        summary = tools[name].get("summary", "")
        assert summary, f"MCP tool {name!r} has empty summary"
        assert len(summary) >= 30, (
            f"MCP tool {name!r} summary too short ({len(summary)} "
            f"chars); operator-§1g rule: descriptive"
        )
        low = summary.lower()
        assert "anti-min" in low or "anti-minimization" in low, (
            f"MCP tool {name!r} summary must mention anti-min: "
            f"{summary!r}"
        )


def test_osctl_anti_min_json_emits_parseable_json():
    """Each of the 3 R523-exposed verbs MUST emit parseable JSON
    when invoked via osctl — load-bearing wire contract for the
    MCP tools."""
    env = {"PATH": "/usr/bin:/bin", "HOME": "/tmp"}
    for verb in ("patterns", "report", "waivers"):
        cp = subprocess.run(
            ["bash", str(OSCTL), "anti-minimization-audit", verb,
             "--json"],
            capture_output=True, text=True, timeout=120, env=env,
        )
        assert cp.returncode == 0, (
            f"anti-min {verb} --json exit nonzero: "
            f"{cp.stderr[:300]}"
        )
        data = json.loads(cp.stdout)
        assert isinstance(data, dict), (
            f"anti-min {verb} --json must emit a JSON object; "
            f"got {type(data).__name__}"
        )


def test_anti_min_surface_map_extended_to_mcp():
    """R523 extends anti-min surface-map to 5 shipped surfaces —
    mcp MUST appear as shipped, NOT as a FUTURE waiver."""
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module",
         "anti-minimization-audit", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr[:300]
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    assert entry.get("surface_count", 0) >= 5, (
        f"anti-min must be at >=5 surfaces post-R523; got {entry}"
    )
    matrix = entry.get("matrix", [])
    mcp_row = next(
        (r for r in matrix if r.get("surface") == "mcp"), None
    )
    assert mcp_row is not None, (
        "anti-min coverage matrix missing 'mcp' row"
    )
    assert mcp_row.get("state") == "shipped", (
        f"anti-min mcp surface must be shipped; got {mcp_row}"
    )
