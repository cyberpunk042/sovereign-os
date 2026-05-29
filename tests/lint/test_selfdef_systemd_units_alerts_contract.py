"""Selfdef systemd-units-health alerts — contract test."""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = (
    REPO_ROOT / "config" / "prometheus" / "alerts"
    / "selfdef-systemd-units.rules.yml"
)

REQUIRED_ALERTS = {
    "SelfdefSystemdUnitsTextfileEmitFailed",
    "SelfdefSystemdUnitsObserverSilent",
    "SelfdefSystemdUnitFailed",
    "SelfdefSystemdUnitsCountLow",
}


def _all_rules():
    doc = yaml.safe_load(RULES_PATH.read_text())
    return [r for g in doc["groups"] for r in g["rules"]]


def test_rules_file_present_and_valid_yaml():
    assert RULES_PATH.is_file()


def test_all_required_alerts_present():
    names = {r["alert"] for r in _all_rules()}
    missing = REQUIRED_ALERTS - names
    assert not missing, f"missing: {sorted(missing)}"


def test_every_alert_carries_full_envelope():
    for r in _all_rules():
        for f in ("alert", "expr", "for", "labels", "annotations"):
            assert f in r
        assert r["labels"]["subsystem"] == "selfdef-systemd-units"
        assert r["labels"]["severity"] in ("warning", "critical")
        for ann in ("summary", "description", "runbook_url"):
            assert ann in r["annotations"]


def test_observer_silent_threshold_300s():
    by_name = {r["alert"]: r for r in _all_rules()}
    assert "> 300" in by_name["SelfdefSystemdUnitsObserverSilent"]["expr"]


def test_emit_failed_references_sentinel():
    by_name = {r["alert"]: r for r in _all_rules()}
    assert "selfdef_systemd_units_textfile_emit_failed" in by_name[
        "SelfdefSystemdUnitsTextfileEmitFailed"
    ]["expr"]


def test_unit_failed_targets_failed_gauge():
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefSystemdUnitFailed"]["expr"]
    assert "> 0" in expr
    assert "selfdef_systemd_units_failed" in expr


def test_count_low_threshold_8():
    """Count-low threshold MUST be 8 — generous floor below selfdef's
    10+ shipped units."""
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefSystemdUnitsCountLow"]["expr"]
    assert "< 8" in expr


def test_observer_fault_and_unit_failed_critical():
    by_name = {r["alert"]: r for r in _all_rules()}
    for name in (
        "SelfdefSystemdUnitsTextfileEmitFailed",
        "SelfdefSystemdUnitsObserverSilent",
        "SelfdefSystemdUnitFailed",
    ):
        assert by_name[name]["labels"]["severity"] == "critical"


def test_count_low_warning():
    by_name = {r["alert"]: r for r in _all_rules()}
    assert by_name["SelfdefSystemdUnitsCountLow"]["labels"]["severity"] == "warning"


def test_systemd_link_labels_canonical():
    by_name = {r["alert"]: r for r in _all_rules()}
    expected = {
        "SelfdefSystemdUnitsTextfileEmitFailed": "observer-fault",
        "SelfdefSystemdUnitsObserverSilent":     "observer-silent",
        "SelfdefSystemdUnitFailed":              "rollup",
        "SelfdefSystemdUnitsCountLow":           "rollup",
    }
    for name, link in expected.items():
        assert by_name[name]["labels"].get("systemd_link") == link


def test_unit_failed_description_includes_diagnostic_commands():
    """The UnitFailed alert description MUST include the systemctl
    --failed + journalctl diagnostic commands — actionable Fix."""
    by_name = {r["alert"]: r for r in _all_rules()}
    desc = by_name["SelfdefSystemdUnitFailed"]["annotations"]["description"]
    assert "systemctl --failed" in desc or "systemctl --failed --all" in desc
    assert "journalctl" in desc


def test_rule_group_interval_30s():
    doc = yaml.safe_load(RULES_PATH.read_text())
    g = next(g for g in doc["groups"] if g["name"] == "selfdef-systemd-units")
    assert g["interval"] == "30s"


def test_rules_cite_selfdef_producer_commit():
    assert "7121c72" in RULES_PATH.read_text()


def test_runbook_sections_present_for_every_alert():
    guide = REPO_ROOT / "docs" / "operator" / "m060-deployment-guide.md"
    body = guide.read_text()
    for name in REQUIRED_ALERTS:
        assert f"#### {name}" in body


def test_unit_failed_runbook_includes_systemctl_failed_command():
    guide = REPO_ROOT / "docs" / "operator" / "m060-deployment-guide.md"
    body = guide.read_text()
    start = body.find("#### SelfdefSystemdUnitFailed")
    next_h = body.find("\n#### ", start + 1)
    section = body[start:next_h if next_h > 0 else len(body)]
    assert "systemctl --failed" in section
