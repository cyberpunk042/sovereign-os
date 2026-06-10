"""Layer 1 lint — Grafana dashboard JSON templates have the minimum
shape Grafana requires (title, uid, panels[], schemaVersion). Per
SDD-016 Layer C — JSON templates are operator-imported; bad JSON
means a silent broken import."""

from __future__ import annotations

import json
import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DASH_DIR = REPO_ROOT / "docs" / "observability" / "dashboards"


def _dashboards() -> list[pathlib.Path]:
    return sorted(DASH_DIR.glob("*.json"))


def test_dashboard_dir_exists():
    assert DASH_DIR.is_dir(), f"missing dashboard dir: {DASH_DIR}"


def test_at_least_two_dashboards_present():
    dashboards = _dashboards()
    assert len(dashboards) >= 2, f"expected ≥2 dashboards, found {len(dashboards)}"


@pytest.mark.parametrize("dash", _dashboards(), ids=lambda p: p.name)
def test_dashboard_json_parses(dash: pathlib.Path):
    """Each JSON parses cleanly."""
    json.loads(dash.read_text())


@pytest.mark.parametrize("dash", _dashboards(), ids=lambda p: p.name)
def test_dashboard_has_minimum_shape(dash: pathlib.Path):
    """Each dashboard has the keys Grafana's import requires."""
    data = json.loads(dash.read_text())
    for key in ("title", "uid", "panels", "schemaVersion"):
        assert key in data, f"{dash.name}: missing required key '{key}'"
    assert isinstance(data["panels"], list), f"{dash.name}: panels must be a list"
    assert len(data["panels"]) >= 1, f"{dash.name}: must declare ≥1 panel"


@pytest.mark.parametrize("dash", _dashboards(), ids=lambda p: p.name)
def test_dashboard_uses_sovereign_os_metrics(dash: pathlib.Path):
    """Each dashboard references a sanctioned metric family: sovereign_os_*
    (native control-plane gauges), selfdef_* (cross-project mirror dashboards
    consuming the selfdef-emitted gauges per R10212 read-only doctrine:
    sovereign-os consumes, selfdef enforces), sovereign_telemetry_* (the
    dedicated `sovereign-telemetry` probe binary's namespace, M045/M013), OR
    sovereign_gateway_* (the `sovereign-gatewayd` daemon's own GET /metrics
    namespace — served over HTTP by the daemon itself, scraped directly;
    same dedicated-binary precedent as sovereign_telemetry_*)."""
    text = dash.read_text()
    assert (
        ("sovereign_os_" in text)
        or ("selfdef_" in text)
        or ("sovereign_telemetry_" in text)
        or ("sovereign_gateway_" in text)
    ), (
        f"{dash.name}: doesn't reference any sovereign_os_* / selfdef_* / "
        f"sovereign_telemetry_* / sovereign_gateway_* metric — is this "
        f"dashboard tagged correctly?"
    )


@pytest.mark.parametrize("dash", _dashboards(), ids=lambda p: p.name)
def test_dashboard_tagged_sovereign_os(dash: pathlib.Path):
    """Each dashboard carries the 'sovereign-os' tag."""
    data = json.loads(dash.read_text())
    tags = data.get("tags") or []
    assert "sovereign-os" in tags, f"{dash.name}: 'sovereign-os' tag missing from tags={tags}"
