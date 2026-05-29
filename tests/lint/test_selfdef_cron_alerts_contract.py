"""Selfdef cron + systemd-timer alerts — contract test."""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = (
    REPO_ROOT / "config" / "prometheus" / "alerts"
    / "selfdef-cron.rules.yml"
)

REQUIRED_ALERTS = {
    "SelfdefCronTextfileEmitFailed",
    "SelfdefCronObserverSilent",
    "SelfdefCronEntryDriftHigh",
    "SelfdefCronDFileCountDrift",
    "SelfdefSystemdTimerDrift",
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
        assert r["labels"]["subsystem"] == "selfdef-cron"
        assert r["labels"]["severity"] in ("warning", "critical")


def test_observer_silent_threshold_300s():
    by_name = {r["alert"]: r for r in _all_rules()}
    assert "> 300" in by_name["SelfdefCronObserverSilent"]["expr"]


def test_drift_alerts_use_changes_over_1h():
    """Drift alerts MUST use changes() over a 1-hour window — not
    direct gauge comparison, since absolute counts vary per host."""
    by_name = {r["alert"]: r for r in _all_rules()}
    for drift_alert in ("SelfdefCronEntryDriftHigh",
                        "SelfdefCronDFileCountDrift",
                        "SelfdefSystemdTimerDrift"):
        expr = by_name[drift_alert]["expr"]
        assert "changes(" in expr, f"{drift_alert} must use changes()"
        assert "[1h])" in expr, f"{drift_alert} must use 1h window"


def test_cron_d_drift_targets_root_level_surface():
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefCronDFileCountDrift"]["expr"]
    assert "selfdef_cron_d_files" in expr


def test_systemd_timer_drift_targets_canonical_gauge():
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefSystemdTimerDrift"]["expr"]
    assert "selfdef_systemd_timers_total" in expr


def test_severity_classification():
    by_name = {r["alert"]: r for r in _all_rules()}
    expected = {
        "SelfdefCronTextfileEmitFailed": "critical",
        "SelfdefCronObserverSilent":     "critical",
        "SelfdefCronEntryDriftHigh":     "warning",
        "SelfdefCronDFileCountDrift":    "warning",
        "SelfdefSystemdTimerDrift":      "warning",
    }
    for name, sev in expected.items():
        assert by_name[name]["labels"]["severity"] == sev


def test_cron_link_labels_canonical():
    by_name = {r["alert"]: r for r in _all_rules()}
    expected = {
        "SelfdefCronTextfileEmitFailed": "observer-fault",
        "SelfdefCronObserverSilent":     "observer-silent",
        "SelfdefCronEntryDriftHigh":     "entry-drift",
        "SelfdefCronDFileCountDrift":    "cron-d-drift",
        "SelfdefSystemdTimerDrift":      "systemd-timer-drift",
    }
    for name, link in expected.items():
        assert by_name[name]["labels"].get("cron_link") == link


def test_rule_group_interval_30s():
    doc = yaml.safe_load(RULES_PATH.read_text())
    g = next(g for g in doc["groups"] if g["name"] == "selfdef-cron")
    assert g["interval"] == "30s"


def test_rules_cite_selfdef_producer_commit():
    assert "b80b389" in RULES_PATH.read_text()


def test_every_alert_carries_runbook_url():
    for r in _all_rules():
        url = r["annotations"].get("runbook_url", "")
        assert "m060-deployment-guide.md#" in url
