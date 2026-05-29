"""MS022 SSE subscriber quota Prometheus alert rules — contract test.

Locks the alert surface for the selfdef-side
`selfdef_sse_subscribers_*` metrics shipped in selfdef commit
77b4499. Same drift-protection shape as
test_m060_chain_health_alerts_contract.py: every alert references
the correct metric, severity classification matches semantics,
runbook sections exist for each alert, and thresholds are locked
against silent regressions.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = REPO_ROOT / "config" / "prometheus" / "alerts" / "ms022-sse-quota.rules.yml"
GUIDE_PATH = REPO_ROOT / "docs" / "operator" / "m060-deployment-guide.md"

REQUIRED_ALERTS = {
    "MS022SseGlobalQuotaApproaching",
    "MS022SseGlobalQuotaSaturated",
    "MS022SsePerTokenQuotaSaturated",
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
    assert any(g["name"] == "ms022-sse-quota" for g in doc["groups"])


def test_all_required_alerts_present():
    """Drift catch: each MS022 alert MUST ship. Missing any silently
    masks the failure mode the operator depends on."""
    rules = _all_rules()
    names = {r["alert"] for r in rules}
    missing = REQUIRED_ALERTS - names
    assert not missing, f"missing required MS022 alerts: {sorted(missing)}"


def test_every_alert_carries_required_fields():
    for rule in _all_rules():
        for field in ("alert", "expr", "labels", "annotations"):
            assert field in rule, (
                f"alert {rule.get('alert')!r} missing required field {field!r}"
            )
        labels = rule["labels"]
        assert labels.get("subsystem") == "ms022-sse-quota", (
            f"alert {rule['alert']!r} missing subsystem=ms022-sse-quota"
        )
        assert labels.get("severity") in ("warning", "critical")
        for ann_field in ("summary", "description"):
            assert ann_field in rule["annotations"]
            assert rule["annotations"][ann_field], (
                f"alert {rule['alert']!r} has empty {ann_field}"
            )


def test_global_alerts_reference_saturation_metric():
    """Both global-quota alerts MUST reference
    selfdef_sse_subscribers_global_saturation. Drift would mean the
    alert silently never fires."""
    by_name = {r["alert"]: r for r in _all_rules()}
    for name in ("MS022SseGlobalQuotaApproaching", "MS022SseGlobalQuotaSaturated"):
        expr = by_name[name]["expr"]
        assert "selfdef_sse_subscribers_global_saturation" in expr, (
            f"alert {name!r} expr must reference global_saturation; got {expr!r}"
        )


def test_per_token_alert_references_saturated_count():
    """The per-token alert uses the saturated-count rollup, NOT the
    per-token gauge directly (which would emit one alert per token —
    operator-noisy)."""
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["MS022SsePerTokenQuotaSaturated"]["expr"]
    assert "selfdef_sse_subscribers_per_token_saturated" in expr, (
        f"per-token alert must use the _saturated rollup; got {expr!r}"
    )


def test_severity_classification_matches_semantics():
    """Approaching = warn (proactive), Saturated = critical
    (operator's clients ARE being throttled right now)."""
    by_name = {r["alert"]: r for r in _all_rules()}
    assert by_name["MS022SseGlobalQuotaApproaching"]["labels"]["severity"] == "warning"
    assert by_name["MS022SseGlobalQuotaSaturated"]["labels"]["severity"] == "critical"
    # Per-token saturated stays warning — single token throttling is
    # operator-tractable, not a chain-wide emergency.
    assert by_name["MS022SsePerTokenQuotaSaturated"]["labels"]["severity"] == "warning"


def test_global_approaching_threshold_is_0_85():
    """Lock the 0.85 saturation threshold so operators have ~15%
    headroom to plan capacity before the critical alert fires.
    Drift below 0.85 = noisier; drift above = less headroom."""
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["MS022SseGlobalQuotaApproaching"]["expr"]
    assert "> 0.85" in expr, (
        f"approaching threshold must be exactly 0.85; got {expr!r}"
    )


def test_global_saturated_threshold_is_1():
    """Critical threshold is exactly 100% saturation."""
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["MS022SseGlobalQuotaSaturated"]["expr"]
    assert ">= 1.0" in expr, (
        f"saturated threshold must be exactly 1.0; got {expr!r}"
    )


def test_every_alert_has_for_clause():
    """`for:` clauses suppress single-scrape blips — required on all
    MS022 alerts to avoid pager noise from transient bursts."""
    for rule in _all_rules():
        assert "for" in rule, (
            f"alert {rule['alert']!r} missing `for:` clause"
        )


def test_every_alert_has_runbook_url():
    """Every MS022 alert annotation MUST carry runbook_url pointing
    at the sovereign-os deployment-guide section."""
    for rule in _all_rules():
        url = rule["annotations"].get("runbook_url", "")
        assert "cyberpunk042/sovereign-os" in url, (
            f"alert {rule['alert']!r} runbook_url must point at the "
            f"sovereign-os runbook; got: {url!r}"
        )
        assert "m060-deployment-guide" in url, (
            f"alert {rule['alert']!r} runbook_url must reference the "
            f"deployment guide; got: {url!r}"
        )


def test_every_alert_has_runbook_section_in_guide():
    """Each MS022 alert MUST have a matching `#### <AlertName>` section
    in the deployment guide so the runbook_url anchor resolves. Pager
    landing on a non-existent anchor = silent operator dead-end."""
    guide_text = GUIDE_PATH.read_text()
    for name in REQUIRED_ALERTS:
        assert f"#### {name}" in guide_text, (
            f"deployment-guide missing runbook section for {name!r}"
        )


def test_runbook_sections_carry_diagnosis_and_fix_commands():
    """Each runbook section must contain a diagnosis command path
    (curl/journalctl/systemctl) AND a fix path (config edit + restart
    OR rotate subscribers). Empty runbook sections = useless to the
    operator paging in at 3am."""
    guide_text = GUIDE_PATH.read_text()
    for name in REQUIRED_ALERTS:
        idx = guide_text.find(f"#### {name}")
        # Take the next ~3000 chars as the section body.
        section = guide_text[idx : idx + 3000]
        next_heading = re.search(r"^####? ", section[10:], re.MULTILINE)
        if next_heading:
            section = section[: next_heading.start() + 10]
        # Diagnosis tooling.
        assert (
            "curl" in section or "journalctl" in section or "systemctl" in section
        ), (
            f"runbook section for {name!r} missing a diagnosis command "
            f"(curl/journalctl/systemctl)"
        )
        # Fix path: either a config-edit hint OR a verb invocation.
        assert (
            "selfdef.toml" in section
            or "systemctl restart" in section
            or "selfdefctl" in section
        ), (
            f"runbook section for {name!r} missing a fix command path "
            f"(config edit / systemctl restart / selfdefctl verb)"
        )
