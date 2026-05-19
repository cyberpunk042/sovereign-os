"""R544 (E5++) — surface-map selfdef MCP tool contract lint.

Exposes the R462 cross-repo SurfaceManifest discovery
(`surface-map selfdef --json`) over MCP so agents can read the §1g
delivery state of sibling ecosystem repos in one fixed-argv call.

R462 anchor: sibling repos write SurfaceManifests under
/etc/selfdef/surfaces describing their own §1g surface coverage;
surface-map is the DISCOVERER of those manifests (not the AUTHOR —
manifests are produced by their owning repo's CI, NOT by surface-map).
Operator §17 sovereignty boundary: discovery is read-only.

Per operator §1g 8-surface delivery contract anchor verbatim (R453):

  "everything is not just core, not just cli, not just TUI, not just
   API, not just tool and MCP but also Dashboards and Web Apps and
   Services"

Operator-§1g UX rule: one MCP call surfaces the entire cross-repo
state — agents don't need filesystem scans.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MCP_AGG = REPO_ROOT / "scripts" / "interop" / "mcp-aggregate.py"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"

TOOL_NAME = "surface-map-selfdef"


def _load_mcp_aggregate():
    spec = importlib.util.spec_from_file_location("_mcp_agg", MCP_AGG)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_mcp_tool_registered():
    mod = _load_mcp_aggregate()
    names = {t["name"] for t in mod.LOCAL_TOOLS}
    assert TOOL_NAME in names, (
        f"R544: MCP aggregator must register {TOOL_NAME!r}; "
        f"got {sorted(names)}"
    )


def test_mcp_tool_fixed_argv_shape_r286():
    """Per R286: MCP aggregator tools MUST have fixed argv (no runtime
    args). The selfdef verb is parameterless — clean MCP fit."""
    mod = _load_mcp_aggregate()
    tool = next(t for t in mod.LOCAL_TOOLS if t["name"] == TOOL_NAME)
    argv = tool["argv"]
    assert argv[0] == "sovereign-osctl"
    assert argv[1] == "surface-map"
    assert argv[2] == "selfdef"
    assert argv[-1] == "--json", (
        f"{TOOL_NAME} must terminate with --json (R286); got {argv}"
    )
    for arg in argv:
        assert "<" not in arg and ">" not in arg, (
            f"{TOOL_NAME} argv has runtime-arg slot {arg!r} — "
            f"MCP tools have fixed argv only (per R286)"
        )


def test_mcp_tool_summary_substantive():
    """Operator-§1g UX rule: 30-second readable. Summary MUST mention
    R462 + cross-repo + SurfaceManifest + the §1g framing."""
    mod = _load_mcp_aggregate()
    tool = next(t for t in mod.LOCAL_TOOLS if t["name"] == TOOL_NAME)
    summary = tool.get("summary", "")
    assert len(summary) >= 80, f"summary too thin: {summary!r}"
    low = summary.lower()
    assert "r462" in low, "summary must cite R462"
    assert "cross-repo" in low or "cross repo" in low, (
        "summary must mention cross-repo dimension"
    )
    assert "surfacemanifest" in low or "surface manifest" in low, (
        "summary must mention SurfaceManifest"
    )
    assert "§1g" in summary or "1g" in low
    assert "read-only" in low or "discovery" in low, (
        "summary must surface the read-only/discovery framing"
    )
    # §17 sovereignty boundary must surface — manifests are AUTHORED
    # by the owning repo, surface-map only DISCOVERS them.
    assert (
        "§17" in summary or "section 17" in low
        or "sovereignty" in low or "operator §17" in low
    ), (
        f"{TOOL_NAME} summary must surface the §17 boundary; "
        f"got {summary!r}"
    )


def test_mcp_tool_categories_anchor_cross_repo():
    mod = _load_mcp_aggregate()
    tool = next(t for t in mod.LOCAL_TOOLS if t["name"] == TOOL_NAME)
    cats = set(tool.get("categories", []))
    assert "surface-map" in cats
    assert "selfdef" in cats
    assert "cross-repo" in cats, (
        f"{TOOL_NAME} categories must include 'cross-repo'; "
        f"got {sorted(cats)}"
    )


def test_mcp_tool_end_to_end_smoke():
    """End-to-end smoke: invoking the tool's argv must produce
    JSON-parseable output matching the R462 SurfaceManifest discovery
    shape (manifest_dir + discovered[] + errors[] + count)."""
    mod = _load_mcp_aggregate()
    tool = next(t for t in mod.LOCAL_TOOLS if t["name"] == TOOL_NAME)
    argv = list(tool["argv"])
    if argv[0] == "sovereign-osctl":
        argv[0] = str(OSCTL)
        argv.insert(0, "bash")
    cp = subprocess.run(
        argv, capture_output=True, text=True, timeout=15,
        env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"},
    )
    assert cp.returncode == 0, (
        f"{TOOL_NAME} ({tool['argv']}) failed: {cp.stderr[:300]}"
    )
    payload = json.loads(cp.stdout)
    assert isinstance(payload, dict)
    # R462 SurfaceManifest discovery shape — operator-named keys.
    for key in ("manifest_dir", "discovered", "errors", "count"):
        assert key in payload, (
            f"R544 payload missing R462 key {key!r}; got "
            f"{sorted(payload.keys())}"
        )
    assert isinstance(payload["discovered"], list)
    assert isinstance(payload["errors"], list)
    assert isinstance(payload["count"], int)


def test_mcp_aggregator_has_no_duplicate_tool_names_post_r544():
    """Adding a new tool MUST NOT create a name collision — operator-
    §1g UX rule: every MCP tool name is unique across the aggregator."""
    mod = _load_mcp_aggregate()
    names = [t["name"] for t in mod.LOCAL_TOOLS]
    seen = set()
    dupes = []
    for n in names:
        if n in seen:
            dupes.append(n)
        seen.add(n)
    assert not dupes, (
        f"R544 must not introduce name collisions; got duplicates: "
        f"{dupes}"
    )


def test_surface_map_mcp_tool_family_complete_post_r544():
    """The surface-map MCP family covers exactly the parameterless
    inspection verbs: surfaces / modules / coverage / milestone /
    selfdef. Verbs that take runtime args (waivers --module <m>,
    gaps --threshold N, coverage --module <m>) stay CLI-only per
    the R286 / R532 ceiling-promotion rule."""
    mod = _load_mcp_aggregate()
    family = {
        t["name"] for t in mod.LOCAL_TOOLS
        if t["name"].startswith("surface-map-")
    }
    expected = {
        "surface-map-surfaces",
        "surface-map-modules",
        "surface-map-coverage",
        "surface-map-milestone",
        "surface-map-selfdef",
    }
    missing = expected - family
    extra = family - expected
    assert not missing, f"R544: missing surface-map MCP tools: {missing}"
    assert not extra, (
        f"R544: unexpected surface-map MCP tools (any that takes "
        f"runtime args must stay CLI-only per R286): {extra}"
    )
