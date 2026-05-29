"""Four-watchdog IPS-spine Prometheus alert rules — contract test.

Locks the alert surface for the selfdef-side
`selfdef_four_watchdog_*` textfile gauges shipped by
selfdef-four-watchdog-doctor.{service,timer} (selfdef commits
`7869a45` + `a009b39`). Same drift-protection shape as the M060
chain-health and MS022 SSE quota alerts — every alert references
the correct gauge metric, severity classification matches semantics,
each alert carries the required envelope fields, and thresholds are
locked against silent regressions.

The four-watchdog set IS the IPS spine per SECURITY.md and SDD-004
§"Four-watchdog set (IPS spine, MS046+MS047+MS044+MS048)" — drift
catching here protects the operator-visible early-warning surface
for the production-shipped IPS runtime.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = (
    REPO_ROOT / "config" / "prometheus" / "alerts" / "four-watchdog.rules.yml"
)

REQUIRED_ALERTS = {
    "FourWatchdogWorstSeverityCritical",
    "FourWatchdogAnyWarn",
    "FourWatchdogTextfileEmitFailed",
    "FourWatchdogObserverSilent",
}


def _load_rules() -> dict:
    return yaml.safe_load(RULES_PATH.read_text())


def _all_rules() -> list[dict]:
    doc = _load_rules()
    return [r for g in doc["groups"] for r in g["rules"]]


def test_rules_file_present_and_valid_yaml():
    assert RULES_PATH.is_file(), f"missing alert rules file: {RULES_PATH}"
    doc = _load_rules()
    assert "groups" in doc
    assert any(g["name"] == "four-watchdog" for g in doc["groups"])


def test_all_required_alerts_present():
    """Drift catch: each four-watchdog alert MUST ship. Missing any
    silently masks the failure mode the operator depends on."""
    names = {r["alert"] for r in _all_rules()}
    missing = REQUIRED_ALERTS - names
    assert not missing, (
        f"missing required four-watchdog alerts: {sorted(missing)}"
    )


def test_every_alert_carries_required_fields():
    for rule in _all_rules():
        for field in ("alert", "expr", "for", "labels", "annotations"):
            assert field in rule, (
                f"alert {rule.get('alert')!r} missing required field {field!r}"
            )
        labels = rule["labels"]
        assert labels.get("subsystem") == "four-watchdog", (
            f"alert {rule['alert']!r} missing subsystem=four-watchdog"
        )
        assert labels.get("severity") in ("warning", "critical")
        for ann_field in ("summary", "description", "runbook_url"):
            assert ann_field in rule["annotations"]
            assert rule["annotations"][ann_field], (
                f"alert {rule['alert']!r} has empty {ann_field}"
            )


def test_worst_severity_alert_references_rollup_gauge():
    """FourWatchdogWorstSeverityCritical MUST reference the worst-
    severity rollup gauge — drift would silently never fire."""
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["FourWatchdogWorstSeverityCritical"]["expr"]
    assert "selfdef_four_watchdog_worst_severity" in expr, (
        f"FourWatchdogWorstSeverityCritical must reference worst_severity; "
        f"got {expr!r}"
    )
    assert ">= 2" in expr or ">=2" in expr, (
        f"critical threshold must be >= 2 (the CRITICAL severity value); "
        f"got {expr!r}"
    )


def test_warn_alert_targets_severity_one_exact():
    """FourWatchdogAnyWarn MUST target severity==1 (not >=1) so it
    doesn't double-fire alongside the critical alert. Drift here =
    operator gets two pages for the same incident."""
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["FourWatchdogAnyWarn"]["expr"]
    assert "== 1" in expr or "==1" in expr, (
        f"WARN alert must target == 1 exactly (not >= 1) to avoid "
        f"double-pages with critical; got {expr!r}"
    )


def test_textfile_emit_failed_references_sentinel_gauge():
    """FourWatchdogTextfileEmitFailed MUST reference the honest-offline
    sentinel gauge — drift here means the operator silently can't tell
    a wedged wrapper from a healthy daemon."""
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["FourWatchdogTextfileEmitFailed"]["expr"]
    assert "selfdef_four_watchdog_textfile_emit_failed" in expr, (
        f"emit-failed alert must reference the sentinel gauge; "
        f"got {expr!r}"
    )


def test_observer_silent_threshold_locked_at_300s():
    """The observer-silent threshold MUST be 300s (5x the 60s cadence)
    — locked in the cross-surface threshold-lockstep contract test
    alongside the rest of the M060 chain. Drift catches both ways:
    too-tight = false page on transient lag; too-loose = silent
    observer outage."""
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["FourWatchdogObserverSilent"]["expr"]
    assert "> 300" in expr, (
        f"observer-silent alert must use the canonical 300s threshold; "
        f"got {expr!r}"
    )
    assert "selfdef_four_watchdog_last_run_unix" in expr, (
        f"observer-silent alert must reference last_run_unix; got {expr!r}"
    )


def test_observer_fault_severity_is_critical():
    """The observer-fault paths (TextfileEmitFailed + ObserverSilent)
    are CRITICAL — a wedged observer means the operator can't see the
    IPS spine state at all. Drift here = WARN-classified observer
    fault that the operator might ignore overnight."""
    by_name = {r["alert"]: r for r in _all_rules()}
    for name in ("FourWatchdogTextfileEmitFailed", "FourWatchdogObserverSilent"):
        sev = by_name[name]["labels"]["severity"]
        assert sev == "critical", (
            f"alert {name!r} must be severity=critical; got {sev!r}"
        )


def test_spine_link_labels_distinguish_alert_origin():
    """Each alert carries a spine_link label distinguishing rollup-
    based alerts (firing on the four-watchdog metric itself) from
    observer-fault alerts (firing on the wrapper's health). Drift
    here = Grafana filters can't group the alerts correctly."""
    by_name = {r["alert"]: r for r in _all_rules()}
    expected = {
        "FourWatchdogWorstSeverityCritical": "rollup",
        "FourWatchdogAnyWarn":               "rollup",
        "FourWatchdogTextfileEmitFailed":    "observer-fault",
        "FourWatchdogObserverSilent":        "observer-silent",
    }
    for name, link in expected.items():
        actual = by_name[name]["labels"].get("spine_link")
        assert actual == link, (
            f"alert {name!r} spine_link label drift: expected {link!r}, "
            f"got {actual!r}"
        )


def test_rule_group_interval_is_30s():
    """The rule group MUST evaluate at 30s — matches the Prometheus
    scrape interval. Drift to 60s would mean a 60s blind window
    after each fire window."""
    doc = _load_rules()
    group = next(g for g in doc["groups"] if g["name"] == "four-watchdog")
    assert group["interval"] == "30s"


def test_all_runbook_urls_point_at_deployment_guide():
    """All runbook_url annotations MUST point at the deployment guide
    — drift catches the case where one alert silently links to a
    nonexistent runbook section."""
    for rule in _all_rules():
        url = rule["annotations"]["runbook_url"]
        assert "m060-deployment-guide.md" in url, (
            f"alert {rule['alert']!r} runbook_url must point at the "
            f"deployment guide; got {url!r}"
        )
        # Anchor to lowercased alert name (Prometheus convention).
        anchor = rule["alert"].lower()
        assert anchor in url.lower(), (
            f"alert {rule['alert']!r} runbook_url must include the "
            f"alert-name anchor {anchor!r}; got {url!r}"
        )


def test_ips_spine_anchored_in_comment_block():
    """The rules file header MUST document the IPS-spine anchor
    (MS046+MS047+MS044+MS048) so operators reading the rules know
    what production-shipped milestones they protect. Drift here
    means the audit trail thins out."""
    body = RULES_PATH.read_text()
    for ms in ("MS046", "MS047", "MS044", "MS048"):
        assert ms in body, (
            f"rules file header must anchor to {ms} (IPS spine)"
        )


def test_runbook_sections_present_for_every_alert():
    """Every four-watchdog alert MUST have a `#### <AlertName>` section
    in the deployment guide so the runbook_url anchor actually resolves.
    Drift here = the alert pages and the runbook 404s on the operator."""
    guide_path = (
        REPO_ROOT / "docs" / "operator" / "m060-deployment-guide.md"
    )
    body = guide_path.read_text()
    for name in REQUIRED_ALERTS:
        anchor = f"#### {name}"
        assert anchor in body, (
            f"deployment guide missing runbook section {anchor!r} — "
            f"the alert's runbook_url 404s without it"
        )


def test_runbook_sections_include_diagnosis_and_fix_blocks():
    """Each four-watchdog runbook section MUST include actionable
    bash diagnosis commands AND a Fix block — drift to summary-only
    documentation defeats the runbook's purpose."""
    guide_path = (
        REPO_ROOT / "docs" / "operator" / "m060-deployment-guide.md"
    )
    body = guide_path.read_text()
    for name in REQUIRED_ALERTS:
        section_start = body.find(f"#### {name}")
        # Find the next #### or ## boundary as the section end.
        next_h4 = body.find("\n#### ", section_start + 1)
        next_h2 = body.find("\n## ", section_start + 1)
        candidates = [x for x in (next_h4, next_h2) if x > 0]
        section_end = min(candidates) if candidates else len(body)
        section = body[section_start:section_end]
        assert "**Diagnosis:**" in section, (
            f"runbook section {name!r} missing **Diagnosis:** block"
        )
        assert "**Fix:**" in section, (
            f"runbook section {name!r} missing **Fix:** block"
        )
        assert "```" in section, (
            f"runbook section {name!r} missing a fenced code block "
            f"(diagnosis commands must be operator-copyable)"
        )


def test_rules_file_cites_selfdef_producer_commit():
    """The rules file MUST cite the selfdef-side producer commit so
    operators reading the rules can find the canonical producer.
    Drift catches the case where the producer side moves without
    updating the consumer-side audit trail."""
    body = RULES_PATH.read_text()
    assert "7869a45" in body or "a009b39" in body, (
        "rules file should cite the selfdef producer commit "
        "(7869a45 or a009b39 — the four-watchdog observer ship)"
    )
