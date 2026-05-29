"""Selfdef sshd-config hardening alerts — contract test."""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = (
    REPO_ROOT / "config" / "prometheus" / "alerts"
    / "selfdef-sshd-config.rules.yml"
)

REQUIRED_ALERTS = {
    "SelfdefSshdConfigTextfileEmitFailed",
    "SelfdefSshdConfigObserverSilent",
    "SelfdefSshdPermitRootLoginEnabled",
    "SelfdefSshdPermitEmptyPasswords",
    "SelfdefSshdPasswordAuthEnabled",
    "SelfdefSshdConfigHashDrift",
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
        assert r["labels"]["subsystem"] == "selfdef-sshd-config"
        assert r["labels"]["severity"] in ("warning", "critical")


def test_observer_silent_threshold_300s():
    by_name = {r["alert"]: r for r in _all_rules()}
    assert "> 300" in by_name["SelfdefSshdConfigObserverSilent"]["expr"]


def test_permit_root_login_alert_uses_canonical_gauge():
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefSshdPermitRootLoginEnabled"]["expr"]
    assert "selfdef_sshd_permit_root_login" in expr
    assert "== 1" in expr


def test_permit_empty_passwords_alert_uses_canonical_gauge():
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefSshdPermitEmptyPasswords"]["expr"]
    assert "selfdef_sshd_permit_empty_passwords" in expr


def test_hash_drift_alert_uses_changes_1h():
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefSshdConfigHashDrift"]["expr"]
    assert "changes(" in expr
    assert "selfdef_sshd_config_hash" in expr
    assert "[1h])" in expr


def test_severity_classification():
    by_name = {r["alert"]: r for r in _all_rules()}
    expected = {
        "SelfdefSshdConfigTextfileEmitFailed":  "critical",
        "SelfdefSshdConfigObserverSilent":      "critical",
        "SelfdefSshdPermitRootLoginEnabled":    "critical",
        "SelfdefSshdPermitEmptyPasswords":      "critical",
        "SelfdefSshdPasswordAuthEnabled":       "warning",
        "SelfdefSshdConfigHashDrift":           "warning",
    }
    for name, sev in expected.items():
        assert by_name[name]["labels"]["severity"] == sev


def test_sshd_link_labels_canonical():
    by_name = {r["alert"]: r for r in _all_rules()}
    expected = {
        "SelfdefSshdConfigTextfileEmitFailed":  "observer-fault",
        "SelfdefSshdConfigObserverSilent":      "observer-silent",
        "SelfdefSshdPermitRootLoginEnabled":    "permit-root",
        "SelfdefSshdPermitEmptyPasswords":      "empty-passwords",
        "SelfdefSshdPasswordAuthEnabled":       "password-auth",
        "SelfdefSshdConfigHashDrift":           "hash-drift",
    }
    for name, link in expected.items():
        assert by_name[name]["labels"].get("sshd_link") == link


def test_permit_root_login_description_cites_auth_events_pairing():
    by_name = {r["alert"]: r for r in _all_rules()}
    desc = by_name["SelfdefSshdPermitRootLoginEnabled"]["annotations"]["description"]
    assert "auth-events" in desc or "fail2ban" in desc


def test_rule_group_interval_30s():
    doc = yaml.safe_load(RULES_PATH.read_text())
    g = next(g for g in doc["groups"] if g["name"] == "selfdef-sshd-config")
    assert g["interval"] == "30s"


def test_rules_cite_selfdef_producer_commit():
    assert "c86e4e4" in RULES_PATH.read_text()


def test_every_alert_carries_runbook_url():
    for r in _all_rules():
        url = r["annotations"].get("runbook_url", "")
        assert "m060-deployment-guide.md#" in url
