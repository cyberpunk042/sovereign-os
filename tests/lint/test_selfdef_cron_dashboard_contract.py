"""Selfdef cron + systemd-timer Grafana dashboard — contract test."""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_PATH = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-selfdef-cron.json"
)

CANONICAL_GAUGES = {
    "selfdef_cron_d_files",
    "selfdef_cron_periodic_files",
    "selfdef_cron_user_crontabs",
    "selfdef_cron_total_entries",
    "selfdef_systemd_timers_total",
    "selfdef_cron_textfile_emit_failed",
}


def _load():
    return json.loads(DASHBOARD_PATH.read_text())


def test_dashboard_present_and_valid_json():
    assert DASHBOARD_PATH.is_file()
    _load()


def test_title_locked():
    assert _load()["title"] == "sovereign-os — selfdef cron + systemd timers (persistence detection)"


def test_uid_canonical():
    assert _load()["uid"] == "sovereign-os-selfdef-cron"


def test_tags_include_persistence_detection_marker():
    tags = set(_load()["tags"])
    for required in ("sovereign-os", "selfdef", "cron", "systemd-timers",
                     "IPS-spine", "security", "persistence-detection"):
        assert required in tags


def test_every_canonical_gauge_appears():
    exprs = " ".join(
        t.get("expr", "")
        for p in _load()["panels"]
        for t in p.get("targets", [])
    )
    for gauge in CANONICAL_GAUGES:
        assert gauge in exprs


def test_drift_detector_panel_uses_changes_function():
    dash = _load()
    for panel in dash["panels"]:
        if "drift detector" not in panel.get("title", "").lower():
            continue
        exprs = " ".join(t.get("expr", "") for t in panel.get("targets", []))
        assert "changes(" in exprs
        assert "[1h])" in exprs
        return
    raise AssertionError("dashboard missing drift-detector changes() panel")


def test_surface_inventory_panel_charts_all_four_surfaces():
    dash = _load()
    for panel in dash["panels"]:
        if "surface inventory" not in panel.get("title", "").lower():
            continue
        exprs = " ".join(t.get("expr", "") for t in panel.get("targets", []))
        for gauge in (
            "selfdef_cron_d_files",
            "selfdef_cron_periodic_files",
            "selfdef_cron_user_crontabs",
            "selfdef_systemd_timers_total",
        ):
            assert gauge in exprs
        return
    raise AssertionError("dashboard missing cron-surface inventory panel")


def test_refresh_30s():
    assert _load()["refresh"] == "30s"


def test_panel_count_locked():
    assert len(_load()["panels"]) == 7


def test_links_to_selfdef_producer():
    urls = " ".join(link.get("url", "") for link in _load().get("links", []))
    assert "selfdef-cron-textfile.sh" in urls


def test_links_to_kernel_modules_pair():
    """The persistence-detection dashboard MUST link to kernel-modules
    (paired rootkit-detection dashboard) for IPS-pair correlation."""
    urls = " ".join(link.get("url", "") for link in _load().get("links", []))
    assert "kernel-modules" in urls


def test_anchors_to_selfdef_producer_commit():
    assert "b80b389" in _load().get("_comment", "")
