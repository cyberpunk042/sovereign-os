"""Contract tests for the sovereign-telemetry Grafana dashboard.

Locks that the dashboard surfaces every metric the probe emits (so a panel
can't silently drop a signal) and keeps its identity stable.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASH_PATH = (
    REPO_ROOT / "docs" / "observability" / "dashboards" / "sovereign-os-telemetry.json"
)

# Lockstep with crates/sovereign-telemetry/src/main.rs::Sample::to_prometheus
# and config/prometheus/alerts/sovereign-telemetry.rules.yml.
EMITTED_METRICS = {
    "sovereign_pressure_axis",
    "sovereign_load_util_pct",
    "sovereign_load_vram_used_gb",
    "sovereign_thermal_verdict",
    "sovereign_thermal_any_shutdown",
    "sovereign_adaptive_reaction_active",
    "sovereign_telemetry_valid",
}


def _dash() -> dict:
    return json.loads(DASH_PATH.read_text(encoding="utf-8"))


def _all_exprs(dash: dict) -> str:
    out = []
    for p in dash["panels"]:
        for t in p.get("targets", []):
            out.append(t.get("expr", ""))
    return "\n".join(out)


def test_dashboard_exists_and_parses():
    assert DASH_PATH.is_file()
    assert _dash()["panels"], "dashboard has panels"


def test_identity_is_stable():
    d = _dash()
    assert d["uid"] == "sovereign-telemetry"
    assert "telemetry" in d["tags"] and "sovereign-os" in d["tags"]
    assert d["refresh"] == "30s"


def test_every_emitted_metric_is_on_a_panel():
    exprs = _all_exprs(_dash())
    for m in EMITTED_METRICS:
        assert m in exprs, f"metric {m} not surfaced on any panel"


def test_panel_count_locked():
    assert len(_dash()["panels"]) == 8


def test_thermal_shutdown_panel_has_red_threshold():
    d = _dash()
    panel = next(p for p in d["panels"] if "Thermal shutdown" in p["title"])
    steps = panel["fieldConfig"]["defaults"]["thresholds"]["steps"]
    assert any(s.get("color") == "red" and s.get("value") == 1 for s in steps), steps


def test_every_panel_uses_prometheus_datasource():
    for p in _dash()["panels"]:
        assert p["datasource"]["type"] == "prometheus", p["title"]
