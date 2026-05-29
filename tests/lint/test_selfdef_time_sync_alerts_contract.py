"""Selfdef time-sync alerts — contract test."""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = (
    REPO_ROOT / "config" / "prometheus" / "alerts"
    / "selfdef-time-sync.rules.yml"
)

REQUIRED_ALERTS = {
    "SelfdefTimeSyncTextfileEmitFailed",
    "SelfdefTimeSyncObserverSilent",
    "SelfdefTimeSyncNotSynced",
    "SelfdefTimeSyncNtpInactive",
    "SelfdefTimeSyncDriftHigh",
    "SelfdefTimeSyncRtcLocalTz",
}


def _all_rules():
    doc = yaml.safe_load(RULES_PATH.read_text())
    return [r for g in doc["groups"] for r in g["rules"]]


def test_rules_file_present_and_valid_yaml():
    assert RULES_PATH.is_file()


def test_all_required_alerts_present():
    names = {r["alert"] for r in _all_rules()}
    assert not REQUIRED_ALERTS - names


def test_every_alert_carries_full_envelope():
    for r in _all_rules():
        for f in ("alert", "expr", "for", "labels", "annotations"):
            assert f in r
        assert r["labels"]["subsystem"] == "selfdef-time-sync"
        assert r["labels"]["severity"] in ("warning", "critical")


def test_observer_silent_300s():
    by_name = {r["alert"]: r for r in _all_rules()}
    assert "> 300" in by_name["SelfdefTimeSyncObserverSilent"]["expr"]


def test_emit_failed_references_sentinel():
    by_name = {r["alert"]: r for r in _all_rules()}
    assert "selfdef_time_sync_textfile_emit_failed" in by_name[
        "SelfdefTimeSyncTextfileEmitFailed"
    ]["expr"]


def test_not_synced_targets_synced_gauge():
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefTimeSyncNotSynced"]["expr"]
    assert "selfdef_time_sync_synced" in expr
    assert "== 0" in expr


def test_ntp_inactive_targets_ntp_gauge():
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefTimeSyncNtpInactive"]["expr"]
    assert "selfdef_time_sync_ntp_active" in expr
    assert "== 0" in expr


def test_drift_high_threshold_60s():
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefTimeSyncDriftHigh"]["expr"]
    assert "> 60" in expr
    assert "selfdef_time_sync_drift_seconds" in expr


def test_rtc_local_tz_targets_gauge():
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefTimeSyncRtcLocalTz"]["expr"]
    assert "selfdef_time_sync_rtc_local_tz" in expr
    assert "== 1" in expr


def test_severity_classification():
    by_name = {r["alert"]: r for r in _all_rules()}
    expected = {
        "SelfdefTimeSyncTextfileEmitFailed": "critical",
        "SelfdefTimeSyncObserverSilent":     "critical",
        "SelfdefTimeSyncNotSynced":          "critical",
        "SelfdefTimeSyncNtpInactive":        "critical",
        "SelfdefTimeSyncDriftHigh":          "warning",
        "SelfdefTimeSyncRtcLocalTz":         "warning",
    }
    for name, sev in expected.items():
        assert by_name[name]["labels"]["severity"] == sev


def test_time_link_labels_canonical():
    by_name = {r["alert"]: r for r in _all_rules()}
    expected = {
        "SelfdefTimeSyncTextfileEmitFailed": "observer-fault",
        "SelfdefTimeSyncObserverSilent":     "observer-silent",
        "SelfdefTimeSyncNotSynced":          "rollup",
        "SelfdefTimeSyncNtpInactive":        "rollup",
        "SelfdefTimeSyncDriftHigh":          "rollup",
        "SelfdefTimeSyncRtcLocalTz":         "rollup",
    }
    for name, link in expected.items():
        assert by_name[name]["labels"].get("time_link") == link


def test_descriptions_include_actionable_commands():
    """Every rollup alert MUST include an operator-runnable
    command in its description."""
    by_name = {r["alert"]: r for r in _all_rules()}
    assert "timedatectl set-ntp" in by_name["SelfdefTimeSyncNotSynced"]["annotations"]["description"]
    assert "systemctl enable" in by_name["SelfdefTimeSyncNtpInactive"]["annotations"]["description"]
    assert "hwclock" in by_name["SelfdefTimeSyncDriftHigh"]["annotations"]["description"]
    assert "set-local-rtc 0" in by_name["SelfdefTimeSyncRtcLocalTz"]["annotations"]["description"]


def test_rule_group_interval_30s():
    doc = yaml.safe_load(RULES_PATH.read_text())
    g = next(g for g in doc["groups"] if g["name"] == "selfdef-time-sync")
    assert g["interval"] == "30s"


def test_rules_cite_selfdef_producer_commit():
    assert "36d1c8f" in RULES_PATH.read_text()


def test_runbook_sections_present_for_every_alert():
    guide = REPO_ROOT / "docs" / "operator" / "m060-deployment-guide.md"
    body = guide.read_text()
    for name in REQUIRED_ALERTS:
        assert f"#### {name}" in body, f"missing #### {name}"
