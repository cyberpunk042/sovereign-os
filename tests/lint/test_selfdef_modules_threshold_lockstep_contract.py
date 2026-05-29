"""Selfdef module-catalog cross-surface threshold-lockstep lint.

The module-catalog observability arc shares 3 invariants across the
consumer-side surfaces (alert rules + Grafana dashboard + runbook
sections). Drift between them is the silent operator-misdirection
hazard.

  1. Observer-silent threshold == 300s — locked across:
       - alert rules YAML (`> 300` literal)
       - Grafana dashboard (red threshold step value=300)
       - runbook sections (300s / 5 minutes mention)
     Also matches the M060 chain + four-watchdog observer-silent
     thresholds (cross-arc consistency — locked at the chain-wide
     300s threshold across all 3 observability verticals).

  2. CountLow threshold == 100 — locked across:
       - alert rules YAML (`< 100` literal)
       - Grafana dashboard (yellow threshold step value=100)

  3. Canonical metric names locked across:
       - alert rules YAML
       - Grafana dashboard panel exprs
       - selfdef producer wrapper (via opt-in cross-repo check)

Optional cross-repo cross-reference via $SELFDEF_REPO_ROOT verifies
the partner's wrapper at packaging/scripts/selfdef-modules-textfile.sh
carries the same canonical metric names. Closes the bidirectional
drift loop matching the M060 + MS022 + four-watchdog patterns.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

OBSERVER_SILENT_THRESHOLD_SECS = 300  # 5 minutes (locked across all 3 verticals)
COUNT_LOW_THRESHOLD = 100  # 188+ shipped at install time

ALERTS_PATH = (
    REPO_ROOT / "config" / "prometheus" / "alerts"
    / "selfdef-modules-catalog.rules.yml"
)
DASHBOARD_PATH = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-selfdef-modules.json"
)
GUIDE_PATH = REPO_ROOT / "docs" / "operator" / "m060-deployment-guide.md"

CANONICAL_GAUGES = {
    "selfdef_modules_total",
    "selfdef_modules_by_category",
    "selfdef_modules_by_phase",
    "selfdef_modules_last_run_unix",
    "selfdef_modules_textfile_emit_failed",
}


def _read(path: Path) -> str:
    return path.read_text()


def _alert_rules() -> list[dict]:
    doc = yaml.safe_load(_read(ALERTS_PATH))
    return [r for g in doc["groups"] for r in g["rules"]]


def _dashboard() -> dict:
    return json.loads(_read(DASHBOARD_PATH))


def test_observer_silent_threshold_300s_across_alert_and_dashboard():
    """The 300s threshold MUST appear identically in the alert
    expression AND the dashboard red-threshold step value."""
    by_name = {r["alert"]: r for r in _alert_rules()}
    expr = by_name["SelfdefModulesObserverSilent"]["expr"]
    assert "> 300" in expr, (
        f"alert ObserverSilent must use > 300; got {expr!r}"
    )

    dash = _dashboard()
    found_red_300 = False
    for panel in dash["panels"]:
        title = panel.get("title", "").lower()
        if "observer age" not in title:
            continue
        steps = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("thresholds", {})
            .get("steps", [])
        )
        for s in steps:
            if s.get("color") == "red" and s.get("value") == 300:
                found_red_300 = True
    assert found_red_300, (
        "dashboard must render red threshold at value=300 on observer-age panel"
    )


def test_observer_silent_runbook_documents_300s():
    """The runbook section MUST mention the 300s / 5-minute
    threshold so operators understand the trigger condition."""
    guide = _read(GUIDE_PATH)
    section_start = guide.find("#### SelfdefModulesObserverSilent")
    assert section_start != -1
    next_h = guide.find("\n#### ", section_start + 1)
    section = guide[section_start:next_h if next_h > 0 else len(guide)]
    assert "300s" in section or "5+ minutes" in section, (
        "runbook section must reference 300s / 5+ minutes threshold"
    )


def test_count_low_threshold_100_across_alert_and_dashboard():
    """The 100 floor MUST appear identically in the alert + dashboard."""
    by_name = {r["alert"]: r for r in _alert_rules()}
    expr = by_name["SelfdefModulesCountLow"]["expr"]
    assert "< 100" in expr

    dash = _dashboard()
    found = False
    for panel in dash["panels"]:
        targets = [t.get("expr", "") for t in panel.get("targets", [])]
        if not any("selfdef_modules_total" in e for e in targets):
            continue
        steps = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("thresholds", {})
            .get("steps", [])
        )
        for s in steps:
            if s.get("value") == 100:
                found = True
                break
    assert found, "dashboard must mark the 100 threshold"


def test_canonical_metric_names_match_across_alerts_and_dashboard():
    """The 5 canonical gauges MUST appear identically in the alert
    expressions AND the dashboard panel targets."""
    alerts_text = _read(ALERTS_PATH)
    dash = _dashboard()
    all_panel_exprs = " ".join(
        t.get("expr", "")
        for p in dash["panels"]
        for t in p.get("targets", [])
    )
    for gauge in CANONICAL_GAUGES:
        if gauge in {"selfdef_modules_by_category",
                     "selfdef_modules_by_phase"}:
            # These appear in dashboard targets but not necessarily
            # alert exprs (alerts focus on the rollup gauges).
            assert gauge in all_panel_exprs, (
                f"dashboard missing canonical gauge {gauge!r}"
            )
            continue
        assert gauge in alerts_text, (
            f"alert rules missing canonical gauge {gauge!r}"
        )
        assert gauge in all_panel_exprs, (
            f"dashboard missing canonical gauge {gauge!r}"
        )


def test_alert_severities_align_with_runbook_section_severities():
    """Each alert MUST advertise its severity (warning/critical)
    consistently with the runbook section heading suffix."""
    by_name = {r["alert"]: r for r in _alert_rules()}
    guide = _read(GUIDE_PATH)
    expected_headings = {
        "SelfdefModulesTextfileEmitFailed": "#### SelfdefModulesTextfileEmitFailed (critical)",
        "SelfdefModulesObserverSilent":     "#### SelfdefModulesObserverSilent (critical)",
        "SelfdefModulesCountLow":           "#### SelfdefModulesCountLow (warning)",
    }
    for name, expected in expected_headings.items():
        assert expected in guide, (
            f"runbook missing heading {expected!r}"
        )
        alert_sev = by_name[name]["labels"]["severity"]
        runbook_sev = (
            "critical" if "(critical)" in expected else "warning"
        )
        assert alert_sev == runbook_sev, (
            f"alert {name!r} severity mismatch: alert={alert_sev} "
            f"runbook={runbook_sev}"
        )


def test_partner_repo_wrapper_carries_canonical_metric_names():
    """Cross-repo opt-in: when $SELFDEF_REPO_ROOT points at a
    selfdef checkout, verify the partner's wrapper script emits the
    same canonical gauge names. Skipped silently when env var
    unset."""
    partner_env = os.environ.get("SELFDEF_REPO_ROOT")
    if not partner_env:
        return
    partner = Path(partner_env)
    wrapper_path = (
        partner / "packaging" / "scripts" / "selfdef-modules-textfile.sh"
    )
    if not wrapper_path.is_file():
        return
    body = wrapper_path.read_text()
    for gauge in CANONICAL_GAUGES:
        assert gauge in body, (
            f"partner-repo wrapper missing canonical gauge {gauge!r}"
        )


def test_partner_repo_wrapper_cadence_matches_alert_threshold():
    """Cross-repo opt-in: the partner timer's OnUnitActiveSec MUST
    be 60s so the consumer's 300s observer-silent threshold (= 5x
    cadence) is satisfied. Drift would silently break the alert
    tuning."""
    partner_env = os.environ.get("SELFDEF_REPO_ROOT")
    if not partner_env:
        return
    partner = Path(partner_env)
    timer_path = (
        partner / "packaging" / "systemd"
        / "selfdef-modules-textfile.timer"
    )
    if not timer_path.is_file():
        return
    body = timer_path.read_text()
    assert "OnUnitActiveSec=60s" in body, (
        "partner-repo timer cadence drift; locked at 60s by the "
        "consumer's 300s observer-silent threshold"
    )
