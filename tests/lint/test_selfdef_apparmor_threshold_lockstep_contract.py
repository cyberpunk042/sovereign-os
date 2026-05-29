"""Selfdef AppArmor cross-surface threshold-lockstep lint.

Locks invariants across alert rules + Grafana dashboard + runbook
sections + opt-in partner-repo cross-reference.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

ALERTS_PATH = (
    REPO_ROOT / "config" / "prometheus" / "alerts" / "selfdef-apparmor.rules.yml"
)
DASHBOARD_PATH = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-selfdef-apparmor.json"
)
GUIDE_PATH = REPO_ROOT / "docs" / "operator" / "m060-deployment-guide.md"

CANONICAL_PROFILE = "/usr/bin/selfdefd"
CANONICAL_GAUGES = {
    "selfdef_apparmor_profile_loaded",
    "selfdef_apparmor_profile_enforce",
    "selfdef_apparmor_profile_complain",
    "selfdef_apparmor_profiles_loaded_total",
    "selfdef_apparmor_textfile_emit_failed",
}


def _alert_rules():
    doc = yaml.safe_load(ALERTS_PATH.read_text())
    return [r for g in doc["groups"] for r in g["rules"]]


def _dashboard():
    return json.loads(DASHBOARD_PATH.read_text())


def test_observer_silent_300s_across_alert_and_runbook():
    by_name = {r["alert"]: r for r in _alert_rules()}
    assert "> 300" in by_name["SelfdefApparmorObserverSilent"]["expr"]
    guide = GUIDE_PATH.read_text()
    start = guide.find("#### SelfdefApparmorObserverSilent")
    next_h = guide.find("\n#### ", start + 1)
    section = guide[start:next_h if next_h > 0 else len(guide)]
    assert "300" in section or "5+ minutes" in section


def test_canonical_profile_name_across_alert_and_dashboard():
    """Both surfaces MUST reference the canonical profile path —
    drift = alert fires on one profile, dashboard renders another."""
    alerts_text = ALERTS_PATH.read_text()
    dash_exprs = " ".join(
        t.get("expr", "")
        for p in _dashboard()["panels"]
        for t in p.get("targets", [])
    )
    assert CANONICAL_PROFILE in alerts_text
    assert CANONICAL_PROFILE in dash_exprs


def test_canonical_metric_names_match_across_alerts_and_dashboard():
    rules_text = ALERTS_PATH.read_text()
    dash_exprs = " ".join(
        t.get("expr", "")
        for p in _dashboard()["panels"]
        for t in p.get("targets", [])
    )
    for gauge in CANONICAL_GAUGES:
        assert gauge in rules_text, f"alert missing {gauge}"
        assert gauge in dash_exprs, f"dashboard missing {gauge}"


def test_complain_mode_alert_severity_matches_runbook():
    """ComplainMode is critical in alert + runbook heading. Drift
    catches if either side accidentally demotes to warning."""
    by_name = {r["alert"]: r for r in _alert_rules()}
    assert by_name["SelfdefApparmorProfileInComplainMode"]["labels"]["severity"] == "critical"
    guide = GUIDE_PATH.read_text()
    assert "#### SelfdefApparmorProfileInComplainMode (critical)" in guide


def test_aa_enforce_command_documented_in_both_alert_and_runbook():
    """The aa-enforce restore command MUST appear in the alert
    description AND in the runbook Fix block — operators looking at
    either surface see the same actionable command."""
    by_name = {r["alert"]: r for r in _alert_rules()}
    alert_desc = by_name["SelfdefApparmorProfileInComplainMode"]["annotations"]["description"]
    assert "aa-enforce" in alert_desc
    guide = GUIDE_PATH.read_text()
    start = guide.find("#### SelfdefApparmorProfileInComplainMode")
    next_h = guide.find("\n#### ", start + 1)
    section = guide[start:next_h if next_h > 0 else len(guide)]
    assert "aa-enforce" in section


def test_partner_repo_wrapper_carries_canonical_gauges():
    partner_env = os.environ.get("SELFDEF_REPO_ROOT")
    if not partner_env:
        return
    wrapper_path = (
        Path(partner_env) / "packaging" / "scripts"
        / "selfdef-apparmor-textfile.sh"
    )
    if not wrapper_path.is_file():
        return
    body = wrapper_path.read_text()
    for gauge in CANONICAL_GAUGES:
        assert gauge in body


def test_partner_repo_timer_cadence_60s():
    partner_env = os.environ.get("SELFDEF_REPO_ROOT")
    if not partner_env:
        return
    timer_path = (
        Path(partner_env) / "packaging" / "systemd"
        / "selfdef-apparmor-textfile.timer"
    )
    if not timer_path.is_file():
        return
    assert "OnUnitActiveSec=60s" in timer_path.read_text()
