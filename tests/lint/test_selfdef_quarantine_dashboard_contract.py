"""Selfdef SDD-066 quarantine Grafana dashboard — contract test."""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_PATH = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-selfdef-quarantine.json"
)

CANONICAL_GAUGES = {
    "selfdef_quarantine_slice_present",
    "selfdef_quarantine_active_count",
    "selfdef_quarantine_frozen_count",
    "selfdef_quarantine_oldest_expiry_unix",
    "selfdef_quarantine_textfile_emit_failed",
}


def _load():
    return json.loads(DASHBOARD_PATH.read_text())


def test_dashboard_present_and_valid_json():
    assert DASHBOARD_PATH.is_file()
    _load()


def test_title_locked():
    assert _load()["title"] == "sovereign-os — selfdef SDD-066 quarantine (enforcement layer)"


def test_uid_canonical():
    assert _load()["uid"] == "sovereign-os-selfdef-quarantine"


def test_tags_include_enforcement_layer_marker():
    tags = set(_load()["tags"])
    for required in ("sovereign-os", "selfdef", "quarantine", "sdd-066",
                     "IPS-spine", "security", "enforcement-layer"):
        assert required in tags


def test_every_canonical_gauge_appears():
    exprs = " ".join(
        t.get("expr", "")
        for p in _load()["panels"]
        for t in p.get("targets", [])
    )
    for gauge in CANONICAL_GAUGES:
        assert gauge in exprs


def test_slice_panel_red_at_zero():
    dash = _load()
    for panel in dash["panels"]:
        if "slice present" not in panel.get("title", "").lower():
            continue
        steps = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("thresholds", {})
            .get("steps", [])
        )
        for s in steps:
            if s.get("color") == "red" and s.get("value") == 0:
                return
    raise AssertionError("slice-present panel must mark red at 0")


def test_active_panel_yellow_at_10():
    dash = _load()
    for panel in dash["panels"]:
        if "active quarantines" not in panel.get("title", "").lower():
            continue
        steps = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("thresholds", {})
            .get("steps", [])
        )
        for s in steps:
            if s.get("color") == "yellow" and s.get("value") == 10:
                return
    raise AssertionError("active-quarantines panel must mark yellow at 10")


def test_active_vs_frozen_panel_charts_both():
    dash = _load()
    for panel in dash["panels"]:
        if "active vs frozen" not in panel.get("title", "").lower():
            continue
        exprs = " ".join(t.get("expr", "") for t in panel.get("targets", []))
        assert "selfdef_quarantine_active_count" in exprs
        assert "selfdef_quarantine_frozen_count" in exprs
        return
    raise AssertionError("dashboard missing active-vs-frozen timeseries panel")


def test_refresh_30s():
    assert _load()["refresh"] == "30s"


def test_panel_count_locked():
    assert len(_load()["panels"]) == 6


def test_links_to_sdd_066_spec():
    urls = " ".join(link.get("url", "") for link in _load().get("links", []))
    assert "066-process-quarantine-action-surface" in urls


def test_links_to_blockset_pair():
    urls = " ".join(link.get("url", "") for link in _load().get("links", []))
    assert "blockset" in urls


def test_anchors_to_selfdef_producer_commit():
    assert "55a3c33" in _load().get("_comment", "")
