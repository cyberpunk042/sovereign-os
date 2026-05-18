"""R528 (E5++) — ux-design-audit TUI surface contract lint.

Closes the ux-design-audit tui:FUTURE waiver. Raises the ux-design-
audit surface count from 3 -> 4 shipped surfaces (core / cli /
dashboard / tui). First commit in the ux-design-audit tier-3 surface-
expansion arc; R529 (mcp) and R530 (api + webapp) will close the
ux-design-audit ladder to the §1g ceiling (modulo the service-not-
applicable waiver which the daemon promotion replaces, same pattern
as R510/R515/R518/R521/R524/R527).

Per operator §1g STANDING RULE verbatim (sacrosanct, R456-anchored):

  "If you think something is really already done, ask yourself if
  you covered all angles and levels and layers and even if then
  improve it. Do not minimize or settle for less."

Per operator §1g verbatim (R457 anchor):

  "everything will also need to go through a thorough UX Design stage
  in order to be of quality"

The TUI surface is a refresh-loop `sovereign-osctl ux-design-audit
watch` subcommand that re-renders the R457 6-UX-dimension score
matrix continuously — same shape as R525 doc-coverage.watch, R522
anti-min.watch, R519 compliance.watch, R516 router.watch, R513
trinity.watch, R488 master-dashboard.watch.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
SURFACE_MAP = REPO_ROOT / "scripts" / "operator" / "surface-map.py"

# R457 6 UX dimension ids — each must be operator-discoverable in the
# audit (the watch frame embeds the `ux-design-audit score` output;
# the dimension names themselves live in `dimensions` and `audit`).
R457_UX_DIMENSIONS = (  # R457 R528
    "action-budget", "discoverable",     # R457 R528
    "recoverable", "next-step",          # R457 R528
    "operator-named", "readable-30s",    # R457 R528
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


def test_ux_design_audit_watch_subcommand_help():
    """`sovereign-osctl ux-design-audit watch --help` MUST advertise
    refresh + iterations flags and return exit 0."""
    cp = _run_osctl(["ux-design-audit", "watch", "--help"])
    assert cp.returncode == 0, (
        f"ux-design-audit watch --help failed: {cp.stderr[:300]}"
    )
    assert "--refresh" in cp.stdout
    assert "--iterations" in cp.stdout
    assert "ux-design-audit" in cp.stdout.lower()


def test_ux_design_audit_watch_dry_run_single_render():
    """SOVEREIGN_OS_DRY_RUN=1 MUST cap the watch loop to a single
    render and exit 0 (CI-safe — operator-named guarantee mirroring
    R525 doc-coverage.watch / R522 anti-min.watch)."""
    cp = _run_osctl(
        ["ux-design-audit", "watch", "--refresh", "1"],
        env_extra={"SOVEREIGN_OS_DRY_RUN": "1"},
        timeout=60,
    )
    assert cp.returncode == 0, (
        f"ux-design-audit watch DRY_RUN exit nonzero: {cp.returncode}\n"
        f"stderr: {cp.stderr[:300]}"
    )
    assert "ux-design-audit.watch" in cp.stdout
    assert "frame 1" in cp.stdout


def test_ux_design_audit_watch_iterations_flag():
    """`--iterations N` MUST bound the loop."""
    cp = _run_osctl(
        ["ux-design-audit", "watch", "--refresh", "1",
         "--iterations", "2"],
        timeout=60,
    )
    assert cp.returncode == 0, cp.stderr[:300]
    assert "frame 1" in cp.stdout
    assert "frame 2" in cp.stdout
    assert "frame 3" not in cp.stdout
    assert "reached --iterations=2" in cp.stdout


def test_ux_design_audit_watch_refresh_floor():
    """`--refresh 0` MUST be coerced to the 1s floor."""
    cp = _run_osctl(
        ["ux-design-audit", "watch", "--refresh", "0"],
        env_extra={"SOVEREIGN_OS_DRY_RUN": "1"},
        timeout=60,
    )
    assert cp.returncode == 0
    assert "refresh=1s" in cp.stdout


def test_ux_design_audit_watch_rejects_unknown_flag():
    cp = _run_osctl(
        ["ux-design-audit", "watch", "--no-such-flag"],
        timeout=5,
    )
    assert cp.returncode != 0


def test_ux_design_audit_watch_renders_score_matrix():
    """The watch frame MUST embed the R457 score matrix — operator-
    §1g visibility rule (the watch loop calls `ux-design-audit score`,
    so every tracked module shows up with an X/6 score)."""
    cp = _run_osctl(
        ["ux-design-audit", "watch", "--refresh", "1"],
        env_extra={"SOVEREIGN_OS_DRY_RUN": "1"},
        timeout=60,
    )
    assert cp.returncode == 0
    out = cp.stdout
    assert "ux-design-audit.score" in out, (
        "watch frame must embed the R457 `score` matrix; "
        f"got head: {out[:400]}"
    )
    # The score emit reports per-module ratings as e.g. "4/6" / "5/6"
    # / "6/6". At least one such cell must appear (operator-§1g 30-
    # second visibility rule — the matrix must be RENDERED, not just
    # referenced).
    assert "/6" in out, (
        f"watch frame must render at least one X/6 score cell; "
        f"got head: {out[:400]}"
    )


def test_ux_design_audit_non_watch_verbs_still_delegate_to_python():
    """R528 wraps `watch`; the existing 6 verbs (dimensions / modules /
    audit / score / report / selfdef) MUST still delegate to
    ux-design-audit.py — no regression."""
    cp = _run_osctl(["ux-design-audit", "dimensions", "--json"], timeout=60)
    assert cp.returncode == 0, (
        f"ux-design-audit dimensions --json broken post-R528: "
        f"{cp.stderr[:300]}"
    )
    data = json.loads(cp.stdout)
    assert "dimensions" in data
    assert len(data["dimensions"]) == 6
    names = {d.get("id") for d in data["dimensions"]}
    for dim in R457_UX_DIMENSIONS:
        assert dim in names, (
            f"R457 UX dimension {dim!r} missing post-R528; got {names}"
        )


def test_top_level_help_lists_ux_design_audit_watch():
    """The top-level `sovereign-osctl --help` MUST surface the
    ux-design-audit watch subverb post-R528 — operator-§1g 30-second
    visibility rule."""
    cp = _run_osctl(["--help"], timeout=5)
    combined = cp.stdout + cp.stderr
    assert "ux-design-audit watch" in combined, (
        f"top-level help must list 'ux-design-audit watch'; "
        f"got tail: {combined[-500:]}"
    )


def test_ux_design_audit_surface_map_extended_to_tui():
    """R528 extends ux-design-audit surface-map to 4 shipped
    surfaces — tui MUST appear as shipped, NOT as a FUTURE waiver."""
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module",
         "ux-design-audit", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr[:300]
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    assert entry.get("surface_count", 0) >= 4, (
        f"ux-design-audit must be at >=4 surfaces post-R528; got {entry}"
    )
    matrix = entry.get("matrix", [])
    tui_row = next(
        (r for r in matrix if r.get("surface") == "tui"), None
    )
    assert tui_row is not None, (
        "ux-design-audit matrix missing tui row"
    )
    assert tui_row.get("state") == "shipped", (
        f"ux-design-audit tui surface must be shipped; got {tui_row}"
    )
    # R528 drains the tui waiver. R529 will drain mcp; R530 will
    # drain api + webapp (and REPLACE the service: not applicable
    # waiver with a real read-only daemon, same ceiling-promotion
    # pattern as R510/R515/R518/R521/R524/R527). The tui-shipped
    # invariant above is the load-bearing R528 contract.
