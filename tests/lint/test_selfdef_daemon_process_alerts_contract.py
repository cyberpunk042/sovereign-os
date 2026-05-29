"""Selfdef daemon process-state Prometheus alert rules — contract test.

Locks the alert surface for the selfdef-side
`selfdef_daemon_process_*` textfile gauges shipped by
selfdef-daemon-process-textfile.{service,timer} (selfdef commit
`09822c1`).
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = (
    REPO_ROOT / "config" / "prometheus" / "alerts"
    / "selfdef-daemon-process.rules.yml"
)

REQUIRED_ALERTS = {
    "SelfdefDaemonProcessTextfileEmitFailed",
    "SelfdefDaemonProcessObserverSilent",
    "SelfdefDaemonProcessMemoryHigh",
    "SelfdefDaemonProcessFdExhaustionApproaching",
    "SelfdefDaemonProcessRestartLoop",
}


def _load_rules() -> dict:
    return yaml.safe_load(RULES_PATH.read_text())


def _all_rules() -> list[dict]:
    doc = _load_rules()
    return [r for g in doc["groups"] for r in g["rules"]]


def test_rules_file_present_and_valid_yaml():
    assert RULES_PATH.is_file()
    doc = _load_rules()
    assert any(g["name"] == "selfdef-daemon-process" for g in doc["groups"])


def test_all_required_alerts_present():
    names = {r["alert"] for r in _all_rules()}
    missing = REQUIRED_ALERTS - names
    assert not missing, f"missing required alerts: {sorted(missing)}"


def test_every_alert_carries_required_fields():
    for rule in _all_rules():
        for field in ("alert", "expr", "for", "labels", "annotations"):
            assert field in rule, (
                f"alert {rule.get('alert')!r} missing field {field!r}"
            )
        labels = rule["labels"]
        assert labels.get("subsystem") == "selfdef-daemon-process"
        assert labels.get("severity") in ("warning", "critical")
        for ann in ("summary", "description", "runbook_url"):
            assert ann in rule["annotations"]


def test_observer_silent_threshold_locked_at_300s():
    """Locked across all 4 observability verticals (M060, four-watchdog,
    modules-catalog, daemon-process) via cross-surface lockstep."""
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefDaemonProcessObserverSilent"]["expr"]
    assert "> 300" in expr
    assert "selfdef_daemon_process_last_run_unix" in expr


def test_emit_failed_references_sentinel_gauge():
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefDaemonProcessTextfileEmitFailed"]["expr"]
    assert "selfdef_daemon_process_textfile_emit_failed" in expr


def test_observer_fault_paths_are_critical():
    by_name = {r["alert"]: r for r in _all_rules()}
    for name in (
        "SelfdefDaemonProcessTextfileEmitFailed",
        "SelfdefDaemonProcessObserverSilent",
    ):
        assert by_name[name]["labels"]["severity"] == "critical"


def test_memory_high_threshold_is_1_gib():
    """1 GiB threshold = 1073741824 bytes — generous floor for
    selfdefd's defensive-daemon footprint."""
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefDaemonProcessMemoryHigh"]["expr"]
    assert "1073741824" in expr, (
        f"memory threshold must be 1 GiB (1073741824 bytes); got {expr!r}"
    )


def test_fd_exhaustion_at_80_percent_of_default_ulimit():
    """819 = 80% of default Linux 1024 ulimit. Operators raising
    ulimit drop a recording-rule override."""
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefDaemonProcessFdExhaustionApproaching"]["expr"]
    assert "> 819" in expr


def test_restart_loop_uses_increase_function():
    """Restart count is monotonic counter — use increase() over
    a 10m window to detect crashlooping."""
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefDaemonProcessRestartLoop"]["expr"]
    assert "increase(" in expr
    assert "10m" in expr
    assert ">= 3" in expr


def test_process_link_labels_canonical():
    by_name = {r["alert"]: r for r in _all_rules()}
    expected = {
        "SelfdefDaemonProcessTextfileEmitFailed":      "observer-fault",
        "SelfdefDaemonProcessObserverSilent":          "observer-silent",
        "SelfdefDaemonProcessMemoryHigh":              "rollup",
        "SelfdefDaemonProcessFdExhaustionApproaching": "rollup",
        "SelfdefDaemonProcessRestartLoop":             "rollup",
    }
    for name, link in expected.items():
        assert by_name[name]["labels"].get("process_link") == link


def test_rule_group_interval_30s():
    doc = _load_rules()
    g = next(g for g in doc["groups"] if g["name"] == "selfdef-daemon-process")
    assert g["interval"] == "30s"


def test_rules_file_cites_selfdef_producer_commit():
    assert "09822c1" in RULES_PATH.read_text()
