"""R526 (E5++) — doc-coverage MCP surface contract lint.

Closes the doc-coverage mcp:FUTURE waiver. Raises the doc-coverage
surface count from 4 -> 5 shipped surfaces (core / cli / tui /
dashboard / mcp). Second commit in the doc-coverage tier-3 surface-
expansion arc; R527 (api + webapp + service) will close the doc-
coverage ladder to the §1g ceiling — same shape as the anti-min
R522-R524 triple and the compliance R519-R521 triple just completed.

Per operator §1g STANDING RULE verbatim (sacrosanct, R456-anchored):

  "If you think something is really already done, ask yourself if
   you covered all angles and levels and layers and even if then
   improve it. Do not minimize or settle for less."

The MCP surface is exposed via the R286 aggregator (scripts/interop/
mcp-aggregate.py LOCAL_TOOLS registry) as three read-only tool
entries — each tool delegates to a
`sovereign-osctl doc-coverage <verb> --json` invocation, backed by
the R454 6-doc-surface scanner.

Three discrete tools (kinds / modules / coverage). The `scan` and
`gaps` verbs take runtime `--module` / `--threshold` arguments and
are intentionally NOT exposed via MCP — LOCAL_TOOLS uses fixed argv
(same reason `router classify`, `trinity profile switch`, `compliance
module` and `anti-minimization-audit scan` stay CLI-only). The R525
`watch` refresh-loop TUI is NOT exposed — loop tools are an MCP
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
    "doc-coverage-kinds",
    "doc-coverage-modules",
    "doc-coverage-coverage",
}


def test_mcp_surface_lists_doc_coverage_tools():
    """R526 MCP surface MUST advertise ALL 3 read-only doc-coverage
    inspection verbs."""
    tools = _tools_by_name(_manifest())
    missing = REQUIRED_TOOLS - set(tools.keys())
    assert not missing, (
        f"MCP manifest missing doc-coverage tools: {sorted(missing)}"
    )


def test_mcp_doc_coverage_tools_have_operator_g_category():
    tools = _tools_by_name(_manifest())
    for name in REQUIRED_TOOLS:
        t = tools[name]
        cats = t.get("categories", [])
        assert "operator-§1g" in cats, (
            f"MCP tool {name!r} missing 'operator-§1g' category"
        )
        assert "doc-coverage" in cats, (
            f"MCP tool {name!r} missing 'doc-coverage' category"
        )


def test_mcp_doc_coverage_tools_invoke_via_osctl_with_json():
    """Each R526 tool MUST invoke `sovereign-osctl doc-coverage <verb>
    --json` — load-bearing wire contract."""
    tools = _tools_by_name(_manifest())
    verb_for = {
        "doc-coverage-kinds":    "kinds",
        "doc-coverage-modules":  "modules",
        "doc-coverage-coverage": "coverage",
    }
    for name, verb in verb_for.items():
        argv = tools[name].get("argv") or []
        assert argv[:2] == ["sovereign-osctl", "doc-coverage"], (
            f"MCP tool {name!r} argv must start with sovereign-osctl "
            f"doc-coverage; got {argv}"
        )
        assert verb in argv, (
            f"MCP tool {name!r} argv missing verb {verb!r}: {argv}"
        )
        assert "--json" in argv, (
            f"MCP tool {name!r} argv missing --json flag: {argv}"
        )


def test_mcp_doc_coverage_tools_are_read_only():
    """Inspection is the surface; doc-coverage is a query-only
    instrument. No mutation-shaped verbs at the MCP surface
    (operator §17 sovereignty boundary)."""
    tools = _tools_by_name(_manifest())
    forbidden = {
        "doc-coverage-set",
        "doc-coverage-apply",
        "doc-coverage-mutate",
        "doc-coverage-install",
        "doc-coverage-clear",
        "doc-coverage-write",
    }
    leaked = forbidden & set(tools.keys())
    assert not leaked, (
        f"MCP manifest leaks mutation verbs: {sorted(leaked)}"
    )


def test_mcp_doc_coverage_runtime_arg_verbs_not_exposed():
    """The runtime-argument-shaped verbs (`scan --module <m>`,
    `gaps --threshold N`) MUST NOT be exposed via MCP — LOCAL_TOOLS
    uses fixed argv (same reason `router classify`, `trinity profile
    switch`, `compliance module`, `anti-minimization-audit scan` stay
    CLI-only)."""
    tools = _tools_by_name(_manifest())
    for name in (
        "doc-coverage-scan",
        "doc-coverage-gaps",
    ):
        assert name not in tools, (
            f"{name!r} must NOT be exposed via MCP — runtime-"
            f"argument-shaped, incompatible with LOCAL_TOOLS fixed-"
            f"argv contract"
        )


def test_mcp_doc_coverage_watch_not_exposed_via_mcp():
    """The R525 `watch` refresh-loop TUI verb is intentionally NOT
    exposed via MCP — loop tools are an MCP anti-pattern."""
    tools = _tools_by_name(_manifest())
    assert "doc-coverage-watch" not in tools, (
        "doc-coverage-watch must NOT be exposed via MCP — refresh-"
        "loop TUI"
    )


def test_mcp_doc_coverage_tools_have_descriptive_summaries():
    tools = _tools_by_name(_manifest())
    for name in REQUIRED_TOOLS:
        summary = tools[name].get("summary", "")
        assert summary, f"MCP tool {name!r} has empty summary"
        assert len(summary) >= 30, (
            f"MCP tool {name!r} summary too short ({len(summary)} "
            f"chars); operator-§1g rule: descriptive"
        )
        low = summary.lower()
        assert "doc-coverage" in low or "documentation" in low, (
            f"MCP tool {name!r} summary must mention doc-coverage: "
            f"{summary!r}"
        )


def test_osctl_doc_coverage_json_emits_parseable_json():
    """Each of the 3 R526-exposed verbs MUST emit parseable JSON
    when invoked via osctl — load-bearing wire contract for the
    MCP tools."""
    env = {"PATH": "/usr/bin:/bin", "HOME": "/tmp"}
    for verb in ("kinds", "modules", "coverage"):
        cp = subprocess.run(
            ["bash", str(OSCTL), "doc-coverage", verb, "--json"],
            capture_output=True, text=True, timeout=120, env=env,
        )
        assert cp.returncode == 0, (
            f"doc-coverage {verb} --json exit nonzero: "
            f"{cp.stderr[:300]}"
        )
        data = json.loads(cp.stdout)
        assert isinstance(data, dict), (
            f"doc-coverage {verb} --json must emit a JSON object; "
            f"got {type(data).__name__}"
        )


def test_doc_coverage_surface_map_extended_to_mcp():
    """R526 extends doc-coverage surface-map to 5 shipped surfaces —
    mcp MUST appear as shipped, NOT as a FUTURE waiver."""
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module",
         "doc-coverage", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr[:300]
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    assert entry.get("surface_count", 0) >= 5, (
        f"doc-coverage must be at >=5 surfaces post-R526; got {entry}"
    )
    matrix = entry.get("matrix", [])
    mcp_row = next(
        (r for r in matrix if r.get("surface") == "mcp"), None
    )
    assert mcp_row is not None, (
        "doc-coverage coverage matrix missing 'mcp' row"
    )
    assert mcp_row.get("state") == "shipped", (
        f"doc-coverage mcp surface must be shipped; got {mcp_row}"
    )
