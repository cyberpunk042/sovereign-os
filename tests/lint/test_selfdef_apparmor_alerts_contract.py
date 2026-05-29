"""Selfdef AppArmor profile-enforcement alerts — contract test."""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = (
    REPO_ROOT / "config" / "prometheus" / "alerts"
    / "selfdef-apparmor.rules.yml"
)

REQUIRED_ALERTS = {
    "SelfdefApparmorTextfileEmitFailed",
    "SelfdefApparmorObserverSilent",
    "SelfdefApparmorProfileNotLoaded",
    "SelfdefApparmorProfileInComplainMode",
}


def _all_rules():
    doc = yaml.safe_load(RULES_PATH.read_text())
    return [r for g in doc["groups"] for r in g["rules"]]


def test_rules_file_present_and_valid_yaml():
    assert RULES_PATH.is_file()
    doc = yaml.safe_load(RULES_PATH.read_text())
    assert any(g["name"] == "selfdef-apparmor" for g in doc["groups"])


def test_all_required_alerts_present():
    names = {r["alert"] for r in _all_rules()}
    missing = REQUIRED_ALERTS - names
    assert not missing


def test_every_alert_carries_full_envelope():
    for r in _all_rules():
        for f in ("alert", "expr", "for", "labels", "annotations"):
            assert f in r
        assert r["labels"]["subsystem"] == "selfdef-apparmor"
        assert r["labels"]["severity"] in ("warning", "critical")
        for ann in ("summary", "description", "runbook_url"):
            assert ann in r["annotations"]


def test_observer_silent_threshold_300s():
    by_name = {r["alert"]: r for r in _all_rules()}
    assert "> 300" in by_name["SelfdefApparmorObserverSilent"]["expr"]


def test_emit_failed_references_sentinel():
    by_name = {r["alert"]: r for r in _all_rules()}
    assert "selfdef_apparmor_textfile_emit_failed" in by_name[
        "SelfdefApparmorTextfileEmitFailed"
    ]["expr"]


def test_profile_not_loaded_targets_canonical_profile():
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefApparmorProfileNotLoaded"]["expr"]
    assert "/usr/bin/selfdefd" in expr
    assert "== 0" in expr


def test_complain_mode_targets_canonical_profile():
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefApparmorProfileInComplainMode"]["expr"]
    assert "/usr/bin/selfdefd" in expr
    assert "== 1" in expr
    assert "selfdef_apparmor_profile_complain" in expr


def test_all_alerts_classified_critical():
    """All 4 alerts in this family are critical — AppArmor drift is
    page-worthy because it silently weakens the IPS spine."""
    for r in _all_rules():
        assert r["labels"]["severity"] == "critical"


def test_apparmor_link_labels_canonical():
    by_name = {r["alert"]: r for r in _all_rules()}
    expected = {
        "SelfdefApparmorTextfileEmitFailed": "observer-fault",
        "SelfdefApparmorObserverSilent":     "observer-silent",
        "SelfdefApparmorProfileNotLoaded":   "rollup",
        "SelfdefApparmorProfileInComplainMode": "rollup",
    }
    for name, link in expected.items():
        assert by_name[name]["labels"].get("apparmor_link") == link


def test_rule_group_interval_30s():
    doc = yaml.safe_load(RULES_PATH.read_text())
    g = next(g for g in doc["groups"] if g["name"] == "selfdef-apparmor")
    assert g["interval"] == "30s"


def test_complain_mode_alert_documents_restore_command():
    """The complain-mode alert MUST tell operators how to restore
    enforce mode. Drift = page without an actionable Fix."""
    by_name = {r["alert"]: r for r in _all_rules()}
    desc = by_name["SelfdefApparmorProfileInComplainMode"]["annotations"]["description"]
    assert "aa-enforce" in desc, (
        "complain-mode alert description must include aa-enforce command"
    )


def test_rules_cite_selfdef_producer_commit():
    assert "4680ed8" in RULES_PATH.read_text()


def test_runbook_sections_present_for_every_alert():
    guide_path = REPO_ROOT / "docs" / "operator" / "m060-deployment-guide.md"
    body = guide_path.read_text()
    for name in REQUIRED_ALERTS:
        anchor = f"#### {name}"
        assert anchor in body, f"missing runbook section {anchor!r}"


def test_runbook_sections_include_diagnosis_and_fix():
    guide_path = REPO_ROOT / "docs" / "operator" / "m060-deployment-guide.md"
    body = guide_path.read_text()
    for name in REQUIRED_ALERTS:
        start = body.find(f"#### {name}")
        next_h = body.find("\n#### ", start + 1)
        next_h2 = body.find("\n## ", start + 1)
        candidates = [x for x in (next_h, next_h2) if x > 0]
        end = min(candidates) if candidates else len(body)
        section = body[start:end]
        assert "**Diagnosis:**" in section, f"{name} missing **Diagnosis:**"
        assert "**Fix:**" in section, f"{name} missing **Fix:**"
        assert "```" in section
