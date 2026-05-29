"""Selfdef kernel-modules alerts — contract test."""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = (
    REPO_ROOT / "config" / "prometheus" / "alerts"
    / "selfdef-kernel-modules.rules.yml"
)

REQUIRED_ALERTS = {
    "SelfdefKernelModulesTextfileEmitFailed",
    "SelfdefKernelModulesObserverSilent",
    "SelfdefKernelTaintedUnsigned",
    "SelfdefKernelTaintedAny",
    "SelfdefKernelModulesCountHigh",
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
        assert r["labels"]["subsystem"] == "selfdef-kernel-modules"
        assert r["labels"]["severity"] in ("warning", "critical")


def test_observer_silent_threshold_300s():
    by_name = {r["alert"]: r for r in _all_rules()}
    assert "> 300" in by_name["SelfdefKernelModulesObserverSilent"]["expr"]


def test_unsigned_alert_targets_canonical_gauge():
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefKernelTaintedUnsigned"]["expr"]
    assert "selfdef_kernel_tainted_unsigned" in expr
    assert "== 1" in expr


def test_any_tainted_alert_uses_greater_than_zero():
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefKernelTaintedAny"]["expr"]
    assert "selfdef_kernel_tainted" in expr
    assert "> 0" in expr


def test_count_high_threshold_200():
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefKernelModulesCountHigh"]["expr"]
    assert "> 200" in expr


def test_severity_classification():
    by_name = {r["alert"]: r for r in _all_rules()}
    expected = {
        "SelfdefKernelModulesTextfileEmitFailed": "critical",
        "SelfdefKernelModulesObserverSilent":     "critical",
        "SelfdefKernelTaintedUnsigned":           "critical",
        "SelfdefKernelTaintedAny":                "warning",
        "SelfdefKernelModulesCountHigh":          "warning",
    }
    for name, sev in expected.items():
        assert by_name[name]["labels"]["severity"] == sev


def test_kernel_link_labels_canonical():
    by_name = {r["alert"]: r for r in _all_rules()}
    expected = {
        "SelfdefKernelModulesTextfileEmitFailed": "observer-fault",
        "SelfdefKernelModulesObserverSilent":     "observer-silent",
        "SelfdefKernelTaintedUnsigned":           "rollup",
        "SelfdefKernelTaintedAny":                "rollup",
        "SelfdefKernelModulesCountHigh":          "rollup",
    }
    for name, link in expected.items():
        assert by_name[name]["labels"].get("kernel_link") == link


def test_unsigned_alert_includes_dmesg_diagnostic():
    """The unsigned alert MUST include dmesg + lsmod diagnostic
    commands — actionable rootkit triage."""
    by_name = {r["alert"]: r for r in _all_rules()}
    desc = by_name["SelfdefKernelTaintedUnsigned"]["annotations"]["description"]
    assert "dmesg" in desc and "lsmod" in desc


def test_unsigned_for_window_short():
    """The unsigned alert MUST page quickly (≤ 1m for) — rootkits
    are time-sensitive."""
    by_name = {r["alert"]: r for r in _all_rules()}
    assert by_name["SelfdefKernelTaintedUnsigned"]["for"] == "1m"


def test_rule_group_interval_30s():
    doc = yaml.safe_load(RULES_PATH.read_text())
    g = next(g for g in doc["groups"] if g["name"] == "selfdef-kernel-modules")
    assert g["interval"] == "30s"


def test_rules_cite_selfdef_producer_commit():
    assert "78a9e29" in RULES_PATH.read_text()
