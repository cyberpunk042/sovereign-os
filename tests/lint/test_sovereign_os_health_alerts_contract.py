"""Contract tests for the sovereign-os operational-health alert rules.

Locks that the alerts on sovereign-os's OWN core health metrics — the ones
the recurrent hooks emit (hardware-integrity gate, security perimeter, ZFS
pool, state-fabric backups) — stay well-formed and reference only metrics a
hook actually emits, so the operator-visible page surface can't silently
drift from the producer.

The generic tests/lint/test_alert_runbook_anchor_coverage.py separately
asserts every alert's runbook anchor resolves to a real heading in the
m060 deployment guide; this file owns the per-family structure.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = (
    REPO_ROOT / "config" / "prometheus" / "alerts" / "sovereign-os-health.rules.yml"
)

# The metric families the sovereign-os recurrent hooks emit that this rule
# set alerts on. Kept in lockstep with the emitters:
#   sovereign_os_friction_audit_failures            scripts/hooks/post-install/friction-audit-runtime.sh
#   sovereign_os_perimeter_status                   scripts/hooks/recurrent/tetragon-policy-verify.sh
#   sovereign_os_perimeter_verify_last_run_timestamp        (same)
#   sovereign_os_zfs_pool_health                    scripts/hooks/recurrent/zfs-scrub.sh
#   sovereign_os_zfs_scrub_last_run_timestamp               (same)
#   sovereign_os_snapshot_last_created_timestamp    scripts/hooks/recurrent/backup-snapshot.sh
EMITTED_METRICS = {
    "sovereign_os_friction_audit_failures",
    "sovereign_os_perimeter_status",
    "sovereign_os_perimeter_verify_last_run_timestamp",
    "sovereign_os_zfs_pool_health",
    "sovereign_os_zfs_scrub_last_run_timestamp",
    "sovereign_os_snapshot_last_created_timestamp",
    "sovereign_os_security_updates_available",
    "sovereign_os_security_update_check_last_run_timestamp",
    "sovereign_os_thermal_severity",
    "sovereign_os_thermal_last_run_unix",
}

EXPECTED_ALERTS = {
    "SovereignOsFrictionAuditFailing",
    "SovereignOsPerimeterDown",
    "SovereignOsPerimeterVerifierSilent",
    "SovereignOsZfsPoolDegraded",
    "SovereignOsZfsScrubOverdue",
    "SovereignOsBackupSnapshotStale",
    "SovereignOsSecurityUpdatesPending",
    "SovereignOsSecurityUpdateCheckStale",
    "SovereignOsThermalCritical",
    "SovereignOsThermalWatchSilent",
}


def _rules() -> list[dict]:
    doc = yaml.safe_load(RULES_PATH.read_text(encoding="utf-8"))
    groups = doc["groups"]
    assert len(groups) == 1 and groups[0]["name"] == "sovereign-os-health"
    return groups[0]["rules"]


def test_rules_file_exists_and_parses():
    assert RULES_PATH.is_file()
    assert _rules(), "at least one alert rule"


def test_expected_alerts_present():
    names = {r["alert"] for r in _rules()}
    assert EXPECTED_ALERTS <= names, EXPECTED_ALERTS - names


def test_every_expr_references_only_emitted_metrics():
    for r in _rules():
        expr = r["expr"]
        assert any(m in expr for m in EMITTED_METRICS), (
            f"{r['alert']} expr references no emitted metric: {expr}"
        )


def test_every_alert_has_severity_for_and_runbook():
    for r in _rules():
        assert r["labels"]["severity"] in {"warning", "critical"}, r["alert"]
        assert r["labels"].get("subsystem") in {"hardware", "perimeter", "storage", "security"}, r["alert"]
        assert "for" in r, r["alert"]
        url = r["annotations"]["runbook_url"]
        assert url.startswith("https://"), r["alert"]
        # runbook anchor matches the alert name, lower-cased.
        anchor = url.rsplit("#", 1)[-1]
        assert r["alert"].lower() in anchor, (r["alert"], anchor)


def test_critical_health_failures_are_critical_severity():
    """The three availability/integrity failures (audit failing, perimeter
    down, pool degraded) MUST page as critical — they are not warnings."""
    by_name = {r["alert"]: r for r in _rules()}
    for name in (
        "SovereignOsFrictionAuditFailing",
        "SovereignOsPerimeterDown",
        "SovereignOsZfsPoolDegraded",
        "SovereignOsThermalCritical",
    ):
        assert by_name[name]["labels"]["severity"] == "critical", name


def test_staleness_alerts_use_last_run_or_created_timestamp():
    """The 'observer silent / overdue / stale' alerts must be time()-since-
    timestamp comparisons, not value thresholds — otherwise a dead emitter
    (stuck gauge) would never trip them."""
    by_name = {r["alert"]: r for r in _rules()}
    for name in (
        "SovereignOsPerimeterVerifierSilent",
        "SovereignOsZfsScrubOverdue",
        "SovereignOsBackupSnapshotStale",
        "SovereignOsSecurityUpdateCheckStale",
        "SovereignOsThermalWatchSilent",
    ):
        expr = by_name[name]["expr"]
        assert "time()" in expr and ("timestamp" in expr or "last_run_unix" in expr), (name, expr)
