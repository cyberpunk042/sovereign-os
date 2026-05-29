"""Selfdef auth-events cross-surface threshold-lockstep lint."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
ALERTS_PATH = (
    REPO_ROOT / "config" / "prometheus" / "alerts"
    / "selfdef-auth-events.rules.yml"
)
GUIDE_PATH = REPO_ROOT / "docs" / "operator" / "m060-deployment-guide.md"

CANONICAL_GAUGES = {
    "selfdef_auth_events_login_failures",
    "selfdef_auth_events_ssh_invalid_users",
    "selfdef_auth_events_sudo_invocations",
    "selfdef_auth_events_textfile_emit_failed",
}


def _alert_rules():
    doc = yaml.safe_load(ALERTS_PATH.read_text())
    return [r for g in doc["groups"] for r in g["rules"]]


def test_observer_silent_300s_in_alert():
    by_name = {r["alert"]: r for r in _alert_rules()}
    assert "> 300" in by_name["SelfdefAuthEventsObserverSilent"]["expr"]


def test_brute_force_threshold_20():
    by_name = {r["alert"]: r for r in _alert_rules()}
    assert "> 20" in by_name["SelfdefAuthEventsBruteForceDetected"]["expr"]


def test_ssh_invalid_threshold_5():
    by_name = {r["alert"]: r for r in _alert_rules()}
    assert "> 5" in by_name["SelfdefAuthEventsSshInvalidUserAttempts"]["expr"]


def test_sudo_spike_threshold_10():
    by_name = {r["alert"]: r for r in _alert_rules()}
    assert "> 10" in by_name["SelfdefAuthEventsSudoSpike"]["expr"]


def test_alert_severities_match_runbook_headings():
    by_name = {r["alert"]: r for r in _alert_rules()}
    guide = GUIDE_PATH.read_text()
    expected = {
        "SelfdefAuthEventsTextfileEmitFailed":     "(critical)",
        "SelfdefAuthEventsObserverSilent":         "(critical)",
        "SelfdefAuthEventsBruteForceDetected":     "(critical)",
        "SelfdefAuthEventsSshInvalidUserAttempts": "(warning)",
        "SelfdefAuthEventsSudoSpike":              "(warning)",
    }
    for name, suffix in expected.items():
        heading = f"#### {name} {suffix}"
        assert heading in guide, f"missing {heading!r}"
        sev = "critical" if suffix == "(critical)" else "warning"
        assert by_name[name]["labels"]["severity"] == sev


def test_brute_force_runbook_includes_attacking_ip_pipeline():
    """Brute-force runbook MUST include the awk pipeline for
    extracting attacking source IPs from journalctl — operator-
    actionable forensic command."""
    guide = GUIDE_PATH.read_text()
    start = guide.find("#### SelfdefAuthEventsBruteForceDetected")
    next_h = guide.find("\n#### ", start + 1)
    section = guide[start:next_h if next_h > 0 else len(guide)]
    assert "awk" in section


def test_partner_repo_wrapper_carries_canonical_gauges():
    partner_env = os.environ.get("SELFDEF_REPO_ROOT")
    if not partner_env:
        return
    wrapper_path = (
        Path(partner_env) / "packaging" / "scripts"
        / "selfdef-auth-events-textfile.sh"
    )
    if not wrapper_path.is_file():
        return
    body = wrapper_path.read_text()
    for gauge in CANONICAL_GAUGES:
        assert gauge in body


def test_partner_repo_timer_60s():
    partner_env = os.environ.get("SELFDEF_REPO_ROOT")
    if not partner_env:
        return
    timer_path = (
        Path(partner_env) / "packaging" / "systemd"
        / "selfdef-auth-events-textfile.timer"
    )
    if not timer_path.is_file():
        return
    assert "OnUnitActiveSec=60s" in timer_path.read_text()
