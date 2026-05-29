"""Selfdef time-sync Grafana dashboard — contract test."""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_PATH = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-selfdef-time-sync.json"
)

CANONICAL_GAUGES = {
    "selfdef_time_sync_synced",
    "selfdef_time_sync_ntp_active",
    "selfdef_time_sync_rtc_local_tz",
    "selfdef_time_sync_drift_seconds",
    "selfdef_time_sync_textfile_emit_failed",
}


def _load():
    return json.loads(DASHBOARD_PATH.read_text())


def test_dashboard_present_and_valid_json():
    assert DASHBOARD_PATH.is_file()
    _load()


def test_title_locked():
    assert _load()["title"] == "sovereign-os — selfdef time sync (clock-drift detection)"


def test_uid_canonical():
    assert _load()["uid"] == "sovereign-os-selfdef-time-sync"


def test_tags_canonical():
    tags = set(_load()["tags"])
    for required in ("sovereign-os", "selfdef", "time-sync", "IPS-spine"):
        assert required in tags


def test_every_canonical_gauge_appears():
    exprs = " ".join(
        t.get("expr", "")
        for p in _load()["panels"]
        for t in p.get("targets", [])
    )
    for gauge in CANONICAL_GAUGES:
        assert gauge in exprs


def test_drift_panel_yellow_at_60s():
    dash = _load()
    for panel in dash["panels"]:
        if "drift" not in panel.get("title", "").lower():
            continue
        steps = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("thresholds", {})
            .get("steps", [])
        )
        for s in steps:
            if s.get("color") == "yellow" and s.get("value") == 60:
                return
    raise AssertionError("drift panel must mark yellow at 60s")


def test_synced_panel_red_at_0():
    dash = _load()
    for panel in dash["panels"]:
        if "synced" not in panel.get("title", "").lower():
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
    raise AssertionError("synced panel must mark red at 0")


def test_state_timeseries_charts_all_3_binary_gauges():
    dash = _load()
    for panel in dash["panels"]:
        title = panel.get("title", "").lower()
        if "sync + ntp + rtc" not in title:
            continue
        exprs = " ".join(t.get("expr", "") for t in panel.get("targets", []))
        for gauge in (
            "selfdef_time_sync_synced",
            "selfdef_time_sync_ntp_active",
            "selfdef_time_sync_rtc_local_tz",
        ):
            assert gauge in exprs
        return
    raise AssertionError("dashboard missing 3-state timeseries panel")


def test_refresh_30s():
    assert _load()["refresh"] == "30s"


def test_panel_count_locked():
    assert len(_load()["panels"]) == 7


def test_links_to_selfdef_producer():
    urls = " ".join(link.get("url", "") for link in _load().get("links", []))
    assert "selfdef-time-sync-textfile.sh" in urls


def test_anchors_to_selfdef_producer_commit():
    assert "36d1c8f" in _load().get("_comment", "")
