"""R514 (E5++) — Trinity MCP surface contract lint.

Closes the trinity mcp:FUTURE waiver. Raises the trinity surface
count from 6 → 7 shipped surfaces (core / cli / api / service /
dashboard / tui / mcp). Second commit in the trinity tier-3 surface-
expansion arc; R515 (webapp) will close the trinity ladder to the
full §1g 8-surface ceiling.

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

The MCP surface is exposed via the R286 aggregator
(scripts/interop/mcp-aggregate.py LOCAL_TOOLS registry) as read-only
tool entries. Each tool delegates to a `sovereign-osctl trinity
<verb> --json` invocation. Trinity inspection has no mutation verbs
at any surface — operator §17 sacrosanct sovereignty boundary; the
pinned-process state fabric is mutated by the runtime profile
switcher, not by inspection.

Per operator §1g "We do not minimize anything." — the 4 inspection
verbs (status / pulse / weaver / auditor) are exposed as FOUR
discrete MCP tools, not collapsed into a single bundle. The R513
`watch` refresh-loop TUI surface is intentionally NOT exposed via
MCP (loop tools are an MCP anti-pattern).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MCP_AGGREGATE = REPO_ROOT / "scripts" / "interop" / "mcp-aggregate.py"
INSPECT = REPO_ROOT / "scripts" / "trinity" / "trinity-inspect.py"


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
    "trinity-status",
    "trinity-pulse",
    "trinity-weaver",
    "trinity-auditor",
}


def test_inspect_helper_present_and_executable():
    assert INSPECT.is_file(), (
        f"R514 trinity-inspect helper missing: {INSPECT}"
    )
    assert INSPECT.stat().st_mode & 0o111, (
        "trinity-inspect.py must be executable"
    )


def test_inspect_helper_emits_valid_json_for_each_verb():
    """The Python helper backing the `--json` mode MUST emit parseable
    JSON for each of the 4 inspection verbs."""
    for verb in ("status", "pulse", "weaver", "auditor"):
        cp = subprocess.run(
            ["python3", str(INSPECT), verb],
            capture_output=True, text=True, timeout=10,
        )
        assert cp.returncode == 0, (
            f"trinity-inspect {verb} exit nonzero: {cp.stderr[:300]}"
        )
        data = json.loads(cp.stdout)
        if verb == "status":
            assert data.get("module") == "trinity"
            assert set(data.get("tiers", {}).keys()) == {
                "pulse", "weaver", "auditor"
            }
        else:
            assert data.get("tier") == verb
            assert "service" in data, data


def test_mcp_surface_lists_trinity_tools():
    """R514 MCP surface MUST advertise ALL 4 read-only trinity
    inspection verbs — operator §1g rule: full ladder visible, not
    minimized."""
    tools = _tools_by_name(_manifest())
    missing = REQUIRED_TOOLS - set(tools.keys())
    assert not missing, (
        f"MCP manifest missing trinity tools: {sorted(missing)}"
    )


def test_mcp_trinity_tools_have_operator_g_category():
    tools = _tools_by_name(_manifest())
    for name in REQUIRED_TOOLS:
        t = tools[name]
        assert "operator-§1g" in t.get("categories", []), (
            f"MCP tool {name!r} missing 'operator-§1g' category"
        )
        assert "trinity" in t.get("categories", []), (
            f"MCP tool {name!r} missing 'trinity' category"
        )


def test_mcp_trinity_tools_invoke_via_osctl_with_json():
    """Each R514 tool MUST invoke `sovereign-osctl trinity <verb>
    --json` — that's the load-bearing wire contract."""
    tools = _tools_by_name(_manifest())
    verb_for = {
        "trinity-status":   "status",
        "trinity-pulse":    "pulse",
        "trinity-weaver":   "weaver",
        "trinity-auditor":  "auditor",
    }
    for name, verb in verb_for.items():
        argv = tools[name].get("argv") or []
        assert argv[:2] == ["sovereign-osctl", "trinity"], (
            f"MCP tool {name!r} argv must start with sovereign-osctl "
            f"trinity; got {argv}"
        )
        assert verb in argv, (
            f"MCP tool {name!r} argv missing verb {verb!r}: {argv}"
        )
        assert "--json" in argv, (
            f"MCP tool {name!r} argv missing --json flag: {argv}"
        )


def test_mcp_trinity_tools_are_read_only():
    """Trinity inspection has no mutation verbs at any surface —
    operator §17 sacrosanct sovereignty boundary."""
    tools = _tools_by_name(_manifest())
    forbidden = {
        "trinity-set",
        "trinity-apply",
        "trinity-mutate",
        "trinity-switch",
        "trinity-start",
        "trinity-stop",
    }
    leaked = forbidden & set(tools.keys())
    assert not leaked, (
        f"MCP manifest leaks mutation verbs (§17 boundary violation): "
        f"{sorted(leaked)}"
    )


def test_mcp_trinity_watch_is_not_exposed_via_mcp():
    """The R513 `watch` refresh-loop TUI verb is intentionally NOT
    exposed via MCP — loop tools are an MCP anti-pattern (the agent
    cannot consume a never-returning subprocess)."""
    tools = _tools_by_name(_manifest())
    assert "trinity-watch" not in tools, (
        "trinity-watch must NOT be exposed via MCP — it's a refresh-"
        "loop TUI surface, not a one-shot inspection"
    )


def test_mcp_trinity_tools_have_descriptive_summaries():
    tools = _tools_by_name(_manifest())
    for name in REQUIRED_TOOLS:
        summary = tools[name].get("summary", "")
        assert summary, f"MCP tool {name!r} has empty summary"
        assert len(summary) >= 30, (
            f"MCP tool {name!r} summary too short ({len(summary)} "
            f"chars); operator-§1g rule: descriptive"
        )
        low = summary.lower()
        assert "trinity" in low or "pulse" in low or "weaver" in low \
            or "auditor" in low, (
            f"MCP tool {name!r} summary must mention trinity or its "
            f"domain: {summary!r}"
        )


def test_trinity_surface_map_extended_to_mcp():
    """R514 extends trinity surface-map to 7 shipped surfaces —
    mcp MUST appear as shipped, NOT as a FUTURE waiver."""
    sm_path = REPO_ROOT / "scripts" / "operator" / "surface-map.py"
    result = subprocess.run(
        ["python3", str(sm_path), "coverage", "--module",
         "trinity", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr[:300]
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    assert entry.get("surface_count", 0) >= 7, (
        f"trinity must be at >=7 surfaces post-R514; got {entry}"
    )
    matrix = entry.get("matrix", [])
    mcp_row = next(
        (r for r in matrix if r.get("surface") == "mcp"), None
    )
    assert mcp_row is not None
    assert mcp_row.get("state") == "shipped", (
        f"trinity mcp surface must be shipped; got {mcp_row}"
    )
    # The mcp-shipped invariant is the load-bearing assertion here.
    # Historically R514 left webapp as FUTURE; R515 closed it — so the
    # precise FUTURE-waiver remainder is no longer a stable assertion
    # here. It is asserted directly in the R515 contract test at the
    # close-out round.


def test_osctl_trinity_status_json_routes_to_helper():
    """`sovereign-osctl trinity status --json` MUST emit the same JSON
    payload the helper produces (load-bearing wire contract for the
    MCP tools)."""
    osctl = REPO_ROOT / "scripts" / "sovereign-osctl"
    cp = subprocess.run(
        ["bash", str(osctl), "trinity", "status", "--json"],
        capture_output=True, text=True, timeout=10,
        env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"},
    )
    assert cp.returncode == 0, cp.stderr[:300]
    data = json.loads(cp.stdout)
    assert data.get("module") == "trinity"
    assert set(data.get("tiers", {}).keys()) == {
        "pulse", "weaver", "auditor"
    }
