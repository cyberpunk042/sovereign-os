"""Selfdef module-catalog Prometheus alert rules — contract test.

Locks the alert surface for the selfdef-side
`selfdef_modules_*` textfile gauges shipped by
selfdef-modules-textfile.{service,timer} (selfdef commit
`1ce88c7`). Same drift-protection shape as the four-watchdog
alerts contract — every alert references the correct gauge,
severity classification matches semantics, each alert carries
the required envelope fields, runbook sections exist.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = (
    REPO_ROOT / "config" / "prometheus" / "alerts"
    / "selfdef-modules-catalog.rules.yml"
)

REQUIRED_ALERTS = {
    "SelfdefModulesTextfileEmitFailed",
    "SelfdefModulesObserverSilent",
    "SelfdefModulesCountLow",
}


def _load_rules() -> dict:
    return yaml.safe_load(RULES_PATH.read_text())


def _all_rules() -> list[dict]:
    doc = _load_rules()
    return [r for g in doc["groups"] for r in g["rules"]]


def test_rules_file_present_and_valid_yaml():
    assert RULES_PATH.is_file()
    doc = _load_rules()
    assert "groups" in doc
    assert any(g["name"] == "selfdef-modules-catalog" for g in doc["groups"])


def test_all_required_alerts_present():
    names = {r["alert"] for r in _all_rules()}
    missing = REQUIRED_ALERTS - names
    assert not missing, f"missing required alerts: {sorted(missing)}"


def test_every_alert_carries_required_fields():
    for rule in _all_rules():
        for field in ("alert", "expr", "for", "labels", "annotations"):
            assert field in rule, (
                f"alert {rule.get('alert')!r} missing required field {field!r}"
            )
        labels = rule["labels"]
        assert labels.get("subsystem") == "selfdef-modules-catalog"
        assert labels.get("severity") in ("warning", "critical")
        for ann_field in ("summary", "description", "runbook_url"):
            assert ann_field in rule["annotations"]
            assert rule["annotations"][ann_field]


def test_observer_silent_threshold_locked_at_300s():
    """Lockstep with M060 chain-stale + four-watchdog observer-silent
    thresholds. Drift catches both ways."""
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefModulesObserverSilent"]["expr"]
    assert "> 300" in expr, (
        f"observer-silent must use 300s threshold; got {expr!r}"
    )
    assert "selfdef_modules_last_run_unix" in expr


def test_textfile_emit_failed_references_sentinel_gauge():
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefModulesTextfileEmitFailed"]["expr"]
    assert "selfdef_modules_textfile_emit_failed" in expr


def test_observer_fault_paths_are_critical():
    """Both observer-fault paths (TextfileEmitFailed + ObserverSilent)
    are critical — drift to WARN would let operators ignore wedged
    observer state overnight."""
    by_name = {r["alert"]: r for r in _all_rules()}
    for name in (
        "SelfdefModulesTextfileEmitFailed",
        "SelfdefModulesObserverSilent",
    ):
        assert by_name[name]["labels"]["severity"] == "critical"


def test_count_low_threshold_locked():
    """SelfdefModulesCountLow threshold MUST be 100 — locks the
    generous floor; selfdef actually ships 188+ modules."""
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefModulesCountLow"]["expr"]
    assert "< 100" in expr, (
        f"count-low must use 100 threshold (generous floor below the "
        f"188+ shipped count); got {expr!r}"
    )


def test_catalog_link_labels_distinguish_alert_origin():
    by_name = {r["alert"]: r for r in _all_rules()}
    expected = {
        "SelfdefModulesTextfileEmitFailed": "observer-fault",
        "SelfdefModulesObserverSilent":     "observer-silent",
        "SelfdefModulesCountLow":           "rollup",
    }
    for name, link in expected.items():
        assert by_name[name]["labels"].get("catalog_link") == link, (
            f"alert {name!r} catalog_link drift"
        )


def test_rule_group_interval_is_30s():
    doc = _load_rules()
    group = next(g for g in doc["groups"] if g["name"] == "selfdef-modules-catalog")
    assert group["interval"] == "30s"


def test_rules_file_cites_selfdef_producer_commit():
    body = RULES_PATH.read_text()
    assert "1ce88c7" in body, (
        "rules file should cite the selfdef producer commit (1ce88c7)"
    )


def test_runbook_sections_present_for_every_alert():
    """Every alert MUST have a `#### <AlertName>` section in the
    deployment guide so the runbook_url anchor resolves."""
    guide_path = (
        REPO_ROOT / "docs" / "operator" / "m060-deployment-guide.md"
    )
    body = guide_path.read_text()
    for name in REQUIRED_ALERTS:
        anchor = f"#### {name}"
        assert anchor in body, (
            f"deployment guide missing runbook section {anchor!r}"
        )


def test_runbook_sections_include_diagnosis_and_fix_blocks():
    guide_path = (
        REPO_ROOT / "docs" / "operator" / "m060-deployment-guide.md"
    )
    body = guide_path.read_text()
    for name in REQUIRED_ALERTS:
        section_start = body.find(f"#### {name}")
        next_h4 = body.find("\n#### ", section_start + 1)
        next_h2 = body.find("\n## ", section_start + 1)
        candidates = [x for x in (next_h4, next_h2) if x > 0]
        section_end = min(candidates) if candidates else len(body)
        section = body[section_start:section_end]
        assert "**Diagnosis:**" in section, (
            f"runbook section {name!r} missing **Diagnosis:**"
        )
        assert "**Fix:**" in section, (
            f"runbook section {name!r} missing **Fix:**"
        )
        assert "```" in section, (
            f"runbook section {name!r} missing fenced code block"
        )
