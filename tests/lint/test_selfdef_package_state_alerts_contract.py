"""Selfdef apt/dpkg package-state alerts — contract test."""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = (
    REPO_ROOT / "config" / "prometheus" / "alerts"
    / "selfdef-package-state.rules.yml"
)

REQUIRED_ALERTS = {
    "SelfdefPackageStateTextfileEmitFailed",
    "SelfdefPackageStateObserverSilent",
    "SelfdefAptSecurityUpdatesPending",
    "SelfdefDpkgBrokenPackages",
    "SelfdefAptUpdateStale",
    "SelfdefAptPendingBacklog",
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
        assert r["labels"]["subsystem"] == "selfdef-package-state"
        assert r["labels"]["severity"] in ("warning", "critical")


def test_observer_silent_threshold_300s():
    by_name = {r["alert"]: r for r in _all_rules()}
    assert "> 300" in by_name["SelfdefPackageStateObserverSilent"]["expr"]


def test_security_pending_alert_uses_canonical_gauge():
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefAptSecurityUpdatesPending"]["expr"]
    assert "selfdef_apt_pending_security" in expr
    assert "> 0" in expr


def test_security_pending_for_window_1h():
    """1h grace window — gives the operator a chance to apply patches
    within a maintenance cadence rather than paging every minute."""
    by_name = {r["alert"]: r for r in _all_rules()}
    assert by_name["SelfdefAptSecurityUpdatesPending"]["for"] == "1h"


def test_apt_update_stale_threshold_7_days():
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefAptUpdateStale"]["expr"]
    assert "selfdef_apt_update_age_days" in expr
    assert "> 7" in expr


def test_pending_backlog_threshold_50():
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefAptPendingBacklog"]["expr"]
    assert "selfdef_apt_pending_total" in expr
    assert "> 50" in expr


def test_severity_classification():
    by_name = {r["alert"]: r for r in _all_rules()}
    expected = {
        "SelfdefPackageStateTextfileEmitFailed": "critical",
        "SelfdefPackageStateObserverSilent":     "critical",
        "SelfdefAptSecurityUpdatesPending":      "critical",
        "SelfdefDpkgBrokenPackages":             "critical",
        "SelfdefAptUpdateStale":                 "warning",
        "SelfdefAptPendingBacklog":              "warning",
    }
    for name, sev in expected.items():
        assert by_name[name]["labels"]["severity"] == sev


def test_package_link_labels_canonical():
    by_name = {r["alert"]: r for r in _all_rules()}
    expected = {
        "SelfdefPackageStateTextfileEmitFailed": "observer-fault",
        "SelfdefPackageStateObserverSilent":     "observer-silent",
        "SelfdefAptSecurityUpdatesPending":      "cve-pending",
        "SelfdefDpkgBrokenPackages":             "dpkg-broken",
        "SelfdefAptUpdateStale":                 "apt-stale",
        "SelfdefAptPendingBacklog":              "pending-backlog",
    }
    for name, link in expected.items():
        assert by_name[name]["labels"].get("package_link") == link


def test_rule_group_interval_30s():
    doc = yaml.safe_load(RULES_PATH.read_text())
    g = next(g for g in doc["groups"] if g["name"] == "selfdef-package-state")
    assert g["interval"] == "30s"


def test_rules_cite_selfdef_producer_commit():
    assert "0d05972" in RULES_PATH.read_text()


def test_every_alert_carries_runbook_url():
    for r in _all_rules():
        url = r["annotations"].get("runbook_url", "")
        assert "m060-deployment-guide.md#" in url
