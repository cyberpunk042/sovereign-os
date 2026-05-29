"""Selfdef time-sync cross-surface threshold-lockstep lint."""
from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
ALERTS_PATH = (
    REPO_ROOT / "config" / "prometheus" / "alerts" / "selfdef-time-sync.rules.yml"
)
DASHBOARD_PATH = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-selfdef-time-sync.json"
)
GUIDE_PATH = REPO_ROOT / "docs" / "operator" / "m060-deployment-guide.md"

CANONICAL_GAUGES = {
    "selfdef_time_sync_synced",
    "selfdef_time_sync_ntp_active",
    "selfdef_time_sync_drift_seconds",
    "selfdef_time_sync_textfile_emit_failed",
}


def _alert_rules():
    doc = yaml.safe_load(ALERTS_PATH.read_text())
    return [r for g in doc["groups"] for r in g["rules"]]


def _dashboard():
    return json.loads(DASHBOARD_PATH.read_text())


def test_observer_silent_300s():
    by_name = {r["alert"]: r for r in _alert_rules()}
    assert "> 300" in by_name["SelfdefTimeSyncObserverSilent"]["expr"]


def test_drift_60s_threshold_across_alert_and_dashboard():
    by_name = {r["alert"]: r for r in _alert_rules()}
    assert "> 60" in by_name["SelfdefTimeSyncDriftHigh"]["expr"]
    dash = _dashboard()
    found = False
    for panel in dash["panels"]:
        if "drift" not in panel.get("title", "").lower():
            continue
        steps = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("thresholds", {})
            .get("steps", [])
        )
        for s in steps:
            if s.get("color") == "yellow" and s.get("value") == 60:
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
        "SelfdefTimeSyncTextfileEmitFailed": "(critical)",
        "SelfdefTimeSyncObserverSilent":     "(critical)",
        "SelfdefTimeSyncNotSynced":          "(critical)",
        "SelfdefTimeSyncNtpInactive":        "(critical)",
        "SelfdefTimeSyncDriftHigh":          "(warning)",
        "SelfdefTimeSyncRtcLocalTz":         "(warning)",
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
        / "selfdef-time-sync-textfile.sh"
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
        / "selfdef-time-sync-textfile.timer"
    )
    if not timer_path.is_file():
        return
    assert "OnUnitActiveSec=60s" in timer_path.read_text()
