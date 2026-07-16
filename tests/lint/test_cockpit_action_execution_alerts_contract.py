"""Contract tests for the cockpit action-execution alert rules.

Locks that the alerts on `sovereign_os_operator_cockpit_action_total`
stay well-formed and reference only outcomes the emitter
(`scripts/operator/_action_exec.py`) actually produces, so the
operator-visible page surface can't silently drift from the producer.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = (
    REPO_ROOT / "config" / "prometheus" / "alerts" / "cockpit-action-execution.rules.yml"
)

# The metric family the cockpit execution emitter produces.
EMITTED_METRIC = "sovereign_os_operator_cockpit_action_total"

# The outcomes _action_exec.py emits (kept in lockstep with the emitter).
EMITTED_OUTCOMES = {
    "executed",
    "dry-run",
    "boundary-reject",
    "validation-reject",
    "confirm-required",
    "key-missing",
    "busy",
    "error",
    "unknown-control",
}

EXPECTED_ALERTS = {
    "CockpitActionBoundaryReject",
    "CockpitActionValidationRejectRateHigh",
    "CockpitActionKeyMissing",
    "CockpitActionErrorRateHigh",
    "CockpitActionUnknownControl",
}


def _rules() -> list[dict]:
    doc = yaml.safe_load(RULES_PATH.read_text(encoding="utf-8"))
    groups = doc["groups"]
    assert len(groups) == 1 and groups[0]["name"] == "cockpit-action-execution"
    return groups[0]["rules"]


def test_rules_file_exists_and_parses():
    assert RULES_PATH.is_file()
    assert _rules(), "at least one alert rule"


def test_expected_alerts_present():
    names = {r["alert"] for r in _rules()}
    assert EXPECTED_ALERTS <= names, EXPECTED_ALERTS - names


def test_every_expr_references_the_emitted_metric():
    for r in _rules():
        expr = r["expr"]
        assert EMITTED_METRIC in expr, (
            f"{r['alert']} expr does not reference {EMITTED_METRIC}: {expr}"
        )


def test_every_expr_references_only_emitted_outcomes():
    """Any `outcome="…"` in an expr must match an outcome the emitter produces."""
    import re
    for r in _rules():
        expr = r["expr"]
        # Find all outcome="..." or outcome=~"..." patterns
        for m in re.finditer(r'outcome=(?:~)?"([^"]+)"', expr):
            value = m.group(1)
            # Split pipe-separated regex alternations
            for outcome in value.split("|"):
                assert outcome in EMITTED_OUTCOMES, (
                    f"{r['alert']} references unknown outcome {outcome!r}"
                )


def test_every_alert_has_severity_for_and_runbook():
    for r in _rules():
        assert r["labels"]["severity"] in {"warning", "critical"}, r["alert"]
        assert r["labels"].get("subsystem") == "cockpit-execution", r["alert"]
        assert "for" in r, r["alert"]
        url = r["annotations"]["runbook_url"]
        assert url.startswith("https://"), r["alert"]
        anchor = url.rsplit("#", 1)[-1]
        assert r["alert"].lower() in anchor, (r["alert"], anchor)


def test_critical_errors_are_critical_severity():
    by_name = {r["alert"]: r for r in _rules()}
    assert by_name["CockpitActionErrorRateHigh"]["labels"]["severity"] == "critical"
