"""Selfdef SDD-067 revocations Grafana dashboard — contract test."""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_PATH = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-selfdef-revocations.json"
)

CANONICAL_GAUGES = {
    "selfdef_revocations_state_dir_present",
    "selfdef_revocations_active_count",
    "selfdef_revocations_pending_restores",
    "selfdef_revocations_textfile_emit_failed",
}


def _load():
    return json.loads(DASHBOARD_PATH.read_text())


def test_dashboard_present_and_valid_json():
    assert DASHBOARD_PATH.is_file()
    _load()


def test_title_locked():
    assert _load()["title"] == "sovereign-os — selfdef SDD-067 revocations (enforcement layer)"


def test_uid_canonical():
    assert _load()["uid"] == "sovereign-os-selfdef-revocations"


def test_tags_include_ips_trio_marker():
    tags = set(_load()["tags"])
    for required in ("sovereign-os", "selfdef", "revocations", "sdd-067",
                     "IPS-spine", "security", "enforcement-layer",
                     "ips-trio"):
        assert required in tags


def test_every_canonical_gauge_appears():
    exprs = " ".join(
        t.get("expr", "")
        for p in _load()["panels"]
        for t in p.get("targets", [])
    )
    for gauge in CANONICAL_GAUGES:
        assert gauge in exprs


def test_state_dir_panel_red_at_zero():
    dash = _load()
    for panel in dash["panels"]:
        if "state-dir present" not in panel.get("title", "").lower():
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
    raise AssertionError("state-dir panel must mark red at 0")


def test_active_panel_yellow_at_10():
    dash = _load()
    for panel in dash["panels"]:
        if "active revocations" not in panel.get("title", "").lower():
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
    raise AssertionError("active-revocations panel must mark yellow at 10")


def test_pending_panel_yellow_at_5():
    dash = _load()
    for panel in dash["panels"]:
        if "pending restore decisions" not in panel.get("title", "").lower():
            continue
        steps = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("thresholds", {})
            .get("steps", [])
        )
        for s in steps:
            if s.get("color") == "yellow" and s.get("value") == 5:
                return
    raise AssertionError("pending panel must mark yellow at 5")


def test_active_vs_pending_panel_charts_both():
    dash = _load()
    for panel in dash["panels"]:
        if "active vs pending-restores" not in panel.get("title", "").lower():
            continue
        exprs = " ".join(t.get("expr", "") for t in panel.get("targets", []))
        assert "selfdef_revocations_active_count" in exprs
        assert "selfdef_revocations_pending_restores" in exprs
        return
    raise AssertionError("dashboard missing active-vs-pending timeseries panel")


def test_refresh_30s():
    assert _load()["refresh"] == "30s"


def test_panel_count_locked():
    assert len(_load()["panels"]) == 6


def test_links_to_sdd_067_spec():
    urls = " ".join(link.get("url", "") for link in _load().get("links", []))
    assert "067-session-revocation-action-surface" in urls


def test_links_to_both_trio_pair_dashboards():
    urls = " ".join(link.get("url", "") for link in _load().get("links", []))
    assert "blockset" in urls
    assert "quarantine" in urls


def test_anchors_to_selfdef_producer_commit():
    assert "6f3f19d" in _load().get("_comment", "")
