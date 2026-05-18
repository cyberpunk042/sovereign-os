"""R513 (E5++) — Trinity TUI surface contract lint.

Closes the trinity tui:FUTURE waiver. Raises the trinity surface
count from 5 → 6 shipped surfaces (core / cli / api / service /
dashboard / tui). First commit in the trinity tier-3 surface-
expansion arc — same shape as the auth-tier R501, edge-firewall
R504, network-edge R507, and global-history R510 openers (this one
opens with `tui` instead of `api` because trinity already ships api
+ service via its master-spec § 17 lineage).

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

Per operator §1g 8-surface delivery contract (verbatim):

  "everything is not just core, not just cli, not just TUI, not just
  API, not just tool and MCP but also Dashboards and Web Apps and
  Services"

The TUI surface is a refresh-loop `sovereign-osctl trinity watch`
subcommand that combines the Pulse / Weaver / Auditor brief panels
into one continuously-updating view — same shape as R488 master-
dashboard.watch and R483 network-edge opnsense.watch.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
SURFACE_MAP = REPO_ROOT / "scripts" / "operator" / "surface-map.py"


def _run_osctl(args: list[str], env_extra: dict[str, str] | None = None,
               timeout: int = 10) -> subprocess.CompletedProcess:
    env = {"PATH": "/usr/bin:/bin", "HOME": "/tmp"}
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        ["bash", str(OSCTL), *args],
        capture_output=True, text=True, timeout=timeout, env=env,
    )


def test_osctl_script_present():
    assert OSCTL.is_file()


def test_trinity_watch_subcommand_help():
    """`sovereign-osctl trinity watch --help` MUST advertise refresh
    + iterations flags and return exit 0."""
    cp = _run_osctl(["trinity", "watch", "--help"])
    assert cp.returncode == 0, (
        f"trinity watch --help failed: {cp.stderr[:300]}"
    )
    assert "--refresh" in cp.stdout
    assert "--iterations" in cp.stdout


def test_trinity_watch_dry_run_single_render():
    """SOVEREIGN_OS_DRY_RUN=1 MUST cap the watch loop to a single
    render and exit 0 (CI-safe — operator-named guarantee)."""
    cp = _run_osctl(
        ["trinity", "watch", "--refresh", "1"],
        env_extra={"SOVEREIGN_OS_DRY_RUN": "1"},
        timeout=15,
    )
    assert cp.returncode == 0, (
        f"trinity watch DRY_RUN exit nonzero: {cp.returncode}\n"
        f"stderr: {cp.stderr[:300]}"
    )
    assert "trinity.watch" in cp.stdout
    assert "frame 1" in cp.stdout
    assert "Pulse" in cp.stdout
    assert "Weaver" in cp.stdout
    assert "Auditor" in cp.stdout


def test_trinity_watch_iterations_flag():
    """`--iterations N` MUST bound the loop. With SOVEREIGN_OS_DRY_RUN
    unset but --iterations=2 and --refresh=1, the command MUST render
    2 frames and exit."""
    cp = _run_osctl(
        ["trinity", "watch", "--refresh", "1", "--iterations", "2"],
        timeout=15,
    )
    assert cp.returncode == 0, cp.stderr[:300]
    assert "frame 1" in cp.stdout
    assert "frame 2" in cp.stdout
    assert "frame 3" not in cp.stdout
    assert "reached --iterations=2" in cp.stdout


def test_trinity_watch_refresh_floor():
    """`--refresh 0` MUST be coerced to the 1s floor (operator-named
    guarantee — no /proc + systemctl hammering)."""
    cp = _run_osctl(
        ["trinity", "watch", "--refresh", "0"],
        env_extra={"SOVEREIGN_OS_DRY_RUN": "1"},
        timeout=15,
    )
    assert cp.returncode == 0
    assert "refresh=1s" in cp.stdout


def test_trinity_watch_rejects_unknown_flag():
    cp = _run_osctl(["trinity", "watch", "--no-such-flag"], timeout=5)
    assert cp.returncode != 0
    assert "unknown" in cp.stderr.lower() or "unknown" in cp.stdout.lower()


def test_trinity_status_lists_watch_in_dispatcher_help():
    """The dispatcher's unknown-subcommand error message MUST list
    `watch` in the available verbs — operator-§1g visibility rule."""
    cp = _run_osctl(["trinity", "no-such-verb"], timeout=5)
    assert cp.returncode != 0
    combined = cp.stdout + cp.stderr
    assert "watch" in combined, (
        f"dispatcher help must list 'watch' verb; got: {combined[:300]}"
    )


def test_trinity_surface_map_extended_to_tui():
    """R513 extends trinity surface-map to 6 shipped surfaces — tui
    MUST appear as shipped, NOT as a FUTURE waiver."""
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module",
         "trinity", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr[:300]
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    assert entry.get("surface_count", 0) >= 6, (
        f"trinity must be at >=6 surfaces post-R513; got {entry}"
    )
    matrix = entry.get("matrix", [])
    tui_row = next(
        (r for r in matrix if r.get("surface") == "tui"), None
    )
    assert tui_row is not None, "trinity matrix missing tui row"
    assert tui_row.get("state") == "shipped", (
        f"trinity tui surface must be shipped; got {tui_row}"
    )
    # The tui-shipped invariant is the load-bearing assertion here.
    # Historically R513 left mcp/webapp as FUTURE; R514 (mcp) and R515
    # (webapp) subsequently drained those — so the precise
    # FUTURE-waiver remainder is no longer a stable assertion here. It
    # is asserted directly in the R514/R515 contract tests at their
    # close-out round.
