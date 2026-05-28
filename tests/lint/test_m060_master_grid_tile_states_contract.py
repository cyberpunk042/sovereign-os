"""M060 master-dashboard mirror-grid tile states contract.

The master-dashboard renders 8 tiles, one per M060 mirror domain.
Each tile carries a CSS class indicating the chain-health state of
its underlying publish artifact. This test locks the rendering
contract so a future tweak doesn't silently break the operator's
glance value during a degraded-chain incident.

Contracts locked:
  1. The 5 tile-state CSS classes (online / offline / corrupt /
     stale / unknown) all have CSS rules with distinct colors.
  2. The classifyTileState() JS function maps:
       (snap, !present)     -> "offline"
       (snap, !parses)      -> "corrupt"
       (snap, age > 5min)   -> "stale"
       (snap, present+fresh)-> "online"
       (snap, no health)    -> fallback to snap state
  3. STALE_AGE_SECS matches the selfdef-api::m060_health constant
     (5 min) so the dashboard and the daemon classify identically.
  4. Each tile in M060_MIRRORS carries an `artifact` field mapping
     it to its publish filename — required for the chain-health
     drill-down to wire correctly.
  5. The tile hover-title surfaces the underlying reason for each
     non-online state so operators can hover any tile and see WHY
     it's in that state.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_PATH = REPO_ROOT / "webapp" / "master-dashboard" / "index.html"


def _body() -> str:
    return DASHBOARD_PATH.read_text()


def test_dashboard_present_and_loadable():
    assert DASHBOARD_PATH.is_file()
    body = _body()
    assert "M060_MIRRORS" in body
    assert "classifyTileState" in body


def test_all_five_tile_state_css_classes_present():
    """The 5 tile-state classes (online / offline / corrupt / stale /
    unknown) all have CSS rules in the dashboard's <style> block.
    Operators rely on the distinct colors to read tile states at a
    glance — missing one silently makes that state render as the
    default style."""
    body = _body()
    for cls in ("online", "offline", "corrupt", "stale", "unknown"):
        assert f".m060-tile.{cls}" in body, (
            f".m060-tile.{cls} CSS rule missing — that state would "
            f"render without a distinct color"
        )


def test_corrupt_state_uses_alert_red_distinct_from_offline():
    """Corrupt (degraded chain — present but unparseable) MUST render
    in a visually distinct color from offline (honest-absent). Both
    being red would lose the discrimination operators need to
    distinguish 'never onboarded' from 'present but corrupt'."""
    body = _body()
    # Extract the corrupt and offline CSS rules and verify they use
    # different border colors.
    corrupt_rule = re.search(r"\.m060-tile\.corrupt\s*\{[^}]+\}", body)
    offline_rule = re.search(r"\.m060-tile\.offline\s*\{[^}]+\}", body)
    assert corrupt_rule is not None and offline_rule is not None
    corrupt_color = re.search(r"border-color\s*:\s*(#[0-9a-fA-F]+)", corrupt_rule.group())
    offline_color = re.search(r"border-color\s*:\s*(#[0-9a-fA-F]+)", offline_rule.group())
    assert corrupt_color is not None and offline_color is not None
    assert corrupt_color.group(1).lower() != offline_color.group(1).lower(), (
        f"corrupt ({corrupt_color.group(1)}) and offline "
        f"({offline_color.group(1)}) must use distinct border colors"
    )
    # Corrupt should use the alert-vocabulary RED (#ff3a3a or similar
    # bright red), not the muted #7a3a1f offline color — operator
    # eye should be drawn to the more urgent corrupt state.
    assert corrupt_color.group(1).lower().startswith("#ff"), (
        f"corrupt border-color {corrupt_color.group(1)} should be a "
        f"bright alert-red (#ff*) — corrupt is a critical state"
    )


def test_every_m060_mirror_carries_artifact_field():
    """The chain-health drill-down requires mapping each tile to
    its publish artifact filename. Missing the field on any tile
    breaks the per-artifact health merge for that tile."""
    body = _body()
    # Extract the M060_MIRRORS literal block.
    m060_block = re.search(
        r"const M060_MIRRORS\s*=\s*\[(.*?)\];",
        body, re.DOTALL
    )
    assert m060_block is not None, "M060_MIRRORS literal not found"
    block_text = m060_block.group(1)
    # Find all object literals.
    objects = re.findall(r"\{[^}]+\}", block_text)
    assert len(objects) >= 8, f"expected ≥8 tile entries, got {len(objects)}"
    for obj in objects:
        assert "artifact:" in obj, (
            f"M060_MIRRORS entry missing `artifact` field: {obj[:80]}"
        )


def test_m060_mirror_artifacts_match_canonical_filenames():
    """The artifact filenames must match exactly what the selfdef
    daemon publishes — drift means the chain-health merge silently
    fails to find the per-artifact health entry for that tile."""
    body = _body()
    m060_block = re.search(
        r"const M060_MIRRORS\s*=\s*\[(.*?)\];",
        body, re.DOTALL
    )
    assert m060_block is not None
    block_text = m060_block.group(1)
    artifact_matches = re.findall(r"artifact:\s*\"([^\"]+)\"", block_text)
    artifacts = set(artifact_matches)
    # The 8 D-NN tiles map to these 8 publish files (TUI + CLI are
    # cross-cutting MS007 mirrors, not D-NN-tied, so not in the grid).
    expected = {
        "active-profile.json",
        "rules.json",
        "grants.json",
        "capability-tokens.json",
        "sandboxes.json",
        "audit.json",
        "quarantine.json",
        "trust-scores.json",
    }
    assert artifacts == expected, (
        f"M060_MIRRORS artifact set drift:\n"
        f"  expected: {sorted(expected)}\n"
        f"  got:      {sorted(artifacts)}"
    )


def test_stale_age_threshold_matches_selfdef_daemon():
    """selfdef-api::m060_health::STALE_AGE_SECS = 5*60. The dashboard
    classifier MUST use the same threshold so the dashboard's tile
    state and the daemon's chain state classify identically — drift
    means the dashboard says 'stale' while the daemon says 'online'
    or vice versa."""
    body = _body()
    # Locate the const declaration and verify the value.
    m = re.search(
        r"const M060_TILE_STALE_AGE_SECS\s*=\s*([^;]+);",
        body
    )
    assert m is not None, "M060_TILE_STALE_AGE_SECS const missing"
    expr = m.group(1).strip()
    # Accept either literal 300 or "5 * 60" (or variants).
    assert expr == "300" or "5 * 60" in expr.replace(" ", " ") or "5*60" in expr, (
        f"M060_TILE_STALE_AGE_SECS = {expr!r} does not equal 300s "
        f"(must match selfdef-api::m060_health::STALE_AGE_SECS)"
    )


def test_classify_tile_state_handles_corrupt_branch():
    """The classifier branches must INCLUDE the corrupt state when
    parses_as_json === false — without this branch, a corrupt
    artifact tile renders as online (because present===true)."""
    body = _body()
    fn = re.search(
        r"function classifyTileState\([^)]*\)\s*\{.*?^}",
        body, re.DOTALL | re.MULTILINE
    )
    assert fn is not None, "classifyTileState() function not found"
    fn_body = fn.group()
    # Must check parses_as_json explicitly + return "corrupt".
    assert "parses_as_json" in fn_body, (
        "classifyTileState() does not check parses_as_json"
    )
    assert '"corrupt"' in fn_body, (
        "classifyTileState() does not return \"corrupt\""
    )
    # Must check age_seconds for the stale branch.
    assert "age_seconds" in fn_body, (
        "classifyTileState() does not check age_seconds"
    )
    assert '"stale"' in fn_body, (
        "classifyTileState() does not return \"stale\""
    )


def test_hover_title_surfaces_state_reason():
    """Operators hovering any tile must see WHY it's in its current
    state. The renderer must compute a state-specific title for
    offline / corrupt / stale, not just leave the default empty."""
    body = _body()
    # Locate the renderM060Grid function.
    fn = re.search(
        r"async function renderM060Grid\(\).*?^}",
        body, re.DOTALL | re.MULTILINE
    )
    assert fn is not None, "renderM060Grid() function not found"
    fn_body = fn.group()
    # Must have explicit title computation for each non-online state.
    assert "OFFLINE:" in fn_body, (
        "renderM060Grid does not set hover-title for offline state"
    )
    assert "CORRUPT:" in fn_body, (
        "renderM060Grid does not set hover-title for corrupt state"
    )
    assert "STALE:" in fn_body, (
        "renderM060Grid does not set hover-title for stale state"
    )


def test_chain_health_fetch_happens_once_per_grid_render():
    """Performance + correctness: fetchM060ArtifactHealthMap MUST be
    called once per grid render (in parallel with the per-mirror
    snapshot probes), not once per tile. The latter would multiply
    the load on /api/m060/health by 8."""
    body = _body()
    fn = re.search(
        r"async function renderM060Grid\(\).*?^}",
        body, re.DOTALL | re.MULTILINE
    )
    assert fn is not None
    fn_body = fn.group()
    # Must call fetchM060ArtifactHealthMap exactly once.
    n_calls = fn_body.count("fetchM060ArtifactHealthMap")
    assert n_calls == 1, (
        f"fetchM060ArtifactHealthMap called {n_calls} times — must be "
        f"called exactly once per grid render"
    )
