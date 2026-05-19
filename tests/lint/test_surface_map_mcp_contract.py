"""R532 (E5++) — surface-map MCP surface contract lint.

Closes the surface-map mcp:FUTURE waiver. Raises the surface-map
surface count from 4 -> 5 shipped surfaces (core / cli / tui /
dashboard / mcp). Second commit in the surface-map tier-3 surface-
expansion arc; R533 (api + webapp; and the service-not-applicable
replacement via a real read-only daemon) will close the surface-map
ladder to the §1g ceiling — same shape as the ux-design-audit
R528-R530 triple, the doc-coverage R525-R527 triple, the anti-min
R522-R524 triple, the compliance R519-R521 triple, the router
R516-R518 triple, and the trinity R513-R515 triple.

Per operator §1g STANDING RULE verbatim (sacrosanct, R456-anchored):

  "If you think something is really already done, ask yourself if
   you covered all angles and levels and layers and even if then
   improve it. Do not minimize or settle for less."

Per operator §1g verbatim (R453 anchor):

  "everything is not just core, not just cli, not just TUI, not just
  API, not just tool and MCP but also Dashboards and Web Apps and
  Services"

The MCP surface is exposed via the R286 aggregator (scripts/interop/
mcp-aggregate.py LOCAL_TOOLS registry) as three read-only tool
entries — each tool delegates to a
`sovereign-osctl surface-map <verb> --json` invocation, backed by
the R453 8-§1g-surface coverage matrix.

Three discrete tools (surfaces / modules / coverage). The `gaps` and
`waivers` verbs take optional runtime `--module` / `--threshold` /
`--surface` arguments — these are runtime-arg-shaped and stay CLI-
only (same reason `doc-coverage scan`, `router classify`,
`compliance module`, `ux-design-audit audit` stay CLI-only). The
`selfdef` verb scans an env-controlled directory and is a derived
view; not duplicated at MCP. The R531 `watch` refresh-loop TUI is
NOT exposed — loop tools are an MCP anti-pattern.
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
    "surface-map-surfaces",
    "surface-map-modules",
    "surface-map-coverage",
}


def test_mcp_surface_lists_surface_map_tools():
    """R532 MCP surface MUST advertise ALL 3 read-only surface-map
    inspection verbs."""
    tools = _tools_by_name(_manifest())
    missing = REQUIRED_TOOLS - set(tools.keys())
    assert not missing, (
        f"MCP manifest missing surface-map tools: {sorted(missing)}"
    )


def test_mcp_surface_map_tools_have_operator_g_category():
    tools = _tools_by_name(_manifest())
    for name in REQUIRED_TOOLS:
        t = tools[name]
        cats = t.get("categories", [])
        assert "operator-§1g" in cats, (
            f"MCP tool {name!r} missing 'operator-§1g' category"
        )
        assert "surface-map" in cats, (
            f"MCP tool {name!r} missing 'surface-map' category"
        )


def test_mcp_surface_map_tools_invoke_via_osctl_with_json():
    """Each R532 tool MUST invoke `sovereign-osctl surface-map <verb>
    --json` — load-bearing wire contract."""
    tools = _tools_by_name(_manifest())
    verb_for = {
        "surface-map-surfaces": "surfaces",
        "surface-map-modules":  "modules",
        "surface-map-coverage": "coverage",
    }
    for name, verb in verb_for.items():
        argv = tools[name].get("argv") or []
        assert argv[:2] == ["sovereign-osctl", "surface-map"], (
            f"MCP tool {name!r} argv must start with sovereign-osctl "
            f"surface-map; got {argv}"
        )
        assert verb in argv, (
            f"MCP tool {name!r} argv missing verb {verb!r}: {argv}"
        )
        assert "--json" in argv, (
            f"MCP tool {name!r} argv missing --json flag: {argv}"
        )


def test_mcp_surface_map_tools_are_read_only():
    """Inspection is the surface; surface-map is a query-only
    instrument. No mutation-shaped verbs at the MCP surface
    (operator §17 sovereignty boundary)."""
    tools = _tools_by_name(_manifest())
    forbidden = {
        "surface-map-set",
        "surface-map-apply",
        "surface-map-mutate",
        "surface-map-install",
        "surface-map-clear",
        "surface-map-write",
    }
    leaked = forbidden & set(tools.keys())
    assert not leaked, (
        f"MCP manifest leaks mutation verbs: {sorted(leaked)}"
    )


def test_mcp_surface_map_runtime_arg_verbs_not_exposed():
    """The runtime-argument-shaped verbs (`gaps --module <m>
    --threshold N`, `waivers --module <m>`) MUST NOT be exposed via
    MCP — LOCAL_TOOLS uses fixed argv (same reason `doc-coverage
    scan`, `router classify`, `compliance module`, `anti-minimization-
    audit scan`, `ux-design-audit audit` stay CLI-only).

    R544 ceiling-promotion: `selfdef` is parameterless at the argv
    level (it consults SOVEREIGN_OS_SELFDEF_SURFACE_DIR — a deployment-
    time env constant, NOT a per-call argument). Same shape as
    `surface-map milestone --json` (R541): the tool returns the
    operator's deployment view, agents can't and shouldn't override
    the discovery dir per-call. Promoted out of this prohibition list."""
    tools = _tools_by_name(_manifest())
    for name in (
        "surface-map-gaps",
        "surface-map-waivers",
    ):
        assert name not in tools, (
            f"{name!r} must NOT be exposed via MCP — runtime-"
            f"argument-shaped, incompatible with LOCAL_TOOLS fixed-"
            f"argv contract"
        )
    # R544 positive promotion: selfdef IS now exposed via MCP.
    assert "surface-map-selfdef" in tools, (
        "R544: surface-map-selfdef must be exposed via MCP (parameter-"
        "less argv; env-var driven discovery is deployment-time config "
        "NOT per-call argument — operator §17 read-only discovery)"
    )


def test_mcp_surface_map_watch_not_exposed_via_mcp():
    """The R531 `watch` refresh-loop TUI verb is intentionally NOT
    exposed via MCP — loop tools are an MCP anti-pattern."""
    tools = _tools_by_name(_manifest())
    assert "surface-map-watch" not in tools, (
        "surface-map-watch must NOT be exposed via MCP — refresh-loop "
        "TUI"
    )


def test_mcp_surface_map_tools_have_descriptive_summaries():
    tools = _tools_by_name(_manifest())
    for name in REQUIRED_TOOLS:
        summary = tools[name].get("summary", "")
        assert summary, f"MCP tool {name!r} has empty summary"
        assert len(summary) >= 30, (
            f"MCP tool {name!r} summary too short ({len(summary)} "
            f"chars); operator-§1g rule: descriptive"
        )
        low = summary.lower()
        assert ("surface" in low) or ("§1g" in low), (
            f"MCP tool {name!r} summary must mention surface/§1g: "
            f"{summary!r}"
        )


def test_osctl_surface_map_json_emits_parseable_json():
    """Each of the 3 R532-exposed verbs MUST emit parseable JSON
    when invoked via osctl — load-bearing wire contract for the
    MCP tools."""
    env = {"PATH": "/usr/bin:/bin", "HOME": "/tmp"}
    for verb in ("surfaces", "modules", "coverage"):
        cp = subprocess.run(
            ["bash", str(OSCTL), "surface-map", verb, "--json"],
            capture_output=True, text=True, timeout=120, env=env,
        )
        assert cp.returncode == 0, (
            f"surface-map {verb} --json exit nonzero: "
            f"{cp.stderr[:300]}"
        )
        data = json.loads(cp.stdout)
        assert isinstance(data, dict), (
            f"surface-map {verb} --json must emit a JSON object; "
            f"got {type(data).__name__}"
        )


def test_surface_map_self_extended_to_mcp():
    """R532 extends surface-map's OWN entry to 5 shipped surfaces —
    mcp MUST appear as shipped, NOT as a FUTURE waiver (eating-our-
    own-dogfood / the §1g coverage instrument MUST report its own
    progress honestly)."""
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module",
         "surface-map", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr[:300]
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    assert entry.get("surface_count", 0) >= 5, (
        f"surface-map must be at >=5 surfaces post-R532; got {entry}"
    )
    matrix = entry.get("matrix", [])
    mcp_row = next(
        (r for r in matrix if r.get("surface") == "mcp"), None
    )
    assert mcp_row is not None, (
        "surface-map coverage matrix missing 'mcp' row"
    )
    assert mcp_row.get("state") == "shipped", (
        f"surface-map mcp surface must be shipped; got {mcp_row}"
    )
