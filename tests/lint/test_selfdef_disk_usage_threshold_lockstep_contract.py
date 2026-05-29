"""Selfdef disk-usage cross-surface threshold-lockstep lint."""
from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
ALERTS_PATH = (
    REPO_ROOT / "config" / "prometheus" / "alerts" / "selfdef-disk-usage.rules.yml"
)
DASHBOARD_PATH = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-selfdef-disk-usage.json"
)
GUIDE_PATH = REPO_ROOT / "docs" / "operator" / "m060-deployment-guide.md"

CANONICAL_GAUGES = {
    "selfdef_disk_usage_lib_bytes",
    "selfdef_disk_usage_log_bytes",
    "selfdef_disk_usage_var_used_percent",
    "selfdef_disk_usage_textfile_emit_failed",
}


def _alert_rules():
    doc = yaml.safe_load(ALERTS_PATH.read_text())
    return [r for g in doc["groups"] for r in g["rules"]]


def _dashboard():
    return json.loads(DASHBOARD_PATH.read_text())


def test_observer_silent_300s():
    by_name = {r["alert"]: r for r in _alert_rules()}
    assert "> 300" in by_name["SelfdefDiskUsageObserverSilent"]["expr"]


def test_var_used_90_threshold_across_alert_and_dashboard():
    by_name = {r["alert"]: r for r in _alert_rules()}
    assert "> 90" in by_name["SelfdefDiskUsageVarHigh"]["expr"]
    dash = _dashboard()
    found = False
    for panel in dash["panels"]:
        if "used %" not in panel.get("title", "").lower():
            continue
        steps = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("thresholds", {})
            .get("steps", [])
        )
        for s in steps:
            if s.get("color") == "red" and s.get("value") == 90:
                found = True
    assert found


def test_var_used_75_threshold_across_alert_and_dashboard():
    by_name = {r["alert"]: r for r in _alert_rules()}
    assert "> 75" in by_name["SelfdefDiskUsageVarApproaching"]["expr"]
    dash = _dashboard()
    found = False
    for panel in dash["panels"]:
        if "used %" not in panel.get("title", "").lower():
            continue
        steps = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("thresholds", {})
            .get("steps", [])
        )
        for s in steps:
            if s.get("color") == "yellow" and s.get("value") == 75:
                found = True
    assert found


def test_selfdef_log_threshold_5_gib_across_alert_and_dashboard():
    """5 GiB = 5368709120 bytes — exact match required."""
    by_name = {r["alert"]: r for r in _alert_rules()}
    assert "5368709120" in by_name["SelfdefDiskUsageSelfdefLogHigh"]["expr"]
    dash = _dashboard()
    found = False
    for panel in dash["panels"]:
        title = panel.get("title", "").lower()
        if "log" not in title:
            continue
        steps = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("thresholds", {})
            .get("steps", [])
        )
        for s in steps:
            if s.get("color") == "yellow" and s.get("value") == 5368709120:
                found = True
    assert found


def test_canonical_metric_names_across_alerts_and_dashboard():
    rules_text = ALERTS_PATH.read_text()
    dash_exprs = " ".join(
        t.get("expr", "")
        for p in _dashboard()["panels"]
        for t in p.get("targets", [])
    )
    for gauge in CANONICAL_GAUGES:
        assert gauge in rules_text, f"alert missing {gauge}"
        assert gauge in dash_exprs, f"dashboard missing {gauge}"


def test_alert_severities_align_with_runbook_headings():
    by_name = {r["alert"]: r for r in _alert_rules()}
    guide = GUIDE_PATH.read_text()
    expected = {
        "SelfdefDiskUsageTextfileEmitFailed": "(critical)",
        "SelfdefDiskUsageObserverSilent":     "(critical)",
        "SelfdefDiskUsageVarHigh":            "(critical)",
        "SelfdefDiskUsageVarApproaching":     "(warning)",
        "SelfdefDiskUsageSelfdefLogHigh":     "(warning)",
    }
    for name, suffix in expected.items():
        heading = f"#### {name} {suffix}"
        assert heading in guide, f"missing {heading!r}"
        sev = "critical" if suffix == "(critical)" else "warning"
        assert by_name[name]["labels"]["severity"] == sev


def test_partner_repo_wrapper_carries_canonical_gauges():
    partner_env = os.environ.get("SELFDEF_REPO_ROOT")
    if not partner_env:
        return
    wrapper_path = (
        Path(partner_env) / "packaging" / "scripts"
        / "selfdef-disk-usage-textfile.sh"
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
        / "selfdef-disk-usage-textfile.timer"
    )
    if not timer_path.is_file():
        return
    assert "OnUnitActiveSec=60s" in timer_path.read_text()
