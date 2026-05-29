"""Selfdef nftables alerts — contract test."""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = (
    REPO_ROOT / "config" / "prometheus" / "alerts"
    / "selfdef-nftables.rules.yml"
)

REQUIRED_ALERTS = {
    "SelfdefNftablesTextfileEmitFailed",
    "SelfdefNftablesObserverSilent",
    "SelfdefNftablesRulesetEmpty",
    "SelfdefConntrackTableNearFull",
    "SelfdefConntrackTableHigh",
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
        assert r["labels"]["subsystem"] == "selfdef-nftables"
        assert r["labels"]["severity"] in ("warning", "critical")


def test_observer_silent_threshold_300s():
    by_name = {r["alert"]: r for r in _all_rules()}
    assert "> 300" in by_name["SelfdefNftablesObserverSilent"]["expr"]


def test_ruleset_empty_alert_guards_on_present():
    """RulesetEmpty MUST require present == 1, otherwise it'd fire
    on hosts that legitimately don't install nft (honest-offline)."""
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefNftablesRulesetEmpty"]["expr"]
    assert "selfdef_nftables_present == 1" in expr
    assert "selfdef_nftables_rules_total == 0" in expr


def test_conntrack_near_full_threshold_90():
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefConntrackTableNearFull"]["expr"]
    assert "selfdef_conntrack_used_percent" in expr
    assert "> 90" in expr


def test_conntrack_high_threshold_75():
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefConntrackTableHigh"]["expr"]
    assert "selfdef_conntrack_used_percent" in expr
    assert "> 75" in expr


def test_severity_classification():
    by_name = {r["alert"]: r for r in _all_rules()}
    expected = {
        "SelfdefNftablesTextfileEmitFailed": "critical",
        "SelfdefNftablesObserverSilent":     "critical",
        "SelfdefNftablesRulesetEmpty":       "critical",
        "SelfdefConntrackTableNearFull":     "critical",
        "SelfdefConntrackTableHigh":         "warning",
    }
    for name, sev in expected.items():
        assert by_name[name]["labels"]["severity"] == sev


def test_nftables_link_labels_canonical():
    by_name = {r["alert"]: r for r in _all_rules()}
    expected = {
        "SelfdefNftablesTextfileEmitFailed": "observer-fault",
        "SelfdefNftablesObserverSilent":     "observer-silent",
        "SelfdefNftablesRulesetEmpty":       "ruleset-empty",
        "SelfdefConntrackTableNearFull":     "conntrack-full",
        "SelfdefConntrackTableHigh":         "conntrack-high",
    }
    for name, link in expected.items():
        assert by_name[name]["labels"].get("nftables_link") == link


def test_ruleset_empty_description_cites_fail2ban_pairing():
    by_name = {r["alert"]: r for r in _all_rules()}
    desc = by_name["SelfdefNftablesRulesetEmpty"]["annotations"]["description"]
    assert "fail2ban" in desc or "ban" in desc.lower()


def test_rule_group_interval_30s():
    doc = yaml.safe_load(RULES_PATH.read_text())
    g = next(g for g in doc["groups"] if g["name"] == "selfdef-nftables")
    assert g["interval"] == "30s"


def test_rules_cite_selfdef_producer_commit():
    assert "2c303c4" in RULES_PATH.read_text()


def test_every_alert_carries_runbook_url():
    for r in _all_rules():
        url = r["annotations"].get("runbook_url", "")
        assert "m060-deployment-guide.md#" in url
