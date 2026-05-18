"""R525 (E5++) — doc-coverage TUI surface contract lint.

Closes the doc-coverage tui:FUTURE waiver. Raises the doc-coverage
surface count from 3 -> 4 shipped surfaces (core / cli / dashboard /
tui). First commit in the doc-coverage tier-3 surface-expansion arc;
R526 (mcp) and R527 (api + webapp + service) will close the doc-
coverage ladder to the full §1g ceiling — same shape as the trinity
R513-R515 triple, the router R516-R518 quartet, the compliance
R519-R521 triple, and the anti-min R522-R524 triple just completed.

Per operator §1g STANDING RULE verbatim (sacrosanct, R456-anchored):

  "If you think something is really already done, ask yourself if
  you covered all angles and levels and layers and even if then
  improve it. Do not minimize or settle for less."

Per operator §1g 8-surface delivery contract (verbatim):

  "everything is not just core, not just cli, not just TUI, not just
  API, not just tool and MCP but also Dashboards and Web Apps and
  Services"

The TUI surface is a refresh-loop `sovereign-osctl doc-coverage watch`
subcommand that re-renders the R454 6-doc-surface module matrix
continuously — same shape as R522 anti-min.watch, R519 compliance.
watch, R516 router.watch, R513 trinity.watch, R488 master-dashboard.
watch.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
SURFACE_MAP = REPO_ROOT / "scripts" / "operator" / "surface-map.py"

# R454 6 doc-surface ids — each must surface in the watch frame per
# the operator-§1g visibility rule (the watch frame embeds the full
# `doc-coverage coverage` matrix, which renders every doc surface per
# module).
R454_DOC_SURFACES = (  # R454 R525
    "readme", "sdd",                 # R454 R525
    "helptext", "metric-inventory",  # R454 R525
    "mandate-row", "man-page",       # R454 R525
)


def _run_osctl(args: list[str], env_extra: dict[str, str] | None = None,
               timeout: int = 60) -> subprocess.CompletedProcess:
    env = {"PATH": "/usr/bin:/bin", "HOME": "/tmp"}
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        ["bash", str(OSCTL), *args],
        capture_output=True, text=True, timeout=timeout, env=env,
    )


def test_osctl_script_present():
    assert OSCTL.is_file()


def test_doc_coverage_watch_subcommand_help():
    """`sovereign-osctl doc-coverage watch --help` MUST advertise
    refresh + iterations flags and return exit 0."""
    cp = _run_osctl(["doc-coverage", "watch", "--help"])
    assert cp.returncode == 0, (
        f"doc-coverage watch --help failed: {cp.stderr[:300]}"
    )
    assert "--refresh" in cp.stdout
    assert "--iterations" in cp.stdout
    assert "doc-coverage" in cp.stdout.lower()


def test_doc_coverage_watch_dry_run_single_render():
    """SOVEREIGN_OS_DRY_RUN=1 MUST cap the watch loop to a single
    render and exit 0 (CI-safe — operator-named guarantee mirroring
    R522 anti-min.watch / R519 compliance.watch)."""
    cp = _run_osctl(
        ["doc-coverage", "watch", "--refresh", "1"],
        env_extra={"SOVEREIGN_OS_DRY_RUN": "1"},
        timeout=60,
    )
    assert cp.returncode == 0, (
        f"doc-coverage watch DRY_RUN exit nonzero: {cp.returncode}\n"
        f"stderr: {cp.stderr[:300]}"
    )
    assert "doc-coverage.watch" in cp.stdout
    assert "frame 1" in cp.stdout


def test_doc_coverage_watch_iterations_flag():
    """`--iterations N` MUST bound the loop."""
    cp = _run_osctl(
        ["doc-coverage", "watch", "--refresh", "1",
         "--iterations", "2"],
        timeout=60,
    )
    assert cp.returncode == 0, cp.stderr[:300]
    assert "frame 1" in cp.stdout
    assert "frame 2" in cp.stdout
    assert "frame 3" not in cp.stdout
    assert "reached --iterations=2" in cp.stdout


def test_doc_coverage_watch_refresh_floor():
    """`--refresh 0` MUST be coerced to the 1s floor."""
    cp = _run_osctl(
        ["doc-coverage", "watch", "--refresh", "0"],
        env_extra={"SOVEREIGN_OS_DRY_RUN": "1"},
        timeout=60,
    )
    assert cp.returncode == 0
    assert "refresh=1s" in cp.stdout


def test_doc_coverage_watch_rejects_unknown_flag():
    cp = _run_osctl(
        ["doc-coverage", "watch", "--no-such-flag"],
        timeout=5,
    )
    assert cp.returncode != 0


def test_doc_coverage_watch_renders_six_doc_surfaces():
    """The watch frame MUST surface the R454 6-doc-surface matrix —
    full ladder visible per frame (operator-§1g visibility rule)."""
    cp = _run_osctl(
        ["doc-coverage", "watch", "--refresh", "1"],
        env_extra={"SOVEREIGN_OS_DRY_RUN": "1"},
        timeout=60,
    )
    assert cp.returncode == 0
    out = cp.stdout.lower()
    for kind in R454_DOC_SURFACES:
        assert kind in out, (
            f"watch frame must surface doc-coverage kind {kind!r}; "
            f"got head: {cp.stdout[:400]}"
        )


def test_doc_coverage_non_watch_verbs_still_delegate_to_python():
    """R525 wraps `watch`; the other 4 verbs (kinds / modules / scan /
    coverage / gaps) MUST still delegate to doc-coverage.py — no
    regression."""
    cp = _run_osctl(["doc-coverage", "kinds", "--json"], timeout=60)
    assert cp.returncode == 0, (
        f"doc-coverage kinds --json broken post-R525: {cp.stderr[:300]}"
    )
    data = json.loads(cp.stdout)
    assert "kinds" in data
    assert len(data["kinds"]) == 6


def test_top_level_help_lists_doc_coverage_watch():
    """The top-level `sovereign-osctl --help` MUST surface the
    doc-coverage watch subverb post-R525 — operator-§1g 30-second
    visibility rule."""
    cp = _run_osctl(["--help"], timeout=5)
    combined = cp.stdout + cp.stderr
    assert "doc-coverage watch" in combined, (
        f"top-level help must list 'doc-coverage watch'; "
        f"got: {combined[:500]}"
    )


def test_doc_coverage_surface_map_extended_to_tui():
    """R525 extends doc-coverage surface-map to 4 shipped surfaces —
    tui MUST appear as shipped, NOT as a FUTURE waiver."""
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module",
         "doc-coverage", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr[:300]
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    assert entry.get("surface_count", 0) >= 4, (
        f"doc-coverage must be at >=4 surfaces post-R525; got {entry}"
    )
    matrix = entry.get("matrix", [])
    tui_row = next(
        (r for r in matrix if r.get("surface") == "tui"), None
    )
    assert tui_row is not None, "doc-coverage matrix missing tui row"
    assert tui_row.get("state") == "shipped", (
        f"doc-coverage tui surface must be shipped; got {tui_row}"
    )
    # R525 drains the tui waiver. R526 will drain mcp; R527 will
    # drain api + webapp + service (replacing the not-applicable
    # service waiver with a real read-only daemon). The tui-shipped
    # invariant above is the load-bearing R525 contract.
