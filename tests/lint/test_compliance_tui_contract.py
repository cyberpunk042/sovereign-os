"""R519 (E5++) — Compliance dashboard TUI surface contract lint.

Closes the compliance tui:FUTURE waiver. Raises the compliance surface
count from 3 → 4 shipped surfaces (core / cli / dashboard / tui).
First commit in the compliance tier-3 surface-expansion arc; R520
(mcp) and R521 (api + webapp) will close the compliance ladder to the
full §1g ceiling — same shape as the trinity R513/R514/R515 triple
and the router R516/R517/R518 triple just completed.

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

Per operator §1g 8-surface delivery contract (verbatim):

  "everything is not just core, not just cli, not just TUI, not just
  API, not just tool and MCP but also Dashboards and Web Apps and
  Services"

The TUI surface is a refresh-loop `sovereign-osctl compliance watch`
subcommand that re-renders the §1g/§1h compliance dashboard rollup
(R453 surface-map + R454 doc-coverage + R456 anti-min-audit + R457
ux-design-audit) continuously — same shape as R516 router.watch,
R513 trinity.watch, and R488 master-dashboard.watch.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
SURFACE_MAP = REPO_ROOT / "scripts" / "operator" / "surface-map.py"


def _run_osctl(args: list[str], env_extra: dict[str, str] | None = None,
               timeout: int = 30) -> subprocess.CompletedProcess:
    env = {"PATH": "/usr/bin:/bin", "HOME": "/tmp"}
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        ["bash", str(OSCTL), *args],
        capture_output=True, text=True, timeout=timeout, env=env,
    )


def test_osctl_script_present():
    assert OSCTL.is_file()


def test_compliance_watch_subcommand_help():
    """`sovereign-osctl compliance watch --help` MUST advertise refresh
    + iterations flags and return exit 0."""
    cp = _run_osctl(["compliance", "watch", "--help"])
    assert cp.returncode == 0, (
        f"compliance watch --help failed: {cp.stderr[:300]}"
    )
    assert "--refresh" in cp.stdout
    assert "--iterations" in cp.stdout
    assert "compliance" in cp.stdout.lower()


def test_compliance_watch_dry_run_single_render():
    """SOVEREIGN_OS_DRY_RUN=1 MUST cap the watch loop to a single
    render and exit 0 (CI-safe — operator-named guarantee mirroring
    R516 router.watch / R513 trinity.watch)."""
    cp = _run_osctl(
        ["compliance", "watch", "--refresh", "1"],
        env_extra={"SOVEREIGN_OS_DRY_RUN": "1"},
        timeout=60,
    )
    assert cp.returncode == 0, (
        f"compliance watch DRY_RUN exit nonzero: {cp.returncode}\n"
        f"stderr: {cp.stderr[:300]}"
    )
    assert "compliance.watch" in cp.stdout
    assert "frame 1" in cp.stdout


def test_compliance_watch_iterations_flag():
    """`--iterations N` MUST bound the loop. With SOVEREIGN_OS_DRY_RUN
    unset but --iterations=2 and --refresh=1, the command MUST render
    2 frames and exit."""
    cp = _run_osctl(
        ["compliance", "watch", "--refresh", "1", "--iterations", "2"],
        timeout=60,
    )
    assert cp.returncode == 0, cp.stderr[:300]
    assert "frame 1" in cp.stdout
    assert "frame 2" in cp.stdout
    assert "frame 3" not in cp.stdout
    assert "reached --iterations=2" in cp.stdout


def test_compliance_watch_refresh_floor():
    """`--refresh 0` MUST be coerced to the 1s floor (operator-named
    guarantee — no /proc + systemctl hammering)."""
    cp = _run_osctl(
        ["compliance", "watch", "--refresh", "0"],
        env_extra={"SOVEREIGN_OS_DRY_RUN": "1"},
        timeout=60,
    )
    assert cp.returncode == 0
    assert "refresh=1s" in cp.stdout


def test_compliance_watch_rejects_unknown_flag():
    cp = _run_osctl(["compliance", "watch", "--no-such-flag"], timeout=5)
    assert cp.returncode != 0
    assert "unknown" in cp.stderr.lower() or \
           "unknown" in cp.stdout.lower()


def test_compliance_watch_renders_instrument_sections():
    """The watch frame MUST surface the 4 §1g compliance instruments
    that `compliance status` enumerates (R453 surface-map, R454
    doc-coverage, R456 anti-min, R457 ux-design-audit) — operator-§1g
    visibility rule: full ladder visible per frame."""
    cp = _run_osctl(
        ["compliance", "watch", "--refresh", "1"],
        env_extra={"SOVEREIGN_OS_DRY_RUN": "1"},
        timeout=60,
    )
    assert cp.returncode == 0
    # The compliance status output names each instrument. Watch must
    # surface them via the embedded `compliance status` call.
    out = cp.stdout.lower()
    assert "surface" in out, (
        f"watch frame must surface 'surface' instrument label; got "
        f"head: {cp.stdout[:400]}"
    )
    assert "doc" in out
    assert "minim" in out or "anti-minimization" in out
    assert "ux" in out


def test_compliance_non_watch_verbs_still_delegate_to_python():
    """R519 wraps the bash compliance dispatch around `watch`; the
    other 5 verbs (status / module / worst / history / snapshot) MUST
    still delegate to compliance.py — no regression of the R458
    surface."""
    cp = _run_osctl(["compliance", "status", "--json"], timeout=60)
    assert cp.returncode == 0, (
        f"compliance status --json broken post-R519: {cp.stderr[:300]}"
    )
    # JSON parseable + has the canonical instruments keys.
    data = json.loads(cp.stdout)
    assert "surface_map" in data
    assert "doc_coverage" in data


def test_top_level_help_lists_compliance_watch():
    """The top-level `sovereign-osctl --help` MUST surface the
    compliance watch subverb post-R519 — operator-§1g 30-second
    visibility rule."""
    cp = _run_osctl(["--help"], timeout=5)
    combined = cp.stdout + cp.stderr
    assert "compliance watch" in combined, (
        f"top-level help must list 'compliance watch'; got: "
        f"{combined[:500]}"
    )


def test_compliance_surface_map_extended_to_tui():
    """R519 extends compliance surface-map to 4 shipped surfaces — tui
    MUST appear as shipped, NOT as a FUTURE waiver."""
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module",
         "compliance", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr[:300]
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    assert entry.get("surface_count", 0) >= 4, (
        f"compliance must be at >=4 surfaces post-R519; got {entry}"
    )
    matrix = entry.get("matrix", [])
    tui_row = next(
        (r for r in matrix if r.get("surface") == "tui"), None
    )
    assert tui_row is not None, "compliance matrix missing tui row"
    assert tui_row.get("state") == "shipped", (
        f"compliance tui surface must be shipped; got {tui_row}"
    )
    # R519 drains the tui waiver. The precise count of remaining
    # FUTURE waivers rotates as the compliance tier-3 arc progresses
    # (R520 will drain mcp; R521 will drain api + webapp). The
    # tui-shipped invariant above is the load-bearing R519 contract.
