"""Selfdef SDD-067 revocations alerts — contract test."""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = (
    REPO_ROOT / "config" / "prometheus" / "alerts"
    / "selfdef-revocations.rules.yml"
)

REQUIRED_ALERTS = {
    "SelfdefRevocationsTextfileEmitFailed",
    "SelfdefRevocationsObserverSilent",
    "SelfdefRevocationsStateDirMissing",
    "SelfdefRevocationsPendingRestoreBacklog",
    "SelfdefRevocationsActiveHigh",
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
        assert r["labels"]["subsystem"] == "selfdef-revocations"
        assert r["labels"]["severity"] in ("warning", "critical")


def test_observer_silent_threshold_300s():
    by_name = {r["alert"]: r for r in _all_rules()}
    assert "> 300" in by_name["SelfdefRevocationsObserverSilent"]["expr"]


def test_state_dir_missing_uses_present_eq_zero():
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefRevocationsStateDirMissing"]["expr"]
    assert "selfdef_revocations_state_dir_present == 0" in expr


def test_state_dir_missing_for_window_10m():
    by_name = {r["alert"]: r for r in _all_rules()}
    assert by_name["SelfdefRevocationsStateDirMissing"]["for"] == "10m"


def test_pending_backlog_threshold_5():
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefRevocationsPendingRestoreBacklog"]["expr"]
    assert "selfdef_revocations_pending_restores" in expr
    assert "> 5" in expr


def test_active_high_threshold_10():
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefRevocationsActiveHigh"]["expr"]
    assert "selfdef_revocations_active_count" in expr
    assert "> 10" in expr


def test_severity_classification():
    by_name = {r["alert"]: r for r in _all_rules()}
    expected = {
        "SelfdefRevocationsTextfileEmitFailed":     "critical",
        "SelfdefRevocationsObserverSilent":         "critical",
        "SelfdefRevocationsStateDirMissing":        "critical",
        "SelfdefRevocationsPendingRestoreBacklog":  "warning",
        "SelfdefRevocationsActiveHigh":             "warning",
    }
    for name, sev in expected.items():
        assert by_name[name]["labels"]["severity"] == sev


def test_revocations_link_labels_canonical():
    by_name = {r["alert"]: r for r in _all_rules()}
    expected = {
        "SelfdefRevocationsTextfileEmitFailed":     "observer-fault",
        "SelfdefRevocationsObserverSilent":         "observer-silent",
        "SelfdefRevocationsStateDirMissing":        "state-dir-missing",
        "SelfdefRevocationsPendingRestoreBacklog":  "pending-backlog",
        "SelfdefRevocationsActiveHigh":             "active-high",
    }
    for name, link in expected.items():
        assert by_name[name]["labels"].get("revocations_link") == link


def test_state_dir_missing_description_cites_enforcement_offline():
    by_name = {r["alert"]: r for r in _all_rules()}
    desc = by_name["SelfdefRevocationsStateDirMissing"]["annotations"]["description"]
    assert "enforcement" in desc.lower() or "OFFLINE" in desc


def test_rule_group_interval_30s():
    doc = yaml.safe_load(RULES_PATH.read_text())
    g = next(g for g in doc["groups"] if g["name"] == "selfdef-revocations")
    assert g["interval"] == "30s"


def test_rules_cite_sdd_067_anchor():
    assert "SDD-067" in RULES_PATH.read_text()


def test_rules_cite_selfdef_producer_commit():
    assert "6f3f19d" in RULES_PATH.read_text()


def test_every_alert_carries_runbook_url():
    for r in _all_rules():
        url = r["annotations"].get("runbook_url", "")
        assert "m060-deployment-guide.md#" in url
