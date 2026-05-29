"""Selfdef systemd-units-health Grafana dashboard — contract test."""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_PATH = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-selfdef-systemd-units.json"
)

CANONICAL_GAUGES = {
    "selfdef_systemd_units_total",
    "selfdef_systemd_units_active",
    "selfdef_systemd_units_inactive",
    "selfdef_systemd_units_failed",
    "selfdef_systemd_units_activating",
    "selfdef_systemd_units_other",
    "selfdef_systemd_units_textfile_emit_failed",
}


def _load():
    return json.loads(DASHBOARD_PATH.read_text())


def test_dashboard_present_and_valid_json():
    assert DASHBOARD_PATH.is_file()
    _load()


def test_title_locked():
    assert _load()["title"] == "sovereign-os — selfdef systemd units (silent-failure detection)"


def test_uid_canonical():
    assert _load()["uid"] == "sovereign-os-selfdef-systemd-units"


def test_tags_include_canonical_markers():
    tags = set(_load()["tags"])
    for required in ("sovereign-os", "selfdef", "systemd-units",
                     "IPS-spine", "observability"):
        assert required in tags


def test_every_canonical_gauge_appears():
    exprs = " ".join(
        t.get("expr", "")
        for p in _load()["panels"]
        for t in p.get("targets", [])
    )
    for gauge in CANONICAL_GAUGES:
        assert gauge in exprs


def test_failed_panel_red_at_1():
    """Failed-units panel MUST be red at value=1 — any failure is
    page-worthy."""
    dash = _load()
    for panel in dash["panels"]:
        title = panel.get("title", "").lower()
        if "failed" not in title or "emit-failed" in title:
            continue
        steps = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("thresholds", {})
            .get("steps", [])
        )
        for s in steps:
            if s.get("color") == "red" and s.get("value") == 1:
                return
    raise AssertionError("failed-units panel must mark red at value=1")


def test_total_panel_yellow_at_8():
    """Total panel MUST mark yellow at value=8 (matches CountLow alert)."""
    dash = _load()
    for panel in dash["panels"]:
        if "total" not in panel.get("title", "").lower():
            continue
        steps = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("thresholds", {})
            .get("steps", [])
        )
        for s in steps:
            if s.get("color") == "yellow" and s.get("value") == 8:
                return
    raise AssertionError("total panel must mark yellow at value=8")


def test_per_state_timeseries_charts_all_5_states():
    dash = _load()
    for panel in dash["panels"]:
        if "per-state" not in panel.get("title", "").lower():
            continue
        exprs = " ".join(t.get("expr", "") for t in panel.get("targets", []))
        for state in ("active", "inactive", "failed", "activating", "other"):
            assert f"selfdef_systemd_units_{state}" in exprs, (
                f"per-state panel missing {state} gauge"
            )
        return
    raise AssertionError("dashboard missing per-state timeseries panel")


def test_refresh_30s():
    assert _load()["refresh"] == "30s"


def test_panel_count_locked():
    assert len(_load()["panels"]) == 8


def test_links_to_selfdef_producer():
    urls = " ".join(link.get("url", "") for link in _load().get("links", []))
    assert "selfdef-systemd-units-textfile.sh" in urls


def test_anchors_to_selfdef_producer_commit():
    assert "7121c72" in _load().get("_comment", "")
