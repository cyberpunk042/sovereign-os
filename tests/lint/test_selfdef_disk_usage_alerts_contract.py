"""Selfdef disk-usage alerts — contract test."""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = (
    REPO_ROOT / "config" / "prometheus" / "alerts"
    / "selfdef-disk-usage.rules.yml"
)

REQUIRED_ALERTS = {
    "SelfdefDiskUsageTextfileEmitFailed",
    "SelfdefDiskUsageObserverSilent",
    "SelfdefDiskUsageVarHigh",
    "SelfdefDiskUsageVarApproaching",
    "SelfdefDiskUsageSelfdefLogHigh",
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
        assert r["labels"]["subsystem"] == "selfdef-disk-usage"
        assert r["labels"]["severity"] in ("warning", "critical")


def test_observer_silent_threshold_300s():
    by_name = {r["alert"]: r for r in _all_rules()}
    assert "> 300" in by_name["SelfdefDiskUsageObserverSilent"]["expr"]


def test_var_high_threshold_90():
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefDiskUsageVarHigh"]["expr"]
    assert "> 90" in expr
    assert "selfdef_disk_usage_var_used_percent" in expr


def test_var_approaching_threshold_75():
    by_name = {r["alert"]: r for r in _all_rules()}
    assert "> 75" in by_name["SelfdefDiskUsageVarApproaching"]["expr"]


def test_selfdef_log_threshold_5_gib():
    """5 GiB = 5368709120 bytes."""
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefDiskUsageSelfdefLogHigh"]["expr"]
    assert "5368709120" in expr


def test_severity_classification():
    by_name = {r["alert"]: r for r in _all_rules()}
    expected = {
        "SelfdefDiskUsageTextfileEmitFailed": "critical",
        "SelfdefDiskUsageObserverSilent":     "critical",
        "SelfdefDiskUsageVarHigh":            "critical",
        "SelfdefDiskUsageVarApproaching":     "warning",
        "SelfdefDiskUsageSelfdefLogHigh":     "warning",
    }
    for name, sev in expected.items():
        assert by_name[name]["labels"]["severity"] == sev


def test_disk_link_labels_canonical():
    by_name = {r["alert"]: r for r in _all_rules()}
    expected = {
        "SelfdefDiskUsageTextfileEmitFailed": "observer-fault",
        "SelfdefDiskUsageObserverSilent":     "observer-silent",
        "SelfdefDiskUsageVarHigh":            "rollup",
        "SelfdefDiskUsageVarApproaching":     "rollup",
        "SelfdefDiskUsageSelfdefLogHigh":     "rollup",
    }
    for name, link in expected.items():
        assert by_name[name]["labels"].get("disk_link") == link


def test_var_high_description_includes_du_command():
    """VarHigh description MUST include du -sh diagnostic for
    operators to identify the largest subtrees."""
    by_name = {r["alert"]: r for r in _all_rules()}
    desc = by_name["SelfdefDiskUsageVarHigh"]["annotations"]["description"]
    assert "du -sh" in desc


def test_selfdef_log_description_routes_to_logrotate():
    by_name = {r["alert"]: r for r in _all_rules()}
    desc = by_name["SelfdefDiskUsageSelfdefLogHigh"]["annotations"]["description"]
    assert "logrotate" in desc


def test_rule_group_interval_30s():
    doc = yaml.safe_load(RULES_PATH.read_text())
    g = next(g for g in doc["groups"] if g["name"] == "selfdef-disk-usage")
    assert g["interval"] == "30s"


def test_rules_cite_selfdef_producer_commit():
    assert "694b611" in RULES_PATH.read_text()
