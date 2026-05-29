"""Selfdef listening-sockets cross-surface threshold-lockstep lint."""
from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
ALERTS_PATH = (
    REPO_ROOT / "config" / "prometheus" / "alerts"
    / "selfdef-listening-sockets.rules.yml"
)
DASHBOARD_PATH = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-selfdef-listening-sockets.json"
)
GUIDE_PATH = REPO_ROOT / "docs" / "operator" / "m060-deployment-guide.md"

CANONICAL_GAUGES = {
    "selfdef_listening_sockets_tcp",
    "selfdef_listening_sockets_tcp6",
    "selfdef_listening_sockets_total",
    "selfdef_listening_sockets_textfile_emit_failed",
}


def _alert_rules():
    doc = yaml.safe_load(ALERTS_PATH.read_text())
    return [r for g in doc["groups"] for r in g["rules"]]


def _dashboard():
    return json.loads(DASHBOARD_PATH.read_text())


def test_observer_silent_300s():
    by_name = {r["alert"]: r for r in _alert_rules()}
    assert "> 300" in by_name["SelfdefListeningSocketsObserverSilent"]["expr"]


def test_tcp_high_threshold_20_across_alert_and_dashboard():
    by_name = {r["alert"]: r for r in _alert_rules()}
    assert "> 20" in by_name["SelfdefListeningSocketsTcpCountHigh"]["expr"]
    dash = _dashboard()
    found = False
    for panel in dash["panels"]:
        if "total" not in panel.get("title", "").lower():
            continue
        steps = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("thresholds", {})
            .get("steps", [])
        )
        for s in steps:
            if s.get("color") == "red" and s.get("value") == 20:
                found = True
    assert found


def test_zero_tcp_threshold_1_across_alert_and_dashboard():
    by_name = {r["alert"]: r for r in _alert_rules()}
    assert "< 1" in by_name["SelfdefListeningSocketsZeroTcp"]["expr"]
    dash = _dashboard()
    found = False
    for panel in dash["panels"]:
        title = panel.get("title", "").lower()
        if "tcp" not in title or "udp" in title:
            continue
        steps = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("thresholds", {})
            .get("steps", [])
        )
        for s in steps:
            if s.get("color") == "red" and s.get("value") == 0:
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
        "SelfdefListeningSocketsTextfileEmitFailed": "(critical)",
        "SelfdefListeningSocketsObserverSilent":     "(critical)",
        "SelfdefListeningSocketsTcpCountHigh":       "(warning)",
        "SelfdefListeningSocketsZeroTcp":            "(critical)",
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
        / "selfdef-listening-sockets-textfile.sh"
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
        / "selfdef-listening-sockets-textfile.timer"
    )
    if not timer_path.is_file():
        return
    assert "OnUnitActiveSec=60s" in timer_path.read_text()
