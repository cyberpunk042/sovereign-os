"""Selfdef auth-events alerts — contract test."""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = (
    REPO_ROOT / "config" / "prometheus" / "alerts"
    / "selfdef-auth-events.rules.yml"
)

REQUIRED_ALERTS = {
    "SelfdefAuthEventsTextfileEmitFailed",
    "SelfdefAuthEventsObserverSilent",
    "SelfdefAuthEventsBruteForceDetected",
    "SelfdefAuthEventsSshInvalidUserAttempts",
    "SelfdefAuthEventsSudoSpike",
}


def _all_rules():
    doc = yaml.safe_load(RULES_PATH.read_text())
    return [r for g in doc["groups"] for r in g["rules"]]


def test_rules_file_present_and_valid_yaml():
    assert RULES_PATH.is_file()


def test_all_required_alerts_present():
    names = {r["alert"] for r in _all_rules()}
    missing = REQUIRED_ALERTS - names
    assert not missing


def test_every_alert_carries_full_envelope():
    for r in _all_rules():
        for f in ("alert", "expr", "for", "labels", "annotations"):
            assert f in r
        assert r["labels"]["subsystem"] == "selfdef-auth-events"
        assert r["labels"]["severity"] in ("warning", "critical")
        for ann in ("summary", "description", "runbook_url"):
            assert ann in r["annotations"]


def test_observer_silent_threshold_300s():
    by_name = {r["alert"]: r for r in _all_rules()}
    assert "> 300" in by_name["SelfdefAuthEventsObserverSilent"]["expr"]


def test_emit_failed_references_sentinel():
    by_name = {r["alert"]: r for r in _all_rules()}
    assert "selfdef_auth_events_textfile_emit_failed" in by_name[
        "SelfdefAuthEventsTextfileEmitFailed"
    ]["expr"]


def test_brute_force_threshold_20():
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefAuthEventsBruteForceDetected"]["expr"]
    assert "> 20" in expr
    assert "selfdef_auth_events_login_failures" in expr


def test_ssh_invalid_user_threshold_5():
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefAuthEventsSshInvalidUserAttempts"]["expr"]
    assert "> 5" in expr
    assert "selfdef_auth_events_ssh_invalid_users" in expr


def test_sudo_spike_threshold_10():
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefAuthEventsSudoSpike"]["expr"]
    assert "> 10" in expr
    assert "selfdef_auth_events_sudo_invocations" in expr


def test_observer_fault_paths_critical():
    by_name = {r["alert"]: r for r in _all_rules()}
    for name in (
        "SelfdefAuthEventsTextfileEmitFailed",
        "SelfdefAuthEventsObserverSilent",
        "SelfdefAuthEventsBruteForceDetected",
    ):
        assert by_name[name]["labels"]["severity"] == "critical"


def test_auth_link_labels_canonical():
    by_name = {r["alert"]: r for r in _all_rules()}
    expected = {
        "SelfdefAuthEventsTextfileEmitFailed":     "observer-fault",
        "SelfdefAuthEventsObserverSilent":         "observer-silent",
        "SelfdefAuthEventsBruteForceDetected":     "brute-force",
        "SelfdefAuthEventsSshInvalidUserAttempts": "ssh-recon",
        "SelfdefAuthEventsSudoSpike":              "sudo-spike",
    }
    for name, link in expected.items():
        assert by_name[name]["labels"].get("auth_link") == link


def test_brute_force_description_includes_fail2ban():
    """Brute-force alert description MUST mention fail2ban OR
    nftables — actionable Fix routing for operators."""
    by_name = {r["alert"]: r for r in _all_rules()}
    desc = by_name["SelfdefAuthEventsBruteForceDetected"]["annotations"]["description"]
    assert "fail2ban" in desc or "nftables" in desc


def test_rule_group_interval_30s():
    doc = yaml.safe_load(RULES_PATH.read_text())
    g = next(g for g in doc["groups"] if g["name"] == "selfdef-auth-events")
    assert g["interval"] == "30s"


def test_rules_cite_selfdef_producer_commit():
    assert "e73dc61" in RULES_PATH.read_text()
