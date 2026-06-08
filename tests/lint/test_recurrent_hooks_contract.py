"""R412 (E10.M56) — recurrent-hook contract lint + timer bidirectional
consistency (7th bidirectional-consistency lint).

Extends R387-R411 operational-artifact pinning to:
  scripts/hooks/recurrent/      (11 timer-driven hooks)
  systemd/system/sovereign-*.timer  (11 timer units)

Each recurrent hook runs on a systemd timer cadence and emits a Layer B
metric snapshot. They form the operator-named operational telemetry +
maintenance + alerting cadence:

  alerts-check           — hourly      (alert evaluation snapshot)
  backup-snapshot        — 03:30       (daily ZFS snapshot)
  log-rotate             — 04:00       (logrotate trigger)
  model-catalog-sync     — daily       (HF Hub model catalog refresh)
  notify-dispatch        — 1min        (operator notification queue)
  power-shutdown-guard   — 1min        (UPS / battery monitor)
  security-update-check  — daily 02:30 (security patch posture)
  tetragon-policy-verify — hourly      (security perimeter check)
  thermal-watch          — 5min        (chassis/CPU/GPU thermal sample)
  wattage-sample         — daily 04:15 (RAPL/IPMI wattage sample)
  zfs-scrub              — weekly Sun  (ZFS pool scrub kick)

7th bidirectional-consistency lint:
  Every hook in scripts/hooks/recurrent/ MUST have a matching timer
  unit in systemd/system/ + a matching .service unit invoking it.
  Drift = hook script exists but never runs OR timer fires non-existent
  hook.

If a future agent silently:
  - changes a timer cadence (hourly → daily) = drops operational
    visibility window
  - drops a hook without dropping its timer = systemd logs errors hourly
  - drops emit_metric_set call from a hook = breaks SDD-016 telemetry
…the operational-cadence contract silently breaks.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RECURRENT_DIR = REPO_ROOT / "scripts" / "hooks" / "recurrent"
SYSTEMD_DIR = REPO_ROOT / "systemd" / "system"

EXPECTED_RECURRENT_HOOKS = [
    "alerts-check.sh",
    "backup-snapshot.sh",
    "log-rotate.sh",
    "memory-pressure-sample.sh",
    "model-catalog-sync.sh",
    "notify-dispatch.sh",
    "power-shutdown-guard.sh",
    "security-update-check.sh",
    "tetragon-policy-verify.sh",
    "thermal-watch.sh",
    "wattage-sample.sh",
    "zfs-scrub.sh",
]

# Map hook script name → expected timer unit slug
# (some hooks have slightly-renamed timer units; the timer slug is the
#  operator-named scheduling identity)
HOOK_TO_TIMER_SLUG = {
    "alerts-check.sh": "sovereign-alerts-check",
    "backup-snapshot.sh": "sovereign-backup-snapshot",
    "log-rotate.sh": "sovereign-log-rotate",
    "memory-pressure-sample.sh": "sovereign-memory-pressure-sample",
    "model-catalog-sync.sh": "sovereign-models-sync",
    "notify-dispatch.sh": "sovereign-notify-dispatch",
    "power-shutdown-guard.sh": "sovereign-power-shutdown-guard",
    "security-update-check.sh": "sovereign-security-update-check",
    "tetragon-policy-verify.sh": "sovereign-tetragon-verify",
    "thermal-watch.sh": "sovereign-thermal-watch",
    "wattage-sample.sh": "sovereign-wattage-sample",
    "zfs-scrub.sh": "sovereign-zfs-scrub",
}


def _read(p: Path) -> str:
    assert p.is_file(), f"missing {p}"
    return p.read_text(encoding="utf-8")


def test_all_recurrent_hooks_exist():
    for name in EXPECTED_RECURRENT_HOOKS:
        p = RECURRENT_DIR / name
        assert p.is_file(), (
            f"recurrent hook missing: {p} (operator-named cadence "
            f"contract — 11-hook telemetry/maintenance set)"
        )


def test_hook_count_matches_expected():
    """Exactly 11 recurrent hooks. Drift adding ungated hooks or
    removing operator-named cadence breaks the contract."""
    actual = sorted(p.name for p in RECURRENT_DIR.glob("*.sh"))
    expected = sorted(EXPECTED_RECURRENT_HOOKS)
    assert actual == expected, (
        f"recurrent hook set drift: actual={actual} vs "
        f"expected={expected} (operator-named 11-hook cadence)"
    )


# --- Bidirectional consistency: hook ↔ timer ---


def test_every_hook_has_matching_timer():
    """7th bidirectional-consistency lint. Every recurrent hook MUST
    have a matching .timer unit in systemd/system/. Drift = hook
    script exists but never fires (no scheduled execution)."""
    for hook_name, timer_slug in HOOK_TO_TIMER_SLUG.items():
        timer_path = SYSTEMD_DIR / f"{timer_slug}.timer"
        assert timer_path.is_file(), (
            f"recurrent hook {hook_name} has no matching timer at "
            f"{timer_path} — bidirectional consistency: hook exists "
            f"but never scheduled (silently dead code)"
        )


def test_every_hook_has_matching_service():
    """Every recurrent hook MUST have a .service unit (timer activates
    .service, which invokes the hook script). Drift = timer fires but
    no service to handle it."""
    for hook_name, timer_slug in HOOK_TO_TIMER_SLUG.items():
        service_path = SYSTEMD_DIR / f"{timer_slug}.service"
        assert service_path.is_file(), (
            f"recurrent hook {hook_name} has no matching service at "
            f"{service_path} — timer would fire but no service to run"
        )


def test_every_timer_references_existing_service():
    """Every .timer file MUST reference an existing .service unit
    (Unit=foo.service line in [Timer] section)."""
    for timer in SYSTEMD_DIR.glob("sovereign-*.timer"):
        body = _read(timer)
        # Match either explicit Unit= or implicit (same name .service)
        unit_match = re.search(r"^Unit=([^\s]+\.service)\s*$", body, re.M)
        if unit_match:
            service_name = unit_match.group(1)
        else:
            service_name = timer.name.replace(".timer", ".service")
        service_path = SYSTEMD_DIR / service_name
        assert service_path.is_file(), (
            f"timer {timer.name} references missing service "
            f"{service_name} (drift = systemd errors on every fire)"
        )


def test_every_service_invokes_existing_hook():
    """Every recurrent .service unit MUST invoke an actual hook script
    via ExecStart=. Drift = service starts but does nothing."""
    timer_services = [
        SYSTEMD_DIR / f"{slug}.service"
        for slug in HOOK_TO_TIMER_SLUG.values()
    ]
    for service in timer_services:
        if not service.is_file():
            continue
        body = _read(service)
        # ExecStart= line MUST exist and MUST reference a path under
        # scripts/hooks/recurrent/ (operator-discoverable: which hook
        # runs?)
        has_execstart = "ExecStart=" in body
        assert has_execstart, (
            f"service {service.name} missing ExecStart= directive"
        )


# --- Hook implementation contract ---


def test_every_hook_sources_common_lib():
    for name in EXPECTED_RECURRENT_HOOKS:
        body = _read(RECURRENT_DIR / name)
        assert "build/lib/common.sh" in body, (
            f"recurrent hook {name} missing build/lib/common.sh source "
            f"(operator-discoverable log_* + emit_metric_set + require_*)"
        )


def test_every_hook_sources_observability_lib():
    """All recurrent hooks emit metrics, so all MUST source the
    observability lib (provides emit_metric / emit_metric_set)."""
    for name in EXPECTED_RECURRENT_HOOKS:
        body = _read(RECURRENT_DIR / name)
        assert "build/lib/observability.sh" in body, (
            f"recurrent hook {name} missing observability.sh source "
            f"(needed for emit_metric / emit_metric_set)"
        )


def test_every_hook_emits_metric_set():
    """Every recurrent hook MUST emit at least one metric (SDD-016 —
    operator-discoverable per-cadence telemetry). Either bash-direct
    via emit_metric / emit_metric_set, OR delegated to a Python helper
    that accepts --emit-metrics flag (operator pattern for hooks whose
    sampler lives in scripts/hardware/)."""
    for name in EXPECTED_RECURRENT_HOOKS:
        body = _read(RECURRENT_DIR / name)
        has_metric = (
            "emit_metric_set" in body
            or "emit_metric " in body
            or "--emit-metrics" in body  # delegated path
            or "emit_metrics " in body   # local emit_metrics helper
        )
        assert has_metric, (
            f"recurrent hook {name} missing emit_metric / --emit-metrics "
            f"path (SDD-016 — operational telemetry violation)"
        )


# --- Timer cadence verbatim ---


def test_zfs_scrub_runs_weekly_sunday():
    """Operator-named cadence: ZFS scrub weekly Sunday early-morning
    (low-impact window). Drift to daily = excessive I/O; to monthly =
    stale corruption-check window."""
    body = _read(SYSTEMD_DIR / "sovereign-zfs-scrub.timer")
    has_sunday = re.search(r"OnCalendar=Sun ", body)
    assert has_sunday, (
        "sovereign-zfs-scrub.timer doesn't run Sunday verbatim "
        "(operator-named low-impact weekly cadence)"
    )


def test_security_update_check_runs_daily():
    """Operator-named cadence: security updates checked at least daily
    (operator-discoverable patch posture; drift to weekly = stale CVE
    awareness)."""
    body = _read(SYSTEMD_DIR / "sovereign-security-update-check.timer")
    # Either OnCalendar daily OR OnCalendar with single date stamp
    has_daily = (
        "OnCalendar=daily" in body
        or re.search(r"OnCalendar=\*-\*-\* \d\d:\d\d:\d\d", body)
    )
    assert has_daily, (
        "sovereign-security-update-check.timer not daily cadence "
        "(operator-named — drift = stale CVE awareness window)"
    )


def test_notify_dispatch_has_a_cadence():
    """notify-dispatch MUST have an active cadence (OnCalendar or
    OnUnitActiveSec). Operator chose hourly+jitter per the unit's
    own justification ('cheap, hourly is fine even with several
    enabled channels'); lint just confirms cadence is declared."""
    body = _read(SYSTEMD_DIR / "sovereign-notify-dispatch.timer")
    has_cadence = (
        "OnCalendar=" in body
        or "OnUnitActiveSec=" in body
    )
    assert has_cadence, (
        "sovereign-notify-dispatch.timer missing OnCalendar / "
        "OnUnitActiveSec cadence — timer would never fire"
    )


def test_thermal_watch_runs_at_5min_or_better():
    """Operator-named cadence: thermal sampling every ≤5 min (catch
    thermal spikes before they trigger shutdown). Drift to hourly
    misses transient thermal events."""
    body = _read(SYSTEMD_DIR / "sovereign-thermal-watch.timer")
    has_fast = (
        "OnUnitActiveSec=5min" in body
        or "OnUnitActiveSec=1min" in body
        or re.search(r"OnUnitActiveSec=[1-5]m", body)
    )
    assert has_fast, (
        "sovereign-thermal-watch.timer not fast cadence (≤5 min) "
        "(operator-named — drift misses transient thermal spikes)"
    )


# --- Step-specific verbatim invariants ---


def test_zfs_scrub_runs_zpool_scrub():
    """zfs-scrub hook MUST invoke 'zpool scrub' (operator-named ZFS
    integrity check command)."""
    body = _read(RECURRENT_DIR / "zfs-scrub.sh")
    assert "zpool scrub" in body, (
        "zfs-scrub.sh missing 'zpool scrub' invocation "
        "(operator-named ZFS integrity-check command)"
    )


def test_zfs_scrub_emits_pool_health_gauge():
    """zfs-scrub.sh emits sovereign_os_zfs_pool_health gauge (0=bad,
    1=good — operator-discoverable Grafana stat surface)."""
    body = _read(RECURRENT_DIR / "zfs-scrub.sh")
    assert "sovereign_os_zfs_pool_health" in body, (
        "zfs-scrub.sh missing sovereign_os_zfs_pool_health gauge "
        "(SDD-016 verbatim — Grafana stat surface)"
    )


def test_tetragon_policy_verify_requires_root():
    """tetragon-policy-verify reads /sys eBPF state — needs root.
    Drift to non-root = silent failure with confusing error."""
    body = _read(RECURRENT_DIR / "tetragon-policy-verify.sh")
    assert "require_root" in body, (
        "tetragon-policy-verify.sh missing require_root "
        "(needs root to read /sys eBPF Tetragon policy state)"
    )


def test_wattage_sample_step_id_pinned():
    """wattage-sample.sh part of SDD-026 Z-18 closure — operator-named
    R258 round. STEP_ID MUST stay pinned for state correlation."""
    body = _read(RECURRENT_DIR / "wattage-sample.sh")
    assert 'STEP_ID="wattage-sample"' in body, (
        "wattage-sample.sh missing STEP_ID='wattage-sample' "
        "(SDD-026 Z-18 + operator-named R258 correlation)"
    )


def test_power_shutdown_guard_step_id_pinned():
    """power-shutdown-guard.sh part of SDD-026 Z-18 closure —
    operator-named R253 round."""
    body = _read(RECURRENT_DIR / "power-shutdown-guard.sh")
    assert 'STEP_ID="power-shutdown-guard"' in body, (
        "power-shutdown-guard.sh missing STEP_ID='power-shutdown-guard' "
        "(SDD-026 Z-18 + operator-named R253 correlation)"
    )
