"""R543 (E5++) — `surface-map watch` TUI milestone banner contract lint.

The surface-map watch refresh loop (R531) is the operator's terminal-
first surface for the §1g coverage matrix. R543 wires the R540
milestone rollup as a TOP banner above the per-module matrix so a
human watching the refresh loop sees the system-wide ceiling-closure
state at a glance — same R539 invariants the R541 /milestone REST
endpoint and the R542 webapp panel surface.

Per operator §1g 8-surface delivery contract anchor verbatim (R453):

  "everything is not just core, not just cli, not just TUI, not just
   API, not just tool and MCP but also Dashboards and Web Apps and
   Services"

Operator-§1g UX layout invariant: the milestone banner is HIGH-
SIGNAL system-wide information — it MUST render BEFORE the per-
module coverage matrix on every refresh frame (same rule the R542
webapp panel encodes).
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"


def _run_watch_one_frame() -> tuple[int, str, str]:
    env = os.environ.copy()
    env["SOVEREIGN_OS_DRY_RUN"] = "1"
    env["PATH"] = "/usr/bin:/bin"
    env["HOME"] = "/tmp"
    cp = subprocess.run(
        ["bash", str(OSCTL), "surface-map", "watch", "--iterations", "1"],
        capture_output=True, text=True, timeout=20, env=env,
    )
    return cp.returncode, cp.stdout, cp.stderr


def test_watch_emits_milestone_banner():
    rc, out, err = _run_watch_one_frame()
    assert rc == 0, f"watch exited {rc}: {err[:300]}"
    assert "surface-map.milestone" in out, (
        "R543: watch frame must render the milestone rollup banner"
    )
    assert "§1g 8-surface delivery contract rollup" in out, (
        "milestone banner must cite the §1g delivery contract verbatim"
    )


def test_milestone_banner_carries_r539_invariants():
    rc, out, _err = _run_watch_one_frame()
    assert rc == 0
    # The rollup human format renders the R539 invariants — assert
    # the operator-facing booleans surface as True.
    assert "ALL at structural ceiling?" in out
    assert "ZERO FUTURE waivers?" in out
    # Each invariant question MUST resolve to True post-R539.
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("ALL at structural ceiling?"):
            assert line.endswith("True"), f"got: {line!r}"
        if line.startswith("ALL §1g-named at full 8/8?"):
            assert line.endswith("True"), f"got: {line!r}"
        if line.startswith("ZERO FUTURE waivers?"):
            assert line.endswith("True"), f"got: {line!r}"


def test_milestone_banner_renders_before_coverage_matrix():
    """Operator-§1g UX layout invariant: high-signal milestone state
    MUST render before the per-module coverage matrix on each frame."""
    rc, out, _err = _run_watch_one_frame()
    assert rc == 0
    i_milestone = out.find("surface-map.milestone")
    # The coverage matrix header line is operator-named — search for
    # the X/8 column header rendered by `surface-map coverage`.
    # Fall back to looking for a known §1g-named module entry.
    i_coverage_header = out.find("X/8", i_milestone)
    if i_coverage_header < 0:
        i_coverage_header = out.find("surface-map", i_milestone + 1)
    assert i_milestone >= 0, "milestone banner missing"
    assert i_coverage_header > i_milestone, (
        "R543 layout: milestone banner must render BEFORE the coverage "
        "matrix"
    )


def test_milestone_banner_lists_twelve_full_eight_modules():
    """Post-R539 the rollup must list 12 §1g-named modules at full
    8/8 surfaces — assert the banner surfaces that ceiling-closure
    state for the operator."""
    rc, out, _err = _run_watch_one_frame()
    assert rc == 0
    assert "Modules at full 8/8 surfaces (12):" in out, (
        "R543 banner must report 12 §1g-named modules at full 8/8 "
        "surfaces post-R539"
    )


def test_watch_frame_header_still_present():
    """R543 must NOT regress the R531 watch frame header — operator-
    facing refresh-loop UX rule."""
    rc, out, _err = _run_watch_one_frame()
    assert rc == 0
    assert "surface-map.watch (frame 1" in out, (
        "R531 watch frame header must still render post-R543"
    )


def test_watch_iterations_cap_still_honored():
    """R543 must NOT regress the --iterations cap — operator-named
    R531 guarantee: SOVEREIGN_OS_DRY_RUN=1 forces single-frame exit."""
    rc, out, _err = _run_watch_one_frame()
    assert rc == 0
    assert "reached --iterations=1; exit" in out, (
        "R531 --iterations cap must still trigger single-frame exit"
    )
    # Exactly one frame banner.
    assert out.count("surface-map.watch (frame ") == 1, (
        "R543 must not multiply the frame banner"
    )
    assert out.count("surface-map.milestone") == 1, (
        "R543 milestone banner must render exactly once per frame"
    )


def test_osctl_help_unchanged_for_surface_map_watch():
    """The R531 help block for `surface-map watch` MUST still parse —
    operator-facing UX rule. R543 added a banner inside the loop, not
    a new flag, so the help text is unchanged."""
    rc = subprocess.run(
        ["bash", str(OSCTL), "surface-map", "watch", "--help"],
        capture_output=True, text=True, timeout=10,
        env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"},
    )
    assert rc.returncode == 0, rc.stderr[:300]
    assert "surface-map watch" in rc.stdout
    assert "--refresh" in rc.stdout
    assert "--iterations" in rc.stdout
