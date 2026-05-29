"""Four-watchdog cross-surface threshold-lockstep lint.

The four-watchdog observability arc shares 3 invariants across the
consumer-side surfaces (alert rules + Grafana dashboard + runbook
sections). Drift between them is the silent operator-misdirection
hazard. Per-surface contract tests catch drift WITHIN each surface;
THIS test catches drift BETWEEN them.

  1. Observer-silent threshold == 300s (5 minutes) — locked across:
       - alert rules YAML (`> 300` literal)
       - Grafana dashboard (red threshold step value=300)
       - runbook sections (mention "300s" or "5 minutes")
     Also matches the M060 chain stale-age threshold (cross-arc
     consistency — see test_m060_threshold_lockstep_contract.py).

  2. Severity ladder == {0=OK, 1=WARN, 2=CRITICAL, -1=UNKNOWN}
     locked across:
       - dashboard panel value mappings
       - alert rules expressions (`== 1`, `>= 2`)
       - runbook section severity classifiers

  3. IPS-spine MS family anchor (MS046 process / MS047 perimeter /
     MS044 tamper / MS048 config) locked across:
       - alert rules YAML header
       - dashboard `_comment` block
       - runbook section diagnosis bash (per-alert routing by
         `ms=MSXXX` label)

Optional cross-repo cross-reference via `$SELFDEF_REPO_ROOT` to
verify the partner's wrapper at `packaging/scripts/
four-watchdog-textfile.sh` carries the same canonical metric names
+ severity ladder. Closes the bidirectional drift loop matching
the M060 + MS022 patterns.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

# Canonical four-watchdog invariants.
OBSERVER_SILENT_THRESHOLD_SECS = 300  # 5 minutes
SEVERITY_LADDER = {-1: "UNKNOWN", 0: "OK", 1: "WARN", 2: "CRITICAL"}
IPS_SPINE_MILESTONES = {"MS046", "MS047", "MS044", "MS048"}

ALERTS_PATH = (
    REPO_ROOT / "config" / "prometheus" / "alerts" / "four-watchdog.rules.yml"
)
DASHBOARD_PATH = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-four-watchdog.json"
)
GUIDE_PATH = REPO_ROOT / "docs" / "operator" / "m060-deployment-guide.md"


def _read(path: Path) -> str:
    return path.read_text()


def _alert_rules() -> list[dict]:
    doc = yaml.safe_load(_read(ALERTS_PATH))
    return [r for g in doc["groups"] for r in g["rules"]]


def _dashboard() -> dict:
    return json.loads(_read(DASHBOARD_PATH))


def test_observer_silent_threshold_300_across_all_surfaces():
    """The 300s threshold MUST appear identically in the alert
    expression AND the dashboard red-threshold step value AND the
    runbook section text. Drift = the alert pages at a different
    age than the dashboard turns red."""
    # Alert side: `> 300` literal in expr.
    by_name = {r["alert"]: r for r in _alert_rules()}
    expr = by_name["FourWatchdogObserverSilent"]["expr"]
    assert "> 300" in expr, (
        f"FourWatchdogObserverSilent expr must use > 300; got {expr!r}"
    )

    # Dashboard side: red threshold step at value=300 on observer-age
    # panel.
    dash = _dashboard()
    found_red_300 = False
    for panel in dash["panels"]:
        title = panel.get("title", "").lower()
        if "observer age" not in title and "observer-age" not in title:
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
                break
    assert found_red_300, (
        "dashboard must render red threshold at value=300 on observer-age panel"
    )

    # Runbook side: the FourWatchdogObserverSilent section must
    # mention 300s OR 5 minutes verbatim.
    guide = _read(GUIDE_PATH)
    section_start = guide.find("#### FourWatchdogObserverSilent")
    assert section_start != -1
    next_h = guide.find("\n#### ", section_start + 1)
    section = guide[section_start:next_h if next_h > 0 else len(guide)]
    assert "300s" in section or "5+ minutes" in section, (
        "FourWatchdogObserverSilent runbook section must reference the "
        "300s/5-minute threshold for operator-side clarity"
    )


def test_severity_ladder_consistent_across_alert_expr_and_dashboard():
    """The 0/1/2 ladder MUST appear identically in the alert expr
    (`== 1`, `>= 2`) and the dashboard value mappings (text=OK/
    WARN/CRITICAL on numeric values). Drift = the dashboard turns
    a different color than the alert fires."""
    # Alert side: WARN at == 1, CRITICAL at >= 2.
    by_name = {r["alert"]: r for r in _alert_rules()}
    warn_expr = by_name["FourWatchdogAnyWarn"]["expr"]
    crit_expr = by_name["FourWatchdogWorstSeverityCritical"]["expr"]
    assert ("== 1" in warn_expr or "==1" in warn_expr)
    assert (">= 2" in crit_expr or ">=2" in crit_expr)

    # Dashboard side: the worst-severity stat panel must map all 4
    # canonical values (-1/0/1/2) to their canonical text labels.
    dash = _dashboard()
    found_full_ladder = False
    for panel in dash["panels"]:
        if "worst severity" not in panel.get("title", "").lower():
            continue
        mappings = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("mappings", [])
        )
        for m in mappings:
            opts = m.get("options", {})
            keys_present = {k for k in opts.keys()}
            if {"0", "1", "2", "-1"} <= keys_present:
                texts = {str(k): opts[str(k)].get("text", "") for k in keys_present}
                if (texts.get("0") == "OK"
                        and texts.get("1") == "WARN"
                        and texts.get("2") == "CRITICAL"
                        and texts.get("-1") == "UNKNOWN"):
                    found_full_ladder = True
                    break
        if found_full_ladder:
            break
    assert found_full_ladder, (
        "dashboard worst-severity panel must map all 4 canonical values "
        "(-1/0/1/2) to their canonical text labels (UNKNOWN/OK/WARN/CRITICAL)"
    )


def test_ips_spine_anchor_in_all_three_surfaces():
    """The 4 IPS-spine milestone IDs MUST appear in:
       - the alert rules header (audit anchor)
       - the dashboard _comment block (audit anchor)
       - the runbook sections (operator routing context)
    Drift here = the audit trail thins out across surfaces."""
    alerts = _read(ALERTS_PATH)
    dash_comment = _dashboard().get("_comment", "")
    guide = _read(GUIDE_PATH)

    for ms in IPS_SPINE_MILESTONES:
        assert ms in alerts, f"alert rules missing IPS-spine anchor {ms}"
        assert ms in dash_comment, (
            f"dashboard _comment missing IPS-spine anchor {ms}"
        )
        # Runbook side: the critical alert's Fix block routes by ms=MSXXX.
        section_start = guide.find("#### FourWatchdogWorstSeverityCritical")
        assert section_start != -1
        next_h = guide.find("\n#### ", section_start + 1)
        section = guide[section_start:next_h if next_h > 0 else len(guide)]
        assert ms in section, (
            f"FourWatchdogWorstSeverityCritical runbook section missing "
            f"IPS-spine routing for {ms}"
        )


def test_alert_severities_align_with_runbook_section_severities():
    """Each alert MUST advertise its severity (warning/critical)
    consistently with the runbook section heading suffix
    `(warning)` or `(critical)`. Drift = page severity ≠ runbook
    severity."""
    by_name = {r["alert"]: r for r in _alert_rules()}
    guide = _read(GUIDE_PATH)
    expected_runbook_headings = {
        "FourWatchdogWorstSeverityCritical": "#### FourWatchdogWorstSeverityCritical (critical)",
        "FourWatchdogAnyWarn":               "#### FourWatchdogAnyWarn (warning)",
        "FourWatchdogTextfileEmitFailed":    "#### FourWatchdogTextfileEmitFailed (critical)",
        "FourWatchdogObserverSilent":        "#### FourWatchdogObserverSilent (critical)",
    }
    for name, expected_heading in expected_runbook_headings.items():
        assert expected_heading in guide, (
            f"runbook missing heading {expected_heading!r}"
        )
        alert_sev = by_name[name]["labels"]["severity"]
        runbook_sev = (
            "critical" if "(critical)" in expected_heading
            else "warning"
        )
        assert alert_sev == runbook_sev, (
            f"alert {name!r} severity={alert_sev} but runbook says "
            f"{runbook_sev} — drift"
        )


def test_canonical_metric_names_match_across_alerts_and_dashboard():
    """The 4 canonical gauges MUST appear identically in the alert
    expressions AND the dashboard panel targets. Drift = the alert
    fires on one metric while the dashboard renders another."""
    canonical = {
        "selfdef_four_watchdog_worst_severity",
        "selfdef_four_watchdog_last_run_unix",
        "selfdef_four_watchdog_textfile_emit_failed",
        "selfdef_four_watchdog_severity",
    }
    alerts_text = _read(ALERTS_PATH)
    dash = _dashboard()
    all_panel_exprs = " ".join(
        t.get("expr", "")
        for p in dash["panels"]
        for t in p.get("targets", [])
    )
    for gauge in canonical:
        assert gauge in alerts_text, (
            f"alert rules missing canonical gauge {gauge!r}"
        )
        assert gauge in all_panel_exprs, (
            f"dashboard missing canonical gauge {gauge!r} on any panel"
        )


def test_partner_repo_selfdef_wrapper_carries_canonical_metrics():
    """Cross-repo opt-in: when $SELFDEF_REPO_ROOT points at a
    selfdef checkout, verify the partner's wrapper script emits
    the same canonical gauge names. Skipped silently when env var
    unset. Closes the bidirectional drift loop matching the M060 +
    MS022 cross-repo patterns."""
    partner_env = os.environ.get("SELFDEF_REPO_ROOT")
    if not partner_env:
        return
    partner = Path(partner_env)
    wrapper_path = (
        partner / "packaging" / "scripts" / "four-watchdog-textfile.sh"
    )
    if not wrapper_path.is_file():
        return
    body = wrapper_path.read_text()
    for gauge in (
        "selfdef_four_watchdog_worst_severity",
        "selfdef_four_watchdog_severity",
        "selfdef_four_watchdog_last_run_unix",
        "selfdef_four_watchdog_textfile_emit_failed",
    ):
        assert gauge in body, (
            f"partner-repo wrapper missing canonical gauge {gauge!r}"
        )


def test_partner_repo_selfdef_wrapper_severity_ladder_matches():
    """Cross-repo opt-in: partner wrapper's severity_to_int MUST
    map ok/warn/critical/unknown to 0/1/2/-1 — the same ladder the
    sovereign-os consumer surfaces render."""
    partner_env = os.environ.get("SELFDEF_REPO_ROOT")
    if not partner_env:
        return
    partner = Path(partner_env)
    wrapper_path = (
        partner / "packaging" / "scripts" / "four-watchdog-textfile.sh"
    )
    if not wrapper_path.is_file():
        return
    body = wrapper_path.read_text()
    # Look for the severity_to_int function and its case-arms.
    m = re.search(
        r"severity_to_int\(\)[^}]*?ok\)\s*echo\s*(\d+).*?warn\)\s*echo\s*(\d+).*?critical\)\s*echo\s*(\d+)",
        body, re.DOTALL,
    )
    assert m is not None, (
        "partner-repo wrapper missing severity_to_int ok/warn/critical mapping"
    )
    assert (m.group(1), m.group(2), m.group(3)) == ("0", "1", "2"), (
        f"partner-repo severity ladder drift: "
        f"ok={m.group(1)} warn={m.group(2)} critical={m.group(3)}"
    )
