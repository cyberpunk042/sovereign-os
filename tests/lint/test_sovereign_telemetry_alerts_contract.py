"""Contract tests for the sovereign-telemetry Prometheus alert rules.

Locks that the alerts on the `sovereign-telemetry --prometheus` metric
surface (M045 E0430 / M013) stay well-formed and reference only metrics the
probe actually emits, so the operator-visible surface can't silently drift
from the producer.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = (
    REPO_ROOT / "config" / "prometheus" / "alerts" / "sovereign-telemetry.rules.yml"
)

# The metric families sovereign-telemetry emits in --prometheus mode. Kept in
# lockstep with crates/sovereign-telemetry/src/main.rs::Sample::to_prometheus.
EMITTED_METRICS = {
    "sovereign_pressure_axis",
    "sovereign_load_util_pct",
    "sovereign_load_vram_used_gb",
    "sovereign_thermal_verdict",
    "sovereign_thermal_any_shutdown",
    "sovereign_adaptive_reaction_active",
    "sovereign_telemetry_valid",
}


def _rules() -> list[dict]:
    doc = yaml.safe_load(RULES_PATH.read_text(encoding="utf-8"))
    groups = doc["groups"]
    assert len(groups) == 1 and groups[0]["name"] == "sovereign-telemetry"
    return groups[0]["rules"]


def test_rules_file_exists_and_parses():
    assert RULES_PATH.is_file()
    assert _rules(), "at least one alert rule"


def test_expected_alerts_present():
    names = {r["alert"] for r in _rules()}
    assert {
        "SovereignTelemetryThermalShutdown",
        "SovereignTelemetryHighSystemPressure",
        "SovereignTelemetryInvalidSnapshot",
    } <= names


def test_every_expr_references_only_emitted_metrics():
    for r in _rules():
        expr = r["expr"]
        assert any(m in expr for m in EMITTED_METRICS), (
            f"{r['alert']} expr references no emitted metric: {expr}"
        )


def test_every_alert_has_severity_for_and_runbook():
    for r in _rules():
        assert r["labels"]["severity"] in {"warning", "critical"}, r["alert"]
        assert "for" in r, r["alert"]
        assert r["annotations"]["runbook_url"].startswith("https://"), r["alert"]
        # runbook anchor matches the alert name, lower-cased + severity.
        anchor = r["annotations"]["runbook_url"].rsplit("#", 1)[-1]
        assert r["alert"].lower() in anchor, (r["alert"], anchor)


def test_thermal_shutdown_is_critical():
    rule = next(
        r for r in _rules() if r["alert"] == "SovereignTelemetryThermalShutdown"
    )
    assert rule["labels"]["severity"] == "critical"
    assert "sovereign_thermal_any_shutdown" in rule["expr"]
