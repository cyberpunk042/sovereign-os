"""R516 (E5++) — Inference Router TUI surface contract lint.

Closes the router tui:FUTURE waiver. Raises the router surface count
from 5 → 6 shipped surfaces (core / cli / tui / api / service /
dashboard). First commit in the router tier-3 surface-expansion arc;
R517 (mcp) and R518 (webapp) will close the router ladder to the
full §1g 8-surface ceiling — same shape as the trinity R513/R514/R515
triple just completed.

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

Per operator §1g 8-surface delivery contract (verbatim):

  "everything is not just core, not just cli, not just TUI, not just
  API, not just tool and MCP but also Dashboards and Web Apps and
  Services"

The TUI surface is a refresh-loop `sovereign-osctl router watch`
subcommand that combines the router status + 4-tier backend states
+ SDD-011 routing rules into one continuously-updating view — same
shape as R513 trinity.watch, R488 master-dashboard.watch, and R483
network-edge opnsense.watch.
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


def test_router_dispatcher_present():
    """`sovereign-osctl router --help` MUST advertise the new subverb
    tree and return exit 0."""
    cp = _run_osctl(["router", "--help"])
    assert cp.returncode == 0, (
        f"router --help failed: {cp.stderr[:300]}"
    )
    for verb in ("status", "classify", "rules", "watch"):
        assert verb in cp.stdout, (
            f"router --help must list {verb!r}; got: {cp.stdout[:300]}"
        )


def test_router_rules_emits_sdd_011_ladder():
    """`router rules` MUST print all 5 SDD-011 routing rules — operator
    §1g visibility rule (full ladder visible)."""
    cp = _run_osctl(["router", "rules"])
    assert cp.returncode == 0, cp.stderr[:300]
    out = cp.stdout
    for marker in ("Pulse", "Oracle Core", "Logic Engine",
                   "bitnet", "JSON"):
        assert marker in out, (
            f"router rules must mention {marker!r}; got: {out[:300]}"
        )
    # 5 numbered rules.
    for n in ("1.", "2.", "3.", "4.", "5."):
        assert n in out, (
            f"router rules must enumerate rule {n}; got: {out[:300]}"
        )


def test_router_status_describes_service_and_port():
    cp = _run_osctl(["router", "status"])
    assert cp.returncode == 0, cp.stderr[:300]
    out = cp.stdout
    assert "sovereign-router.service" in out
    assert "8080" in out


def test_router_watch_subcommand_help():
    """`sovereign-osctl router watch --help` MUST advertise refresh
    + iterations flags and return exit 0."""
    cp = _run_osctl(["router", "watch", "--help"])
    assert cp.returncode == 0, (
        f"router watch --help failed: {cp.stderr[:300]}"
    )
    assert "--refresh" in cp.stdout
    assert "--iterations" in cp.stdout


def test_router_watch_dry_run_single_render():
    """SOVEREIGN_OS_DRY_RUN=1 MUST cap the watch loop to a single
    render and exit 0 (CI-safe — operator-named guarantee)."""
    cp = _run_osctl(
        ["router", "watch", "--refresh", "1"],
        env_extra={"SOVEREIGN_OS_DRY_RUN": "1"},
        timeout=15,
    )
    assert cp.returncode == 0, (
        f"router watch DRY_RUN exit nonzero: {cp.returncode}\n"
        f"stderr: {cp.stderr[:300]}"
    )
    assert "router.watch" in cp.stdout
    assert "frame 1" in cp.stdout
    assert "Router" in cp.stdout
    assert "Pulse" in cp.stdout
    assert "Logic" in cp.stdout
    assert "Oracle" in cp.stdout


def test_router_watch_iterations_flag():
    """`--iterations N` MUST bound the loop. With SOVEREIGN_OS_DRY_RUN
    unset but --iterations=2 and --refresh=1, the command MUST render
    2 frames and exit."""
    cp = _run_osctl(
        ["router", "watch", "--refresh", "1", "--iterations", "2"],
        timeout=15,
    )
    assert cp.returncode == 0, cp.stderr[:300]
    assert "frame 1" in cp.stdout
    assert "frame 2" in cp.stdout
    assert "frame 3" not in cp.stdout
    assert "reached --iterations=2" in cp.stdout


def test_router_watch_refresh_floor():
    """`--refresh 0` MUST be coerced to the 1s floor (operator-named
    guarantee — no /proc + systemctl hammering)."""
    cp = _run_osctl(
        ["router", "watch", "--refresh", "0"],
        env_extra={"SOVEREIGN_OS_DRY_RUN": "1"},
        timeout=15,
    )
    assert cp.returncode == 0
    assert "refresh=1s" in cp.stdout


def test_router_watch_rejects_unknown_flag():
    cp = _run_osctl(["router", "watch", "--no-such-flag"], timeout=5)
    assert cp.returncode != 0
    assert "unknown" in cp.stderr.lower() or "unknown" in cp.stdout.lower()


def test_router_rejects_unknown_subcommand():
    """The router dispatcher's unknown-subcommand error message MUST
    list `watch` in the available verbs — operator-§1g visibility
    rule."""
    cp = _run_osctl(["router", "no-such-verb"], timeout=5)
    assert cp.returncode != 0
    combined = cp.stdout + cp.stderr
    assert "watch" in combined, (
        f"router dispatcher help must list 'watch' verb; got: "
        f"{combined[:300]}"
    )


def test_top_level_help_lists_router_watch():
    """The top-level `sovereign-osctl --help` MUST surface the router
    subverb tree post-R516 — operator-§1g 30-second visibility rule."""
    cp = _run_osctl(["--help"], timeout=5)
    # --help may exit 0 or 2 depending on dispatcher; both acceptable.
    combined = cp.stdout + cp.stderr
    assert "router watch" in combined or "router status" in combined, (
        f"top-level help must list router subverbs; got: "
        f"{combined[:500]}"
    )


def test_router_surface_map_extended_to_tui():
    """R516 extends router surface-map to 6 shipped surfaces — tui
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
    assert entry.get("surface_count", 0) >= 6, (
        f"router must be at >=6 surfaces post-R516; got {entry}"
    )
    matrix = entry.get("matrix", [])
    tui_row = next(
        (r for r in matrix if r.get("surface") == "tui"), None
    )
    assert tui_row is not None, "router matrix missing tui row"
    assert tui_row.get("state") == "shipped", (
        f"router tui surface must be shipped; got {tui_row}"
    )
    # mcp + webapp remain FUTURE post-R516 (R517 will close mcp;
    # R518 will close webapp).
    assert entry.get("future_waiver_count", 0) >= 1, (
        f"router must still have FUTURE waivers post-R516; "
        f"got {entry}"
    )
