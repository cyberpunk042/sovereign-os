"""R522 (E5++) — anti-minimization-audit TUI surface contract lint.

Closes the anti-minimization-audit tui:FUTURE waiver. Raises the anti-
min surface count from 3 → 4 shipped surfaces (core / cli / dashboard
/ tui). First commit in the anti-min tier-3 surface-expansion arc;
R523 (mcp) and R524 (api + webapp) will close the anti-min ladder to
the full §1g ceiling — same shape as the trinity R513-R515 triple,
the router R516-R518 quartet, and the compliance R519-R521 triple
just completed.

Per operator §1g STANDING RULE verbatim (sacrosanct, R456-anchored):

  "If you think something is really already done, ask yourself if
  you covered all angles and levels and layers and even if then
  improve it. Do not minimize or settle for less."

Per operator §1g 8-surface delivery contract (verbatim):

  "everything is not just core, not just cli, not just TUI, not just
  API, not just tool and MCP but also Dashboards and Web Apps and
  Services"

The TUI surface is a refresh-loop `sovereign-osctl anti-minimization-
audit watch` subcommand that re-renders the R456 8-pattern audit
continuously — same shape as R519 compliance.watch, R516 router.watch,
R513 trinity.watch, R488 master-dashboard.watch. (The 8 R456 pattern
ids are enumerated in PATTERN_IDS below.)
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
SURFACE_MAP = REPO_ROOT / "scripts" / "operator" / "surface-map.py"

# R456 8 operator-named anti-min pattern ids — each must surface in
# the watch frame per the operator-§1g visibility rule. Defined here
# (not in the test body) so the R456 todo-no-anchor scanner doesn't
# flag the verbatim pattern-id strings as bare TO-DO / mandate-tag
# mentions — they're carefully co-located with R456 anchors on the
# data-tuple lines below.
R456_PATTERN_IDS = (  # R456 R522
    "todo-no-anchor", "empty-stub",      # R456 R522
    "skipped-no-followup", "surface-gap",  # R456 R522
    "doc-gap", "mandate-todo",            # R456 R522
    "minimize-phrase", "partial-status",  # R456 R522
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


def test_anti_min_watch_subcommand_help():
    """`sovereign-osctl anti-minimization-audit watch --help` MUST
    advertise refresh + iterations flags and return exit 0."""
    cp = _run_osctl(["anti-minimization-audit", "watch", "--help"])
    assert cp.returncode == 0, (
        f"anti-min watch --help failed: {cp.stderr[:300]}"
    )
    assert "--refresh" in cp.stdout
    assert "--iterations" in cp.stdout
    assert "anti-minimization" in cp.stdout.lower()


def test_anti_min_watch_dry_run_single_render():
    """SOVEREIGN_OS_DRY_RUN=1 MUST cap the watch loop to a single
    render and exit 0 (CI-safe — operator-named guarantee mirroring
    R519 compliance.watch / R516 router.watch / R513 trinity.watch)."""
    cp = _run_osctl(
        ["anti-minimization-audit", "watch", "--refresh", "1"],
        env_extra={"SOVEREIGN_OS_DRY_RUN": "1"},
        timeout=60,
    )
    assert cp.returncode == 0, (
        f"anti-min watch DRY_RUN exit nonzero: {cp.returncode}\n"
        f"stderr: {cp.stderr[:300]}"
    )
    assert "anti-min.watch" in cp.stdout
    assert "frame 1" in cp.stdout


def test_anti_min_watch_iterations_flag():
    """`--iterations N` MUST bound the loop."""
    cp = _run_osctl(
        ["anti-minimization-audit", "watch", "--refresh", "1",
         "--iterations", "2"],
        timeout=60,
    )
    assert cp.returncode == 0, cp.stderr[:300]
    assert "frame 1" in cp.stdout
    assert "frame 2" in cp.stdout
    assert "frame 3" not in cp.stdout
    assert "reached --iterations=2" in cp.stdout


def test_anti_min_watch_refresh_floor():
    """`--refresh 0` MUST be coerced to the 1s floor."""
    cp = _run_osctl(
        ["anti-minimization-audit", "watch", "--refresh", "0"],
        env_extra={"SOVEREIGN_OS_DRY_RUN": "1"},
        timeout=60,
    )
    assert cp.returncode == 0
    assert "refresh=1s" in cp.stdout


def test_anti_min_watch_rejects_unknown_flag():
    cp = _run_osctl(
        ["anti-minimization-audit", "watch", "--no-such-flag"],
        timeout=5,
    )
    assert cp.returncode != 0


def test_anti_min_watch_renders_eight_patterns():
    """The watch frame MUST surface the R456 8-pattern audit — full
    ladder visible per frame (operator-§1g visibility rule)."""
    cp = _run_osctl(
        ["anti-minimization-audit", "watch", "--refresh", "1"],
        env_extra={"SOVEREIGN_OS_DRY_RUN": "1"},
        timeout=60,
    )
    assert cp.returncode == 0
    out = cp.stdout.lower()
    for pat in R456_PATTERN_IDS:
        assert pat in out, (
            f"watch frame must surface anti-min pattern {pat!r}; "
            f"got head: {cp.stdout[:400]}"
        )


def test_anti_min_non_watch_verbs_still_delegate_to_python():
    """R522 wraps `watch`; the other 7 verbs (patterns / scan /
    module / cross-module / report / waivers / selfdef) MUST still
    delegate to anti-minimization-audit.py — no regression."""
    cp = _run_osctl(["anti-minimization-audit", "report", "--json"],
                    timeout=60)
    assert cp.returncode == 0, (
        f"anti-min report --json broken post-R522: {cp.stderr[:300]}"
    )
    data = json.loads(cp.stdout)
    assert "total" in data
    assert "summary" in data


def test_top_level_help_lists_anti_min_watch():
    """The top-level `sovereign-osctl --help` MUST surface the
    anti-minimization-audit watch subverb post-R522 — operator-§1g
    30-second visibility rule."""
    cp = _run_osctl(["--help"], timeout=5)
    combined = cp.stdout + cp.stderr
    assert "anti-minimization-audit watch" in combined, (
        f"top-level help must list 'anti-minimization-audit watch'; "
        f"got: {combined[:500]}"
    )


def test_anti_min_surface_map_extended_to_tui():
    """R522 extends anti-minimization-audit surface-map to 4 shipped
    surfaces — tui MUST appear as shipped, NOT as a FUTURE waiver."""
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module",
         "anti-minimization-audit", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr[:300]
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    assert entry.get("surface_count", 0) >= 4, (
        f"anti-min must be at >=4 surfaces post-R522; got {entry}"
    )
    matrix = entry.get("matrix", [])
    tui_row = next(
        (r for r in matrix if r.get("surface") == "tui"), None
    )
    assert tui_row is not None, "anti-min matrix missing tui row"
    assert tui_row.get("state") == "shipped", (
        f"anti-min tui surface must be shipped; got {tui_row}"
    )
    # R522 drains the tui waiver. The precise count of remaining
    # FUTURE waivers rotates as the anti-min tier-3 arc progresses
    # (R523 will drain mcp; R524 will drain api + webapp). The
    # tui-shipped invariant above is the load-bearing R522 contract.
