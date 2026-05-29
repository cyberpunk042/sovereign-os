"""Selfdef SDD-066 quarantine alerts — contract test."""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = (
    REPO_ROOT / "config" / "prometheus" / "alerts"
    / "selfdef-quarantine.rules.yml"
)

REQUIRED_ALERTS = {
    "SelfdefQuarantineTextfileEmitFailed",
    "SelfdefQuarantineObserverSilent",
    "SelfdefQuarantineSliceMissing",
    "SelfdefQuarantineActiveHigh",
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
        assert r["labels"]["subsystem"] == "selfdef-quarantine"
        assert r["labels"]["severity"] in ("warning", "critical")


def test_observer_silent_threshold_300s():
    by_name = {r["alert"]: r for r in _all_rules()}
    assert "> 300" in by_name["SelfdefQuarantineObserverSilent"]["expr"]


def test_slice_missing_uses_present_eq_zero():
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefQuarantineSliceMissing"]["expr"]
    assert "selfdef_quarantine_slice_present == 0" in expr


def test_slice_missing_for_window_10m():
    """10m grace gives selfdefd time to start + bootstrap before paging."""
    by_name = {r["alert"]: r for r in _all_rules()}
    assert by_name["SelfdefQuarantineSliceMissing"]["for"] == "10m"


def test_active_high_threshold_10():
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefQuarantineActiveHigh"]["expr"]
    assert "selfdef_quarantine_active_count" in expr
    assert "> 10" in expr


def test_severity_classification():
    by_name = {r["alert"]: r for r in _all_rules()}
    expected = {
        "SelfdefQuarantineTextfileEmitFailed": "critical",
        "SelfdefQuarantineObserverSilent":     "critical",
        "SelfdefQuarantineSliceMissing":       "critical",
        "SelfdefQuarantineActiveHigh":         "warning",
    }
    for name, sev in expected.items():
        assert by_name[name]["labels"]["severity"] == sev


def test_quarantine_link_labels_canonical():
    by_name = {r["alert"]: r for r in _all_rules()}
    expected = {
        "SelfdefQuarantineTextfileEmitFailed": "observer-fault",
        "SelfdefQuarantineObserverSilent":     "observer-silent",
        "SelfdefQuarantineSliceMissing":       "slice-missing",
        "SelfdefQuarantineActiveHigh":         "active-high",
    }
    for name, link in expected.items():
        assert by_name[name]["labels"].get("quarantine_link") == link


def test_slice_missing_description_cites_enforcement_offline():
    by_name = {r["alert"]: r for r in _all_rules()}
    desc = by_name["SelfdefQuarantineSliceMissing"]["annotations"]["description"]
    assert "enforcement" in desc.lower() or "OFFLINE" in desc


def test_rule_group_interval_30s():
    doc = yaml.safe_load(RULES_PATH.read_text())
    g = next(g for g in doc["groups"] if g["name"] == "selfdef-quarantine")
    assert g["interval"] == "30s"


def test_rules_cite_sdd_066_anchor():
    assert "SDD-066" in RULES_PATH.read_text()


def test_rules_cite_selfdef_producer_commit():
    assert "55a3c33" in RULES_PATH.read_text()


def test_every_alert_carries_runbook_url():
    for r in _all_rules():
        url = r["annotations"].get("runbook_url", "")
        assert "m060-deployment-guide.md#" in url
