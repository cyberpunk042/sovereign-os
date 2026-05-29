"""Selfdef disk-usage Grafana dashboard — contract test."""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_PATH = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-selfdef-disk-usage.json"
)

CANONICAL_GAUGES = {
    "selfdef_disk_usage_lib_bytes",
    "selfdef_disk_usage_log_bytes",
    "selfdef_disk_usage_var_log_bytes",
    "selfdef_disk_usage_textfile_collector_bytes",
    "selfdef_disk_usage_var_free_bytes",
    "selfdef_disk_usage_var_used_percent",
    "selfdef_disk_usage_textfile_emit_failed",
}


def _load():
    return json.loads(DASHBOARD_PATH.read_text())


def test_dashboard_present_and_valid_json():
    assert DASHBOARD_PATH.is_file()
    _load()


def test_title_locked():
    assert _load()["title"] == "sovereign-os — selfdef disk usage (disk-fill detection)"


def test_uid_canonical():
    assert _load()["uid"] == "sovereign-os-selfdef-disk-usage"


def test_tags_canonical():
    tags = set(_load()["tags"])
    for required in ("sovereign-os", "selfdef", "disk-usage", "IPS-spine"):
        assert required in tags


def test_every_canonical_gauge_appears():
    exprs = " ".join(
        t.get("expr", "")
        for p in _load()["panels"]
        for t in p.get("targets", [])
    )
    for gauge in CANONICAL_GAUGES:
        assert gauge in exprs


def test_used_percent_panel_yellow_75_red_90():
    """Used-% panel must mark yellow at 75 + red at 90 (matches
    VarApproaching + VarHigh alert thresholds)."""
    dash = _load()
    for panel in dash["panels"]:
        if "used %" not in panel.get("title", "").lower():
            continue
        steps = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("thresholds", {})
            .get("steps", [])
        )
        values = {(s.get("color"), s.get("value")) for s in steps}
        if ("yellow", 75) in values and ("red", 90) in values:
            return
    raise AssertionError("used % panel must mark yellow@75 + red@90")


def test_selfdef_log_panel_yellow_at_5_gib():
    """selfdef-log size panel MUST be yellow at 5 GiB (5368709120)."""
    dash = _load()
    for panel in dash["panels"]:
        title = panel.get("title", "")
        if "selfdef" not in title.lower() and "log/selfdef" not in title.lower():
            continue
        steps = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("thresholds", {})
            .get("steps", [])
        )
        for s in steps:
            if s.get("color") == "yellow" and s.get("value") == 5368709120:
                return
    raise AssertionError("selfdef-log panel must mark yellow at 5 GiB (5368709120)")


def test_per_directory_timeseries_charts_all_4():
    dash = _load()
    for panel in dash["panels"]:
        if "per-directory" not in panel.get("title", "").lower():
            continue
        exprs = " ".join(t.get("expr", "") for t in panel.get("targets", []))
        for gauge in (
            "selfdef_disk_usage_lib_bytes",
            "selfdef_disk_usage_log_bytes",
            "selfdef_disk_usage_var_log_bytes",
            "selfdef_disk_usage_textfile_collector_bytes",
        ):
            assert gauge in exprs, f"per-directory panel missing {gauge}"
        return
    raise AssertionError("dashboard missing per-directory timeseries panel")


def test_refresh_30s():
    assert _load()["refresh"] == "30s"


def test_panel_count_locked():
    assert len(_load()["panels"]) == 8


def test_links_to_selfdef_producer():
    urls = " ".join(link.get("url", "") for link in _load().get("links", []))
    assert "selfdef-disk-usage-textfile.sh" in urls


def test_anchors_to_selfdef_producer_commit():
    assert "694b611" in _load().get("_comment", "")
