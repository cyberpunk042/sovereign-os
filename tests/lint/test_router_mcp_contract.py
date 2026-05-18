"""R517 (E5++) — Inference Router MCP surface contract lint.

Closes the router mcp:FUTURE waiver. Raises the router surface count
from 6 → 7 shipped surfaces (core / cli / tui / api / service /
dashboard / mcp). Second commit in the router tier-3 surface-expansion
arc; R518 (webapp) will close the router ladder to the full §1g
8-surface ceiling — same shape as the trinity R513/R514/R515 triple
just completed.

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

The MCP surface is exposed via the R286 aggregator (scripts/interop/
mcp-aggregate.py LOCAL_TOOLS registry) as read-only tool entries.
Each tool delegates to a `sovereign-osctl router <verb> --json`
invocation, backed by the new `scripts/inference/router-inspect.py`
Python helper.

Three discrete tools (status / rules / metrics) — the `classify`
verb takes a runtime prompt arg and is intentionally NOT exposed via
MCP (LOCAL_TOOLS uses fixed argv); the `watch` refresh-loop TUI is
intentionally NOT exposed (loop tools are an MCP anti-pattern).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MCP_AGGREGATE = REPO_ROOT / "scripts" / "interop" / "mcp-aggregate.py"
INSPECT = REPO_ROOT / "scripts" / "inference" / "router-inspect.py"
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
    "router-status",
    "router-rules",
    "router-metrics",
}


def test_inspect_helper_present_and_executable():
    assert INSPECT.is_file(), (
        f"R517 router-inspect helper missing: {INSPECT}"
    )
    assert INSPECT.stat().st_mode & 0o111, (
        "router-inspect.py must be executable"
    )


def test_inspect_helper_emits_valid_json_for_each_verb():
    """The Python helper backing the `--json` mode MUST emit parseable
    JSON for each of the 3 inspection verbs."""
    for verb in ("status", "rules", "metrics"):
        cp = subprocess.run(
            ["python3", str(INSPECT), verb],
            capture_output=True, text=True, timeout=10,
        )
        assert cp.returncode == 0, (
            f"router-inspect {verb} exit nonzero: {cp.stderr[:300]}"
        )
        data = json.loads(cp.stdout)
        assert data.get("module") == "router", (
            f"router-inspect {verb} payload missing module=router: {data}"
        )


def test_inspect_status_payload_shape():
    cp = subprocess.run(
        ["python3", str(INSPECT), "status"],
        capture_output=True, text=True, timeout=10,
    )
    data = json.loads(cp.stdout)
    assert data.get("spec_ref") == "SDD-011"
    assert data["service"]["name"] == "sovereign-router.service"
    assert data["listen"]["port"] == 8080
    assert set(data["backends"].keys()) == {
        "pulse", "logic-engine", "oracle-core"
    }


def test_inspect_rules_payload_lists_five_rules():
    cp = subprocess.run(
        ["python3", str(INSPECT), "rules"],
        capture_output=True, text=True, timeout=10,
    )
    data = json.loads(cp.stdout)
    rules = data.get("rules", [])
    assert len(rules) == 5, (
        f"rules payload must list ALL 5 SDD-011 rules; got {len(rules)}"
    )
    assert data.get("match_order") == "first match wins"
    rule_tiers = [r["tier"] for r in rules]
    assert "pulse" in rule_tiers
    assert "oracle-core" in rule_tiers
    assert "logic-engine" in rule_tiers


def test_mcp_surface_lists_router_tools():
    """R517 MCP surface MUST advertise ALL 3 read-only router
    inspection verbs — operator §1g rule: full ladder visible."""
    tools = _tools_by_name(_manifest())
    missing = REQUIRED_TOOLS - set(tools.keys())
    assert not missing, (
        f"MCP manifest missing router tools: {sorted(missing)}"
    )


def test_mcp_router_tools_have_operator_g_category():
    tools = _tools_by_name(_manifest())
    for name in REQUIRED_TOOLS:
        t = tools[name]
        assert "operator-§1g" in t.get("categories", []), (
            f"MCP tool {name!r} missing 'operator-§1g' category"
        )
        assert "router" in t.get("categories", []), (
            f"MCP tool {name!r} missing 'router' category"
        )
        assert "inference" in t.get("categories", []), (
            f"MCP tool {name!r} missing 'inference' category"
        )


def test_mcp_router_tools_invoke_via_osctl_with_json():
    """Each R517 tool MUST invoke `sovereign-osctl router <verb>
    --json` — that's the load-bearing wire contract."""
    tools = _tools_by_name(_manifest())
    verb_for = {
        "router-status":   "status",
        "router-rules":    "rules",
        "router-metrics":  "metrics",
    }
    for name, verb in verb_for.items():
        argv = tools[name].get("argv") or []
        assert argv[:2] == ["sovereign-osctl", "router"], (
            f"MCP tool {name!r} argv must start with sovereign-osctl "
            f"router; got {argv}"
        )
        assert verb in argv, (
            f"MCP tool {name!r} argv missing verb {verb!r}: {argv}"
        )
        assert "--json" in argv, (
            f"MCP tool {name!r} argv missing --json flag: {argv}"
        )


def test_mcp_router_tools_are_read_only():
    """Inspection is the surface; mutation lives at routing time
    (operator-driven via HTTP request shape). No mutation verbs at the
    MCP surface."""
    tools = _tools_by_name(_manifest())
    forbidden = {
        "router-set",
        "router-apply",
        "router-mutate",
        "router-switch",
        "router-install",
        "router-start",
        "router-stop",
    }
    leaked = forbidden & set(tools.keys())
    assert not leaked, (
        f"MCP manifest leaks mutation verbs: {sorted(leaked)}"
    )


def test_mcp_router_classify_is_not_exposed_via_mcp():
    """The `classify` verb takes a runtime prompt argument; LOCAL_TOOLS
    uses fixed argv, so classify stays CLI-only (same reason `trinity
    profile switch` and `trinity watch` are CLI-only)."""
    tools = _tools_by_name(_manifest())
    assert "router-classify" not in tools, (
        "router-classify must NOT be exposed via MCP — it takes a "
        "runtime prompt argument incompatible with the LOCAL_TOOLS "
        "fixed-argv contract"
    )


def test_mcp_router_watch_is_not_exposed_via_mcp():
    """The R516 `watch` refresh-loop TUI verb is intentionally NOT
    exposed via MCP — loop tools are an MCP anti-pattern."""
    tools = _tools_by_name(_manifest())
    assert "router-watch" not in tools, (
        "router-watch must NOT be exposed via MCP — refresh-loop TUI"
    )


def test_mcp_router_tools_have_descriptive_summaries():
    tools = _tools_by_name(_manifest())
    for name in REQUIRED_TOOLS:
        summary = tools[name].get("summary", "")
        assert summary, f"MCP tool {name!r} has empty summary"
        assert len(summary) >= 30, (
            f"MCP tool {name!r} summary too short ({len(summary)} "
            f"chars); operator-§1g rule: descriptive"
        )
        low = summary.lower()
        assert "router" in low or "routing" in low, (
            f"MCP tool {name!r} summary must mention router/routing: "
            f"{summary!r}"
        )


def test_osctl_router_json_routes_to_helper():
    """`sovereign-osctl router status --json` MUST emit the same JSON
    payload the helper produces (load-bearing wire contract for the
    MCP tools)."""
    for verb in ("status", "rules", "metrics"):
        cp = subprocess.run(
            ["bash", str(OSCTL), "router", verb, "--json"],
            capture_output=True, text=True, timeout=10,
            env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"},
        )
        assert cp.returncode == 0, (
            f"router {verb} --json exit nonzero: {cp.stderr[:300]}"
        )
        data = json.loads(cp.stdout)
        assert data.get("module") == "router", (
            f"router {verb} --json missing module=router: {data}"
        )


def test_router_surface_map_extended_to_mcp():
    """R517 extends router surface-map to 7 shipped surfaces — mcp
    MUST appear as shipped, NOT as a FUTURE waiver."""
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module",
         "router", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr[:300]
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    assert entry.get("surface_count", 0) >= 7, (
        f"router must be at >=7 surfaces post-R517; got {entry}"
    )
    matrix = entry.get("matrix", [])
    mcp_row = next(
        (r for r in matrix if r.get("surface") == "mcp"), None
    )
    assert mcp_row is not None
    assert mcp_row.get("state") == "shipped", (
        f"router mcp surface must be shipped; got {mcp_row}"
    )
