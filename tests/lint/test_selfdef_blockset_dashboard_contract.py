"""Selfdef SDD-065 blockset Grafana dashboard — contract test."""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_PATH = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-selfdef-blockset.json"
)

CANONICAL_GAUGES = {
    "selfdef_blockset_present",
    "selfdef_blockset_v4_count",
    "selfdef_blockset_v6_count",
    "selfdef_blockset_total_count",
    "selfdef_blockset_oldest_expiry_unix",
    "selfdef_blockset_textfile_emit_failed",
}


def _load():
    return json.loads(DASHBOARD_PATH.read_text())


def test_dashboard_present_and_valid_json():
    assert DASHBOARD_PATH.is_file()
    _load()


def test_title_locked():
    assert _load()["title"] == "sovereign-os — selfdef SDD-065 blockset (enforcement layer)"


def test_uid_canonical():
    assert _load()["uid"] == "sovereign-os-selfdef-blockset"


def test_tags_include_enforcement_layer_marker():
    tags = set(_load()["tags"])
    for required in ("sovereign-os", "selfdef", "blockset", "sdd-065",
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


def test_present_panel_red_at_zero():
    dash = _load()
    for panel in dash["panels"]:
        if "table present" not in panel.get("title", "").lower():
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
    raise AssertionError("table-present panel must mark red at 0")


def test_total_panel_yellow_at_1000():
    dash = _load()
    for panel in dash["panels"]:
        if "total blocks" not in panel.get("title", "").lower():
            continue
        steps = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("thresholds", {})
            .get("steps", [])
        )
        for s in steps:
            if s.get("color") == "yellow" and s.get("value") == 1000:
                return
    raise AssertionError("total-blocks panel must mark yellow at 1000")


def test_entries_panel_charts_v4_v6_and_total():
    dash = _load()
    for panel in dash["panels"]:
        if "blockset entries" not in panel.get("title", "").lower():
            continue
        exprs = " ".join(t.get("expr", "") for t in panel.get("targets", []))
        for gauge in ("selfdef_blockset_v4_count",
                      "selfdef_blockset_v6_count",
                      "selfdef_blockset_total_count"):
            assert gauge in exprs
        return
    raise AssertionError("dashboard missing blockset-entries timeseries panel")


def test_refresh_30s():
    assert _load()["refresh"] == "30s"


def test_panel_count_locked():
    assert len(_load()["panels"]) == 6


def test_links_to_sdd_065_spec():
    urls = " ".join(link.get("url", "") for link in _load().get("links", []))
    assert "065-ip-block-action-surface" in urls


def test_links_to_nftables_pair():
    urls = " ".join(link.get("url", "") for link in _load().get("links", []))
    assert "nftables" in urls


def test_anchors_to_selfdef_producer_commit():
    assert "39e091f" in _load().get("_comment", "")
