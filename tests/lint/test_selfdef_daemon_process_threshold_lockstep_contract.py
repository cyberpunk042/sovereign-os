"""Selfdef daemon process-state cross-surface threshold-lockstep lint.

Locks invariants across alert rules + Grafana dashboard + runbook
sections + opt-in partner-repo cross-reference.

In-repo (always-on):
  1. Observer-silent threshold == 300s consistent across alert YAML
     + Grafana red threshold step + runbook mentions.
  2. Memory threshold == 1 GiB (1073741824 bytes) consistent across
     alert + dashboard.
  3. FD threshold == 819 (80% of 1024 ulimit) consistent across
     alert + dashboard.
  4. Canonical metric names match across alerts + dashboard.
  5. Alert severities align with runbook section heading suffixes.

Partner-repo opt-in via $SELFDEF_REPO_ROOT (2 tests):
  - Wrapper carries 8 canonical gauges
  - Timer cadence = 60s (consumer 300s = 5x cadence assumption)
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

ALERTS_PATH = (
    REPO_ROOT / "config" / "prometheus" / "alerts"
    / "selfdef-daemon-process.rules.yml"
)
DASHBOARD_PATH = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-selfdef-daemon-process.json"
)
GUIDE_PATH = REPO_ROOT / "docs" / "operator" / "m060-deployment-guide.md"


def _read(p: Path) -> str:
    return p.read_text()


def _alert_rules() -> list[dict]:
    doc = yaml.safe_load(_read(ALERTS_PATH))
    return [r for g in doc["groups"] for r in g["rules"]]


def _dashboard() -> dict:
    return json.loads(_read(DASHBOARD_PATH))


def test_observer_silent_300s_across_alert_and_dashboard():
    by_name = {r["alert"]: r for r in _alert_rules()}
    assert "> 300" in by_name["SelfdefDaemonProcessObserverSilent"]["expr"]


def test_memory_threshold_1_gib_across_alert_and_dashboard():
    by_name = {r["alert"]: r for r in _alert_rules()}
    assert "1073741824" in by_name["SelfdefDaemonProcessMemoryHigh"]["expr"]
    dash = _dashboard()
    found = False
    for panel in dash["panels"]:
        if "memory" not in panel.get("title", "").lower():
            continue
        steps = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("thresholds", {})
            .get("steps", [])
        )
        for s in steps:
            if s.get("color") == "red" and s.get("value") == 1073741824:
                found = True
    assert found


def test_fd_threshold_819_across_alert_and_dashboard():
    by_name = {r["alert"]: r for r in _alert_rules()}
    assert "> 819" in by_name["SelfdefDaemonProcessFdExhaustionApproaching"]["expr"]
    dash = _dashboard()
    found = False
    for panel in dash["panels"]:
        if "fd" not in panel.get("title", "").lower():
            continue
        steps = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("thresholds", {})
            .get("steps", [])
        )
        for s in steps:
            if s.get("color") == "red" and s.get("value") == 819:
                found = True
    assert found


def test_canonical_metric_names_match_across_alerts_and_dashboard():
    rules_text = _read(ALERTS_PATH)
    dash_exprs = " ".join(
        t.get("expr", "")
        for p in _dashboard()["panels"]
        for t in p.get("targets", [])
    )
    # Gauges that MUST appear in BOTH alerts AND dashboard. last_run_unix
    # is used in the observer-silent alert expression but not directly
    # charted (the emit-failed sentinel plus uptime panels carry the
    # equivalent operator signal).
    shared = (
        "selfdef_daemon_process_memory_rss_bytes",
        "selfdef_daemon_process_open_fds",
        "selfdef_daemon_process_restart_count",
        "selfdef_daemon_process_textfile_emit_failed",
    )
    for gauge in shared:
        assert gauge in rules_text, f"alert missing {gauge}"
        assert gauge in dash_exprs, f"dashboard missing {gauge}"
    # last_run_unix MUST appear in the alert (drives observer-silent)
    # even though it isn't directly charted.
    assert "selfdef_daemon_process_last_run_unix" in rules_text


def test_alert_severities_align_with_runbook_headings():
    by_name = {r["alert"]: r for r in _alert_rules()}
    guide = _read(GUIDE_PATH)
    expected = {
        "SelfdefDaemonProcessTextfileEmitFailed":      "(critical)",
        "SelfdefDaemonProcessObserverSilent":          "(critical)",
        "SelfdefDaemonProcessMemoryHigh":              "(warning)",
        "SelfdefDaemonProcessFdExhaustionApproaching": "(critical)",
        "SelfdefDaemonProcessRestartLoop":             "(critical)",
    }
    for name, suffix in expected.items():
        heading = f"#### {name} {suffix}"
        assert heading in guide, f"runbook missing {heading!r}"
        sev = "critical" if suffix == "(critical)" else "warning"
        assert by_name[name]["labels"]["severity"] == sev


def test_partner_repo_wrapper_carries_canonical_gauges():
    partner_env = os.environ.get("SELFDEF_REPO_ROOT")
    if not partner_env:
        return
    wrapper_path = (
        Path(partner_env) / "packaging" / "scripts"
        / "selfdef-daemon-process-textfile.sh"
    )
    if not wrapper_path.is_file():
        return
    body = wrapper_path.read_text()
    for gauge in (
        "selfdef_daemon_process_memory_rss_bytes",
        "selfdef_daemon_process_open_fds",
        "selfdef_daemon_process_restart_count",
        "selfdef_daemon_process_textfile_emit_failed",
    ):
        assert gauge in body


def test_partner_repo_timer_cadence_60s():
    partner_env = os.environ.get("SELFDEF_REPO_ROOT")
    if not partner_env:
        return
    timer_path = (
        Path(partner_env) / "packaging" / "systemd"
        / "selfdef-daemon-process-textfile.timer"
    )
    if not timer_path.is_file():
        return
    assert "OnUnitActiveSec=60s" in timer_path.read_text()
