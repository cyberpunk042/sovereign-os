"""R534 (E5++) — weaver TUI surface contract lint.

Closes the weaver tui:FUTURE waiver. Raises the weaver surface count
from 3 -> 4 shipped surfaces (core / cli / dashboard / tui). First
commit in the weaver tier-3 surface-expansion arc; R535 (mcp) and
R536 (api + webapp + service) will close the weaver ladder toward
the §1g ceiling — the SAME ceiling-promotion pattern established by
R510/R515/R518/R521/R524/R527/R530/R533 (the nine ceiling arcs that
preceded), where the `service: not applicable` waiver may be
replaced by a real read-only daemon (a read-only `weaver-api` is
sensible even though atomic-state mutation stays CLI-only —
operator §17 sovereignty boundary: state-fabric WRITES are
sovereignty-critical and stay manual + CLI-gated).

Per operator §1g STANDING RULE verbatim (sacrosanct, R456-anchored):

  "If you think something is really already done, ask yourself if
  you covered all angles and levels and layers and even if then
  improve it. Do not minimize or settle for less."

Per operator §1g verbatim (R453 anchor):

  "everything is not just core, not just cli, not just TUI, not just
  API, not just tool and MCP but also Dashboards and Web Apps and
  Services"

The TUI surface is a refresh-loop `sovereign-osctl weaver watch`
subcommand that re-renders the master spec § 17 Module 2 Weaver
brief panel (podman / vfio / tank/context) PLUS the master spec § 21
atomic-state list (4-state-fabric: IDENTITY / SOUL / AGENTS /
CLAUDE). Same shape as R531 surface-map.watch / R528
ux-design-audit.watch / R525 doc-coverage.watch / R522 anti-min.watch
/ R519 compliance.watch / R516 router.watch / R513 trinity.watch /
R488 master-dashboard.watch.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
SURFACE_MAP = REPO_ROOT / "scripts" / "operator" / "surface-map.py"
ATOMIC_STATE = REPO_ROOT / "scripts" / "weaver" / "atomic-state.py"


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


def test_atomic_state_primitive_present():
    """R534 watch loop calls `atomic-state.py list` — primitive MUST
    exist (master spec § 21.1 anchor)."""
    assert ATOMIC_STATE.is_file()


def test_weaver_help_advertises_verbs():
    """`sovereign-osctl weaver --help` MUST advertise the five new
    operator-discoverable verbs (status / list / read / write /
    watch)."""
    cp = _run_osctl(["weaver", "--help"], timeout=10)
    assert cp.returncode == 0, (
        f"weaver --help failed: {cp.stderr[:300]}"
    )
    combined = cp.stdout + cp.stderr
    for verb in ("status", "list", "read", "write", "watch"):
        assert f"weaver {verb}" in combined, (
            f"weaver --help must advertise {verb!r}; "
            f"got tail: {combined[-500:]}"
        )


def test_weaver_watch_subcommand_help():
    """`sovereign-osctl weaver watch --help` MUST advertise refresh +
    iterations flags and return exit 0."""
    cp = _run_osctl(["weaver", "watch", "--help"])
    assert cp.returncode == 0, (
        f"weaver watch --help failed: {cp.stderr[:300]}"
    )
    assert "--refresh" in cp.stdout
    assert "--iterations" in cp.stdout
    assert "weaver" in cp.stdout.lower()
    # Master spec § 21 + R453 anchor must surface — operator-§1g
    # 30-second visibility rule.
    assert "§ 21" in cp.stdout or "section 21" in cp.stdout.lower() \
        or "atomic" in cp.stdout.lower()


def test_weaver_watch_dry_run_single_render():
    """SOVEREIGN_OS_DRY_RUN=1 MUST cap the watch loop to a single
    render and exit 0 (CI-safe — operator-named guarantee mirroring
    R531 surface-map.watch / R528 ux-design-audit.watch)."""
    cp = _run_osctl(
        ["weaver", "watch", "--refresh", "1"],
        env_extra={"SOVEREIGN_OS_DRY_RUN": "1"},
        timeout=60,
    )
    assert cp.returncode == 0, (
        f"weaver watch DRY_RUN exit nonzero: {cp.returncode}\n"
        f"stderr: {cp.stderr[:300]}"
    )
    assert "weaver.watch" in cp.stdout
    assert "frame 1" in cp.stdout


def test_weaver_watch_iterations_flag():
    """`--iterations N` MUST bound the loop."""
    cp = _run_osctl(
        ["weaver", "watch", "--refresh", "1", "--iterations", "2"],
        timeout=60,
    )
    assert cp.returncode == 0, cp.stderr[:300]
    assert "frame 1" in cp.stdout
    assert "frame 2" in cp.stdout
    assert "frame 3" not in cp.stdout
    assert "reached --iterations=2" in cp.stdout


def test_weaver_watch_refresh_floor():
    """`--refresh 0` MUST be coerced to the 1s floor."""
    cp = _run_osctl(
        ["weaver", "watch", "--refresh", "0"],
        env_extra={"SOVEREIGN_OS_DRY_RUN": "1"},
        timeout=60,
    )
    assert cp.returncode == 0
    assert "refresh=1s" in cp.stdout


def test_weaver_watch_rejects_unknown_flag():
    cp = _run_osctl(
        ["weaver", "watch", "--no-such-flag"],
        timeout=5,
    )
    assert cp.returncode != 0


def test_weaver_watch_renders_weaver_brief_panel():
    """The watch frame MUST embed the Weaver brief panel — operator-
    §1g visibility rule. The brief panel always prints the literal
    `[Weaver]` header regardless of whether podman / vfio /
    tank/context are present (the panel printf-s 'not installed' /
    'unknown' / 'absent' fallbacks)."""
    cp = _run_osctl(
        ["weaver", "watch", "--refresh", "1"],
        env_extra={"SOVEREIGN_OS_DRY_RUN": "1"},
        timeout=60,
    )
    assert cp.returncode == 0
    out = cp.stdout
    assert "weaver.watch" in out
    assert "[Weaver]" in out, (
        f"watch frame must render the Weaver brief panel; "
        f"got head: {out[:400]}"
    )
    # The 4-state-fabric file presence section MUST appear (master
    # spec § 21 anchor — IDENTITY / SOUL / AGENTS / CLAUDE).
    assert "STATE FABRIC" in out or "state fabric" in out.lower(), (
        f"watch frame must render the state-fabric listing; "
        f"got head: {out[:400]}"
    )


def test_weaver_status_default_renders_brief_panel():
    """Bare `sovereign-osctl weaver` (no verb) MUST render the brief
    panel — same shape as `weaver status`."""
    cp = _run_osctl(["weaver"], timeout=10)
    assert cp.returncode == 0, cp.stderr[:300]
    assert "[Weaver]" in cp.stdout


def test_weaver_list_delegates_to_atomic_state():
    """`sovereign-osctl weaver list` MUST delegate to atomic-state.py
    — same data the CLI / TUI / future MCP / future API surfaces will
    share. We can't assert specific output without a live
    /mnt/vault/context, but exit code must be 0 or 1 (the primitive
    handles missing-context-dir gracefully)."""
    cp = _run_osctl(["weaver", "list"], timeout=10)
    # Atomic-state.py exits 0 even when files are absent (it prints
    # "absent" rows). Exit 2 = ARG ERROR, which would be a regression.
    assert cp.returncode in (0, 1), (
        f"weaver list returned unexpected exit {cp.returncode}; "
        f"stderr: {cp.stderr[:300]}"
    )


def test_weaver_unknown_subcommand_rejected():
    """Unknown verb MUST exit nonzero — operator-discoverable error
    surface (R478 operator-§1g rule)."""
    cp = _run_osctl(["weaver", "not-a-real-verb"], timeout=5)
    assert cp.returncode != 0


def test_top_level_help_lists_weaver_watch():
    """The top-level `sovereign-osctl --help` MUST surface the
    weaver watch subverb post-R534 — operator-§1g 30-second
    visibility rule."""
    cp = _run_osctl(["--help"], timeout=5)
    combined = cp.stdout + cp.stderr
    assert "weaver watch" in combined, (
        f"top-level help must list 'weaver watch'; "
        f"got tail: {combined[-500:]}"
    )


def test_weaver_extended_to_tui_surface():
    """R534 extends the weaver entry to 4 shipped surfaces — tui MUST
    appear as shipped, NOT as a FUTURE waiver."""
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module",
         "weaver", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr[:300]
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    assert entry.get("surface_count", 0) >= 4, (
        f"weaver must be at >=4 surfaces post-R534; got {entry}"
    )
    matrix = entry.get("matrix", [])
    tui_row = next(
        (r for r in matrix if r.get("surface") == "tui"), None
    )
    assert tui_row is not None, (
        "weaver matrix missing tui row"
    )
    assert tui_row.get("state") == "shipped", (
        f"weaver tui surface must be shipped post-R534; got {tui_row}"
    )
    # R534 drains the tui waiver. R535 will drain mcp; R536 will
    # drain api + webapp (and may REPLACE the service: not applicable
    # waiver with a real read-only daemon, same ceiling-promotion
    # pattern as R510/R515/R518/R521/R524/R527/R530/R533). The tui-
    # shipped invariant above is the load-bearing R534 contract.
    future_count = entry.get("future_waiver_count", 0)
    assert future_count == 3, (
        f"weaver must have exactly 3 FUTURE waivers remaining post-"
        f"R534 (api/mcp/webapp); got {future_count}"
    )
