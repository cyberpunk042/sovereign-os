"""Cross-vertical observability rollup recording rules — contract test.

Locks the structural shape of
`config/prometheus/rules/sovereign-os-observability-rollup.yml` —
the recording rules that pre-compute aggregate health across the 5
observability verticals shipped this milestone (M060, MS022,
four-watchdog, modules-catalog, daemon-process).

Same drift-protection pattern as the per-vertical alert contract
tests — locks recording-rule names + alert names + threshold
constants + canonical metric references.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = (
    REPO_ROOT / "config" / "prometheus" / "rules"
    / "sovereign-os-observability-rollup.yml"
)

REQUIRED_RECORDS = {
    "sovereign_os:observer_fault_any",
    "sovereign_os:critical_state_any",
    "sovereign_os:warn_state_any",
    "sovereign_os:textfile_observers_healthy_count",
}

REQUIRED_ALERTS = {
    "SovereignObservabilityAnyObserverFault",
    "SovereignObservabilityObserverCountBelowMax",
    "SovereignObservabilityAnyCritical",
}


def _load() -> dict:
    return yaml.safe_load(RULES_PATH.read_text())


def _all_rules() -> list[dict]:
    doc = _load()
    return [r for g in doc["groups"] for r in g["rules"]]


def test_rules_file_present_and_valid_yaml():
    assert RULES_PATH.is_file(), f"missing rules file: {RULES_PATH}"
    doc = _load()
    assert "groups" in doc
    names = {g["name"] for g in doc["groups"]}
    assert "sovereign-os-observability-rollup" in names
    assert "sovereign-os-observability-rollup-alerts" in names


def test_all_required_records_present():
    """Recording rules MUST exist for all 4 canonical rollups."""
    records = {r.get("record") for r in _all_rules() if r.get("record")}
    missing = REQUIRED_RECORDS - records
    assert not missing, (
        f"missing recording rules: {sorted(missing)}"
    )


def test_all_required_alerts_present():
    """Cross-vertical alerts MUST exist."""
    alerts = {r.get("alert") for r in _all_rules() if r.get("alert")}
    missing = REQUIRED_ALERTS - alerts
    assert not missing, f"missing alerts: {sorted(missing)}"


def test_record_names_use_canonical_namespace():
    """All recording rules MUST use the `sovereign_os:` namespace
    prefix per Prometheus naming conventions. Drift to a different
    prefix would break operator dashboards that grep on it."""
    records = [r.get("record") for r in _all_rules() if r.get("record")]
    for name in records:
        assert name.startswith("sovereign_os:"), (
            f"record {name!r} must use sovereign_os: namespace prefix"
        )


def test_observer_fault_record_references_all_3_textfile_observers():
    """The observer_fault_any record MUST reference all 3 selfdef-
    side textfile observers (four-watchdog, modules, daemon-process)."""
    record = next(
        r for r in _all_rules()
        if r.get("record") == "sovereign_os:observer_fault_any"
    )
    expr = record["expr"]
    assert "four_watchdog" in expr
    assert "modules" in expr
    assert "daemon_process" in expr


def test_critical_state_record_references_canonical_thresholds():
    """The critical_state_any record MUST reference the canonical
    thresholds: 1 GiB memory, 819 FDs, 100 modules floor, severity
    >= 2 for four-watchdog. Drift = the rollup fires at different
    points than per-vertical alerts."""
    record = next(
        r for r in _all_rules()
        if r.get("record") == "sovereign_os:critical_state_any"
    )
    expr = record["expr"]
    assert "1073741824" in expr, "memory 1 GiB threshold drift"
    assert "819" in expr, "FD 819 threshold drift"
    assert "< 100" in expr, "modules CountLow threshold drift"
    assert ">= 2" in expr, "four-watchdog severity >= 2 drift"
    assert ">= 1.0" in expr, "MS022 saturated threshold drift"


def test_warn_state_record_references_canonical_thresholds():
    """The warn_state_any record references warning-tier thresholds."""
    record = next(
        r for r in _all_rules()
        if r.get("record") == "sovereign_os:warn_state_any"
    )
    expr = record["expr"]
    assert "== 1" in expr, "four-watchdog WARN drift"
    assert "0.85" in expr, "MS022 approaching threshold drift"


def test_observer_healthy_count_is_3():
    """healthy_count MUST sum across the 3 selfdef-side textfile
    observers — max value is 3 when all are healthy."""
    record = next(
        r for r in _all_rules()
        if r.get("record") == "sovereign_os:textfile_observers_healthy_count"
    )
    expr = record["expr"]
    # 3 distinct observer references.
    assert expr.count("four_watchdog") >= 2  # both emit_failed + last_run_unix
    assert expr.count("modules") >= 2
    assert expr.count("daemon_process") >= 2


def test_every_alert_carries_full_envelope():
    for rule in _all_rules():
        if "alert" not in rule:
            continue
        for field in ("alert", "expr", "for", "labels", "annotations"):
            assert field in rule, (
                f"alert {rule.get('alert')!r} missing field {field!r}"
            )
        labels = rule["labels"]
        assert labels.get("subsystem") == "observability-rollup"
        assert labels.get("severity") in ("warning", "critical")
        for ann in ("summary", "description", "runbook_url"):
            assert ann in rule["annotations"]


def test_observer_count_alert_threshold_3():
    """ObserverCountBelowMax MUST target < 3 (the healthy ceiling)."""
    rule = next(
        r for r in _all_rules()
        if r.get("alert") == "SovereignObservabilityObserverCountBelowMax"
    )
    assert "< 3" in rule["expr"]


def test_observer_fault_alert_references_recording_rule():
    """The cross-vertical observer-fault alert MUST reference the
    recording rule — drift catches breaking the rollup-vs-alert link."""
    rule = next(
        r for r in _all_rules()
        if r.get("alert") == "SovereignObservabilityAnyObserverFault"
    )
    assert "sovereign_os:observer_fault_any" in rule["expr"]


def test_critical_alert_references_recording_rule():
    rule = next(
        r for r in _all_rules()
        if r.get("alert") == "SovereignObservabilityAnyCritical"
    )
    assert "sovereign_os:critical_state_any" in rule["expr"]


def test_rule_groups_evaluate_at_30s():
    doc = _load()
    for g in doc["groups"]:
        assert g["interval"] == "30s", (
            f"group {g['name']!r} interval drift: {g['interval']!r}"
        )


def test_rollup_link_labels_canonical():
    by_name = {r["alert"]: r for r in _all_rules() if r.get("alert")}
    expected = {
        "SovereignObservabilityAnyObserverFault":     "observer-fault-any",
        "SovereignObservabilityObserverCountBelowMax": "observer-count",
        "SovereignObservabilityAnyCritical":          "critical-any",
    }
    for name, link in expected.items():
        assert by_name[name]["labels"].get("rollup_link") == link, (
            f"alert {name!r} rollup_link drift"
        )
