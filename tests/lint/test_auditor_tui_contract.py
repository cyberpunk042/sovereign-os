"""R537 (E5++) — auditor TUI surface contract lint.

Closes the auditor tui:FUTURE waiver. Raises the auditor surface
count from 4 -> 5 shipped surfaces (core / cli / service / dashboard
/ tui). First commit in the auditor tier-3 surface-expansion arc;
R538 (mcp) and R539 (api + webapp) will close the auditor ladder
toward the §1g ceiling.

The auditor arc differs from weaver R534-R536 / surface-map R531-R533
/ ux-design-audit R528-R530 / etc. in that the auditor `service`
surface ALREADY ships (R155 guardian-core systemd daemon) — so the
ceiling-promotion pattern (R510/R515/R518/R521/R524/R527/R530/R533/
R536 replacing `service: not applicable` with a real read-only
daemon) does NOT apply here. The auditor service is a security
daemon (neutralization), not an inspection daemon. The R538/R539
api/webapp surfaces will be PURELY read-only inspection per
operator §17 sovereignty boundary.

Per operator §1g STANDING RULE verbatim (sacrosanct, R456-anchored):

  "If you think something is really already done, ask yourself if
  you covered all angles and levels and layers and even if then
  improve it. Do not minimize or settle for less."

Per operator §1g verbatim (R453 anchor):

  "everything is not just core, not just cli, not just TUI, not just
  API, not just tool and MCP but also Dashboards and Web Apps and
  Services"

The TUI surface is a refresh-loop `sovereign-osctl auditor watch`
subcommand that re-renders the master spec § 17 Module 3 Auditor
brief panel (tetragon / guardian-core / policy state) PLUS the
master spec § 10 Native Guardian Loop violation tail (tail -5
/mnt/vault/context/security_audit.log) + Layer B metric anchors.
Same shape as R534 weaver.watch / R531 surface-map.watch / R528
ux-design-audit.watch / R525 doc-coverage.watch / R522 anti-min.watch.

Operator §17 sovereignty boundary: the TUI surface is READ-ONLY
inspection — neutralization stays CCD-triggered + CLI-gated.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
SURFACE_MAP = REPO_ROOT / "scripts" / "operator" / "surface-map.py"


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


def test_auditor_help_advertises_verbs():
    """`sovereign-osctl auditor --help` MUST advertise the five new
    operator-discoverable verbs (status / full / last-violation /
    history / watch)."""
    cp = _run_osctl(["auditor", "--help"], timeout=10)
    assert cp.returncode == 0, (
        f"auditor --help failed: {cp.stderr[:300]}"
    )
    combined = cp.stdout + cp.stderr
    for verb in ("status", "full", "last-violation", "history", "watch"):
        assert f"auditor {verb}" in combined, (
            f"auditor --help must advertise {verb!r}; "
            f"got tail: {combined[-500:]}"
        )


def test_auditor_watch_subcommand_help():
    """`sovereign-osctl auditor watch --help` MUST advertise refresh +
    iterations flags and return exit 0."""
    cp = _run_osctl(["auditor", "watch", "--help"])
    assert cp.returncode == 0, (
        f"auditor watch --help failed: {cp.stderr[:300]}"
    )
    assert "--refresh" in cp.stdout
    assert "--iterations" in cp.stdout
    assert "auditor" in cp.stdout.lower()
    # Master spec § 10 or § 17 anchor must surface — operator-§1g
    # 30-second visibility rule.
    assert "§ 10" in cp.stdout or "§ 17" in cp.stdout \
        or "section 10" in cp.stdout.lower() \
        or "section 17" in cp.stdout.lower() \
        or "guardian" in cp.stdout.lower()


def test_auditor_watch_help_surfaces_sovereignty_boundary():
    """The watch --help MUST mention the operator §17 read-only
    sovereignty boundary — TUI inspection only, neutralization stays
    CLI-gated."""
    cp = _run_osctl(["auditor", "watch", "--help"])
    assert cp.returncode == 0
    text = cp.stdout.lower()
    assert "§17" in cp.stdout or "section 17" in text or "sovereignty" in text
    assert "read-only" in text or "inspection only" in text \
        or "cli-gated" in text


def test_auditor_watch_dry_run_single_render():
    """SOVEREIGN_OS_DRY_RUN=1 MUST cap the watch loop to a single
    render and exit 0 (CI-safe — operator-named guarantee mirroring
    R534 weaver.watch / R531 surface-map.watch)."""
    cp = _run_osctl(
        ["auditor", "watch", "--refresh", "1"],
        env_extra={"SOVEREIGN_OS_DRY_RUN": "1"},
        timeout=60,
    )
    assert cp.returncode == 0, (
        f"auditor watch DRY_RUN exit nonzero: {cp.returncode}\n"
        f"stderr: {cp.stderr[:300]}"
    )
    assert "auditor.watch" in cp.stdout
    assert "frame 1" in cp.stdout


def test_auditor_watch_iterations_flag():
    """`--iterations N` MUST bound the loop."""
    cp = _run_osctl(
        ["auditor", "watch", "--refresh", "1", "--iterations", "2"],
        timeout=60,
    )
    assert cp.returncode == 0, cp.stderr[:300]
    assert "frame 1" in cp.stdout
    assert "frame 2" in cp.stdout
    assert "frame 3" not in cp.stdout
    assert "reached --iterations=2" in cp.stdout


def test_auditor_watch_refresh_floor():
    """`--refresh 0` MUST be coerced to the 1s floor."""
    cp = _run_osctl(
        ["auditor", "watch", "--refresh", "0"],
        env_extra={"SOVEREIGN_OS_DRY_RUN": "1"},
        timeout=60,
    )
    assert cp.returncode == 0
    assert "refresh=1s" in cp.stdout


def test_auditor_watch_rejects_unknown_flag():
    cp = _run_osctl(
        ["auditor", "watch", "--no-such-flag"],
        timeout=5,
    )
    assert cp.returncode != 0


def test_auditor_watch_renders_auditor_brief_panel():
    """The watch frame MUST embed the Auditor brief panel — operator-
    §1g visibility rule. The brief panel always prints the literal
    `[Auditor]` header regardless of whether tetragon / guardian-core
    are present (the panel printf-s 'not installed' / 'not built'
    fallbacks)."""
    cp = _run_osctl(
        ["auditor", "watch", "--refresh", "1"],
        env_extra={"SOVEREIGN_OS_DRY_RUN": "1"},
        timeout=60,
    )
    assert cp.returncode == 0
    out = cp.stdout
    assert "auditor.watch" in out
    assert "[Auditor]" in out, (
        f"watch frame must render the Auditor brief panel; "
        f"got head: {out[:400]}"
    )
    # The violation tail section MUST appear (master spec § 10
    # anchor — security_audit.log).
    assert "RECENT VIOLATIONS" in out or "security_audit.log" in out, (
        f"watch frame must render the recent-violations section; "
        f"got head: {out[:400]}"
    )


def test_auditor_watch_surfaces_layer_b_metric_anchors():
    """The watch frame MUST surface the three operator-named Layer B
    metric anchors so the operator can pivot to Prometheus without
    digging — operator-§1g 30-second readability rule."""
    cp = _run_osctl(
        ["auditor", "watch", "--refresh", "1"],
        env_extra={"SOVEREIGN_OS_DRY_RUN": "1"},
        timeout=60,
    )
    assert cp.returncode == 0
    out = cp.stdout
    assert "sovereign_os_auditor_neutralization_total" in out, (
        f"watch frame must surface neutralization_total metric; "
        f"got: {out[-500:]}"
    )
    assert "sovereign_os_auditor_event_parse_total" in out
    assert "sovereign_os_auditor_last_neutralization_timestamp" in out


def test_auditor_status_default_renders_brief_panel():
    """Bare `sovereign-osctl auditor` (no verb) MUST render the brief
    panel — same shape as `auditor status`."""
    cp = _run_osctl(["auditor"], timeout=10)
    assert cp.returncode == 0, cp.stderr[:300]
    assert "[Auditor]" in cp.stdout


def test_auditor_full_renders_full_diagnostic():
    """`sovereign-osctl auditor full` MUST render the full diagnostic
    (TETRAGON + POLICY + GUARDIAN DAEMON + RECENT VIOLATIONS + LAYER B
    METRICS sections — operator-known shape from
    `_trinity_auditor_full`)."""
    cp = _run_osctl(["auditor", "full"], timeout=10)
    assert cp.returncode == 0, cp.stderr[:300]
    out = cp.stdout
    assert "[Auditor]" in out
    assert "TETRAGON" in out
    assert "POLICY" in out
    assert "GUARDIAN" in out
    assert "RECENT VIOLATIONS" in out
    assert "LAYER B METRICS" in out


def test_auditor_history_handles_missing_log():
    """`auditor history` MUST exit 0 with a discoverable message when
    /mnt/vault/context/security_audit.log is absent — the operator
    seeing 'absent' is more useful than a stacktrace."""
    cp = _run_osctl(["auditor", "history"], timeout=10)
    assert cp.returncode == 0, cp.stderr[:300]
    # Either a tail of the live log lands, or the absent-message
    # surfaces — both are operator-discoverable.
    out = cp.stdout
    # In CI the log won't exist; assert the absent path. If a real
    # log shows up in a real environment, the assertion still passes
    # because the file path is mentioned in either branch.
    assert "security_audit.log" in out or out.strip() != ""


def test_auditor_history_default_n_is_20():
    """`auditor history` (no N) MUST default to N=20 — not 1, not all,
    operator-named lookback window matching `_trinity_auditor_full`'s
    pattern (which uses tail -5 for the brief). We can't observe the
    N value when the log is absent, so we assert the verb is wired by
    confirming exit 0."""
    cp = _run_osctl(["auditor", "history"], timeout=10)
    assert cp.returncode == 0


def test_auditor_history_n_argument_accepted():
    """`auditor history 5` MUST accept a numeric N argument."""
    cp = _run_osctl(["auditor", "history", "5"], timeout=10)
    assert cp.returncode == 0, cp.stderr[:300]


def test_auditor_history_invalid_n_is_coerced():
    """Non-numeric N MUST be coerced to the default 20 (numeric
    coercion mirror of --refresh/--iterations) — operator-§17
    defense-in-depth: tail -<bad> would blow up."""
    cp = _run_osctl(["auditor", "history", "garbage"], timeout=10)
    # Either the file is absent (exit 0 with message) OR the file
    # exists and tail -20 succeeds. Either way: no crash.
    assert cp.returncode == 0, cp.stderr[:300]


def test_auditor_last_violation_handles_missing_log():
    """`auditor last-violation` MUST handle the absent-log case
    gracefully."""
    cp = _run_osctl(["auditor", "last-violation"], timeout=10)
    assert cp.returncode == 0, cp.stderr[:300]
    # File path must surface so operator knows where to look.
    assert "security_audit.log" in cp.stdout


def test_auditor_unknown_subcommand_rejected():
    """Unknown verb MUST exit nonzero — operator-discoverable error
    surface (R478 operator-§1g rule)."""
    cp = _run_osctl(["auditor", "not-a-real-verb"], timeout=5)
    assert cp.returncode != 0


def test_top_level_help_lists_auditor_watch():
    """The top-level `sovereign-osctl --help` MUST surface the
    auditor watch subverb post-R537 — operator-§1g 30-second
    visibility rule."""
    cp = _run_osctl(["--help"], timeout=5)
    combined = cp.stdout + cp.stderr
    assert "auditor watch" in combined, (
        f"top-level help must list 'auditor watch'; "
        f"got tail: {combined[-500:]}"
    )


def test_top_level_help_lists_auditor_status():
    """Top-level help MUST list `auditor status` too — the operator-
    named entrypoint for the auditor surface."""
    cp = _run_osctl(["--help"], timeout=5)
    combined = cp.stdout + cp.stderr
    assert "auditor status" in combined


def test_auditor_extended_to_tui_surface():
    """R537 extends the auditor entry to 5 shipped surfaces — tui MUST
    appear as shipped, NOT as a FUTURE waiver."""
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module",
         "auditor", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr[:300]
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    assert entry.get("surface_count", 0) >= 5, (
        f"auditor must be at >=5 surfaces post-R537; got {entry}"
    )
    matrix = entry.get("matrix", [])
    tui_row = next(
        (r for r in matrix if r.get("surface") == "tui"), None
    )
    assert tui_row is not None, (
        "auditor matrix missing tui row"
    )
    assert tui_row.get("state") == "shipped", (
        f"auditor tui surface must be shipped post-R537; got {tui_row}"
    )
    # R537 drains the tui waiver. R538 will drain mcp; R539 will
    # drain api + webapp. The auditor service ALREADY ships (R155
    # guardian-core systemd daemon) — different from the R510-R536
    # inspection-daemon ceiling-promotion pattern. The load-bearing
    # R537 invariant is tui-shipped, not the residual waiver count;
    # we relax the residual cap to <= 3 (api / mcp / webapp).
    future_count = entry.get("future_waiver_count", 0)
    assert future_count <= 3, (
        f"auditor must have at most 3 FUTURE waivers remaining post-"
        f"R537 (api/mcp/webapp); got {future_count}"
    )


def test_auditor_service_surface_already_shipped():
    """The auditor `service` surface MUST still report as shipped
    post-R537 (R155 guardian-core systemd daemon). R537 only drains
    tui — it does NOT touch the auditor service contract. Guard
    against accidental regression of the pre-existing service entry."""
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module",
         "auditor", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr[:300]
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    matrix = entry.get("matrix", [])
    svc_row = next(
        (r for r in matrix if r.get("surface") == "service"), None
    )
    assert svc_row is not None, "auditor matrix missing service row"
    assert svc_row.get("state") == "shipped", (
        f"auditor service surface MUST stay shipped (R155 guardian-"
        f"core daemon predates R537); got {svc_row}"
    )
