"""Selfdef SDD-065 blockset alerts — contract test."""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = (
    REPO_ROOT / "config" / "prometheus" / "alerts"
    / "selfdef-blockset.rules.yml"
)

REQUIRED_ALERTS = {
    "SelfdefBlocksetTextfileEmitFailed",
    "SelfdefBlocksetObserverSilent",
    "SelfdefBlocksetTableMissing",
    "SelfdefBlocksetTotalHigh",
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
        assert r["labels"]["subsystem"] == "selfdef-blockset"
        assert r["labels"]["severity"] in ("warning", "critical")


def test_observer_silent_threshold_300s():
    by_name = {r["alert"]: r for r in _all_rules()}
    assert "> 300" in by_name["SelfdefBlocksetObserverSilent"]["expr"]


def test_table_missing_uses_present_eq_zero():
    """Table-missing alert uses selfdef_blockset_present == 0 (NOT
    `<= 0` — we want exact zero, present is binary)."""
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefBlocksetTableMissing"]["expr"]
    assert "selfdef_blockset_present == 0" in expr


def test_table_missing_for_window_10m():
    """10m grace gives selfdefd time to start + bootstrap before paging."""
    by_name = {r["alert"]: r for r in _all_rules()}
    assert by_name["SelfdefBlocksetTableMissing"]["for"] == "10m"


def test_total_high_threshold_1000():
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefBlocksetTotalHigh"]["expr"]
    assert "selfdef_blockset_total_count" in expr
    assert "> 1000" in expr


def test_severity_classification():
    by_name = {r["alert"]: r for r in _all_rules()}
    expected = {
        "SelfdefBlocksetTextfileEmitFailed": "critical",
        "SelfdefBlocksetObserverSilent":     "critical",
        "SelfdefBlocksetTableMissing":       "critical",
        "SelfdefBlocksetTotalHigh":          "warning",
    }
    for name, sev in expected.items():
        assert by_name[name]["labels"]["severity"] == sev


def test_blockset_link_labels_canonical():
    by_name = {r["alert"]: r for r in _all_rules()}
    expected = {
        "SelfdefBlocksetTextfileEmitFailed": "observer-fault",
        "SelfdefBlocksetObserverSilent":     "observer-silent",
        "SelfdefBlocksetTableMissing":       "table-missing",
        "SelfdefBlocksetTotalHigh":          "total-high",
    }
    for name, link in expected.items():
        assert by_name[name]["labels"].get("blockset_link") == link


def test_table_missing_description_cites_enforcement_offline():
    by_name = {r["alert"]: r for r in _all_rules()}
    desc = by_name["SelfdefBlocksetTableMissing"]["annotations"]["description"]
    assert "enforcement" in desc.lower() or "OFFLINE" in desc


def test_rule_group_interval_30s():
    doc = yaml.safe_load(RULES_PATH.read_text())
    g = next(g for g in doc["groups"] if g["name"] == "selfdef-blockset")
    assert g["interval"] == "30s"


def test_rules_cite_sdd_065_anchor():
    assert "SDD-065" in RULES_PATH.read_text()


def test_rules_cite_selfdef_producer_commit():
    assert "39e091f" in RULES_PATH.read_text()


def test_every_alert_carries_runbook_url():
    for r in _all_rules():
        url = r["annotations"].get("runbook_url", "")
        assert "m060-deployment-guide.md#" in url
