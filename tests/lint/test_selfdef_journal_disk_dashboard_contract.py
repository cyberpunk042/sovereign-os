"""Selfdef systemd-journal disk-usage Grafana dashboard — contract test."""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_PATH = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-selfdef-journal-disk.json"
)

CANONICAL_GAUGES = {
    "selfdef_journal_bytes_total",
    "selfdef_journal_persistent",
    "selfdef_journal_volatile",
    "selfdef_journal_available",
    "selfdef_journal_disk_textfile_emit_failed",
}


def _load():
    return json.loads(DASHBOARD_PATH.read_text())


def test_dashboard_present_and_valid_json():
    assert DASHBOARD_PATH.is_file()
    _load()


def test_title_locked():
    assert _load()["title"] == "sovereign-os — selfdef systemd-journal disk usage"


def test_uid_canonical():
    assert _load()["uid"] == "sovereign-os-selfdef-journal-disk"


def test_tags_include_forensic_trail_marker():
    tags = set(_load()["tags"])
    for required in ("sovereign-os", "selfdef", "journal", "systemd",
                     "IPS-spine", "operational-disk", "forensic-trail"):
        assert required in tags


def test_every_canonical_gauge_appears():
    exprs = " ".join(
        t.get("expr", "")
        for p in _load()["panels"]
        for t in p.get("targets", [])
    )
    for gauge in CANONICAL_GAUGES:
        assert gauge in exprs


def test_disk_usage_panel_thresholds_match_alerts():
    """Yellow at 1 GiB (alert High), red at 5 GiB (alert Runaway)."""
    dash = _load()
    for panel in dash["panels"]:
        if panel.get("title", "").lower() != "journal disk usage":
            continue
        steps = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("thresholds", {})
            .get("steps", [])
        )
        colors = {s.get("color"): s.get("value") for s in steps}
        assert colors.get("yellow") == 1073741824
        assert colors.get("red") == 5368709120
        return
    raise AssertionError("journal-disk-usage panel missing thresholds")


def test_persistent_panel_red_at_zero():
    dash = _load()
    for panel in dash["panels"]:
        if "persistent journal" not in panel.get("title", "").lower():
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
    raise AssertionError("persistent-journal panel must mark red at 0")


def test_mode_toggles_panel_charts_all_three():
    dash = _load()
    for panel in dash["panels"]:
        if "mode toggles" not in panel.get("title", "").lower():
            continue
        exprs = " ".join(t.get("expr", "") for t in panel.get("targets", []))
        for gauge in ("selfdef_journal_persistent",
                      "selfdef_journal_volatile",
                      "selfdef_journal_available"):
            assert gauge in exprs
        return
    raise AssertionError("dashboard missing journal-mode-toggles panel")


def test_refresh_30s():
    assert _load()["refresh"] == "30s"


def test_default_window_24h():
    """Log-spam runaway evolves over hours, not minutes — wider default."""
    assert _load()["time"]["from"] == "now-24h"


def test_panel_count_locked():
    assert len(_load()["panels"]) == 5


def test_links_to_selfdef_producer():
    urls = " ".join(link.get("url", "") for link in _load().get("links", []))
    assert "selfdef-journal-disk-textfile.sh" in urls


def test_links_to_disk_usage_pair():
    urls = " ".join(link.get("url", "") for link in _load().get("links", []))
    assert "disk-usage" in urls


def test_anchors_to_selfdef_producer_commit():
    assert "ec6a822" in _load().get("_comment", "")
