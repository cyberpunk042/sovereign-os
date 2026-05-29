"""Selfdef fail2ban alerts — contract test."""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = (
    REPO_ROOT / "config" / "prometheus" / "alerts"
    / "selfdef-fail2ban.rules.yml"
)

REQUIRED_ALERTS = {
    "SelfdefFail2banTextfileEmitFailed",
    "SelfdefFail2banObserverSilent",
    "SelfdefFail2banServerDown",
    "SelfdefFail2banZeroJails",
    "SelfdefFail2banActiveBanSpike",
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
        assert r["labels"]["subsystem"] == "selfdef-fail2ban"
        assert r["labels"]["severity"] in ("warning", "critical")


def test_observer_silent_threshold_300s():
    by_name = {r["alert"]: r for r in _all_rules()}
    assert "> 300" in by_name["SelfdefFail2banObserverSilent"]["expr"]


def test_server_down_alert_uses_alive_zero():
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefFail2banServerDown"]["expr"]
    assert "selfdef_fail2ban_server_alive" in expr
    assert "== 0" in expr


def test_server_down_does_NOT_fire_on_minus_one():
    """server_alive=-1 is honest-offline (fail2ban-client uninstalled)
    — must NOT fire SelfdefFail2banServerDown. The expr `== 0` ensures
    -1 is excluded."""
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefFail2banServerDown"]["expr"]
    # Specifically check we use == 0 not <= 0, which would catch -1.
    assert "<= 0" not in expr
    assert "< 1" not in expr


def test_zero_jails_alert_guards_on_alive():
    """ZeroJails MUST require server_alive == 1 — otherwise a down
    server with no jails would double-fire on top of ServerDown."""
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefFail2banZeroJails"]["expr"]
    assert "selfdef_fail2ban_server_alive == 1" in expr
    assert "selfdef_fail2ban_jails_active == 0" in expr


def test_active_ban_spike_threshold_50():
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefFail2banActiveBanSpike"]["expr"]
    assert "selfdef_fail2ban_current_bans_sum" in expr
    assert "> 50" in expr


def test_severity_classification():
    by_name = {r["alert"]: r for r in _all_rules()}
    expected = {
        "SelfdefFail2banTextfileEmitFailed": "critical",
        "SelfdefFail2banObserverSilent":     "critical",
        "SelfdefFail2banServerDown":         "critical",
        "SelfdefFail2banZeroJails":          "warning",
        "SelfdefFail2banActiveBanSpike":     "warning",
    }
    for name, sev in expected.items():
        assert by_name[name]["labels"]["severity"] == sev


def test_fail2ban_link_labels_canonical():
    by_name = {r["alert"]: r for r in _all_rules()}
    expected = {
        "SelfdefFail2banTextfileEmitFailed": "observer-fault",
        "SelfdefFail2banObserverSilent":     "observer-silent",
        "SelfdefFail2banServerDown":         "daemon-down",
        "SelfdefFail2banZeroJails":          "zero-jails",
        "SelfdefFail2banActiveBanSpike":     "active-ban-spike",
    }
    for name, link in expected.items():
        assert by_name[name]["labels"].get("fail2ban_link") == link


def test_server_down_description_cites_auth_events_pairing():
    """SelfdefFail2banServerDown description MUST explain the
    attack-surface — auth-events records attacks that won't be
    mitigated when fail2ban is down."""
    by_name = {r["alert"]: r for r in _all_rules()}
    desc = by_name["SelfdefFail2banServerDown"]["annotations"]["description"]
    assert "auth-events" in desc or "brute-force" in desc.lower()


def test_server_down_for_window_short():
    """ServerDown MUST page quickly (≤ 2m for) — defensive-tier
    outage is time-sensitive."""
    by_name = {r["alert"]: r for r in _all_rules()}
    assert by_name["SelfdefFail2banServerDown"]["for"] == "2m"


def test_rule_group_interval_30s():
    doc = yaml.safe_load(RULES_PATH.read_text())
    g = next(g for g in doc["groups"] if g["name"] == "selfdef-fail2ban")
    assert g["interval"] == "30s"


def test_rules_cite_selfdef_producer_commit():
    assert "098a45a" in RULES_PATH.read_text()


def test_every_alert_carries_runbook_url():
    for r in _all_rules():
        url = r["annotations"].get("runbook_url", "")
        assert "m060-deployment-guide.md#" in url
