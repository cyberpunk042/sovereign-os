"""R529 (E5++) — ux-design-audit MCP surface contract lint.

Closes the ux-design-audit mcp:FUTURE waiver. Raises the ux-design-
audit surface count from 4 -> 5 shipped surfaces (core / cli / tui /
dashboard / mcp). Second commit in the ux-design-audit tier-3 surface-
expansion arc; R530 (api + webapp; and the service-not-applicable
replacement) will close the ux-design-audit ladder to the §1g
ceiling — same shape as the doc-coverage R525-R527 triple, the
anti-min R522-R524 triple, the compliance R519-R521 triple, the
router R516-R518 triple, and the trinity R513-R515 triple.

Per operator §1g STANDING RULE verbatim (sacrosanct, R456-anchored):

  "If you think something is really already done, ask yourself if
   you covered all angles and levels and layers and even if then
   improve it. Do not minimize or settle for less."

Per operator §1g verbatim (R457 anchor):

  "everything will also need to go through a thorough UX Design stage
  in order to be of quality"

The MCP surface is exposed via the R286 aggregator (scripts/interop/
mcp-aggregate.py LOCAL_TOOLS registry) as three read-only tool
entries — each tool delegates to a
`sovereign-osctl ux-design-audit <verb> --json` invocation, backed by
the R457 6-UX-dimension auditor.

Three discrete tools (dimensions / modules / score). The `audit` and
`report` verbs take optional runtime `--module` / `--threshold`
arguments — `audit` per-module is a runtime-arg-shaped verb so it
stays CLI-only (same reason `doc-coverage scan`, `router classify`,
`compliance module` stay CLI-only). `report` is a derived view of
`score` and intentionally not duplicated. The R528 `watch` refresh-
loop TUI is NOT exposed — loop tools are an MCP anti-pattern.
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
    "ux-design-audit-dimensions",
    "ux-design-audit-modules",
    "ux-design-audit-score",
}


def test_mcp_surface_lists_ux_design_audit_tools():
    """R529 MCP surface MUST advertise ALL 3 read-only ux-design-audit
    inspection verbs."""
    tools = _tools_by_name(_manifest())
    missing = REQUIRED_TOOLS - set(tools.keys())
    assert not missing, (
        f"MCP manifest missing ux-design-audit tools: {sorted(missing)}"
    )


def test_mcp_ux_design_audit_tools_have_operator_g_category():
    tools = _tools_by_name(_manifest())
    for name in REQUIRED_TOOLS:
        t = tools[name]
        cats = t.get("categories", [])
        assert "operator-§1g" in cats, (
            f"MCP tool {name!r} missing 'operator-§1g' category"
        )
        assert "ux-design-audit" in cats, (
            f"MCP tool {name!r} missing 'ux-design-audit' category"
        )


def test_mcp_ux_design_audit_tools_invoke_via_osctl_with_json():
    """Each R529 tool MUST invoke `sovereign-osctl ux-design-audit
    <verb> --json` — load-bearing wire contract."""
    tools = _tools_by_name(_manifest())
    verb_for = {
        "ux-design-audit-dimensions": "dimensions",
        "ux-design-audit-modules":    "modules",
        "ux-design-audit-score":      "score",
    }
    for name, verb in verb_for.items():
        argv = tools[name].get("argv") or []
        assert argv[:2] == ["sovereign-osctl", "ux-design-audit"], (
            f"MCP tool {name!r} argv must start with sovereign-osctl "
            f"ux-design-audit; got {argv}"
        )
        assert verb in argv, (
            f"MCP tool {name!r} argv missing verb {verb!r}: {argv}"
        )
        assert "--json" in argv, (
            f"MCP tool {name!r} argv missing --json flag: {argv}"
        )


def test_mcp_ux_design_audit_tools_are_read_only():
    """Inspection is the surface; ux-design-audit is a query-only
    instrument. No mutation-shaped verbs at the MCP surface
    (operator §17 sovereignty boundary)."""
    tools = _tools_by_name(_manifest())
    forbidden = {
        "ux-design-audit-set",
        "ux-design-audit-apply",
        "ux-design-audit-mutate",
        "ux-design-audit-install",
        "ux-design-audit-clear",
        "ux-design-audit-write",
    }
    leaked = forbidden & set(tools.keys())
    assert not leaked, (
        f"MCP manifest leaks mutation verbs: {sorted(leaked)}"
    )


def test_mcp_ux_design_audit_runtime_arg_verbs_not_exposed():
    """The runtime-argument-shaped verbs (`audit --module <m>`,
    `report --threshold N`) MUST NOT be exposed via MCP — LOCAL_TOOLS
    uses fixed argv (same reason `doc-coverage scan`, `router
    classify`, `compliance module`, `anti-minimization-audit scan`
    stay CLI-only)."""
    tools = _tools_by_name(_manifest())
    for name in (
        "ux-design-audit-audit",
        "ux-design-audit-report",
    ):
        assert name not in tools, (
            f"{name!r} must NOT be exposed via MCP — runtime-"
            f"argument-shaped, incompatible with LOCAL_TOOLS fixed-"
            f"argv contract"
        )


def test_mcp_ux_design_audit_watch_not_exposed_via_mcp():
    """The R528 `watch` refresh-loop TUI verb is intentionally NOT
    exposed via MCP — loop tools are an MCP anti-pattern."""
    tools = _tools_by_name(_manifest())
    assert "ux-design-audit-watch" not in tools, (
        "ux-design-audit-watch must NOT be exposed via MCP — refresh-"
        "loop TUI"
    )


def test_mcp_ux_design_audit_tools_have_descriptive_summaries():
    tools = _tools_by_name(_manifest())
    for name in REQUIRED_TOOLS:
        summary = tools[name].get("summary", "")
        assert summary, f"MCP tool {name!r} has empty summary"
        assert len(summary) >= 30, (
            f"MCP tool {name!r} summary too short ({len(summary)} "
            f"chars); operator-§1g rule: descriptive"
        )
        low = summary.lower()
        assert "ux" in low or "ux-design-audit" in low, (
            f"MCP tool {name!r} summary must mention UX: {summary!r}"
        )


def test_osctl_ux_design_audit_json_emits_parseable_json():
    """Each of the 3 R529-exposed verbs MUST emit parseable JSON
    when invoked via osctl — load-bearing wire contract for the
    MCP tools."""
    env = {"PATH": "/usr/bin:/bin", "HOME": "/tmp"}
    for verb in ("dimensions", "modules", "score"):
        cp = subprocess.run(
            ["bash", str(OSCTL), "ux-design-audit", verb, "--json"],
            capture_output=True, text=True, timeout=120, env=env,
        )
        assert cp.returncode == 0, (
            f"ux-design-audit {verb} --json exit nonzero: "
            f"{cp.stderr[:300]}"
        )
        data = json.loads(cp.stdout)
        assert isinstance(data, dict), (
            f"ux-design-audit {verb} --json must emit a JSON object; "
            f"got {type(data).__name__}"
        )


def test_ux_design_audit_surface_map_extended_to_mcp():
    """R529 extends ux-design-audit surface-map to 5 shipped
    surfaces — mcp MUST appear as shipped, NOT as a FUTURE waiver."""
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module",
         "ux-design-audit", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr[:300]
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    assert entry.get("surface_count", 0) >= 5, (
        f"ux-design-audit must be at >=5 surfaces post-R529; "
        f"got {entry}"
    )
    matrix = entry.get("matrix", [])
    mcp_row = next(
        (r for r in matrix if r.get("surface") == "mcp"), None
    )
    assert mcp_row is not None, (
        "ux-design-audit coverage matrix missing 'mcp' row"
    )
    assert mcp_row.get("state") == "shipped", (
        f"ux-design-audit mcp surface must be shipped; got {mcp_row}"
    )
