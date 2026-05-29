"""Selfdef nftables Grafana dashboard — contract test."""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_PATH = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-selfdef-nftables.json"
)

CANONICAL_GAUGES = {
    "selfdef_nftables_present",
    "selfdef_nftables_tables_total",
    "selfdef_nftables_chains_total",
    "selfdef_nftables_rules_total",
    "selfdef_conntrack_count",
    "selfdef_conntrack_max",
    "selfdef_conntrack_used_percent",
    "selfdef_nftables_textfile_emit_failed",
}


def _load():
    return json.loads(DASHBOARD_PATH.read_text())


def test_dashboard_present_and_valid_json():
    assert DASHBOARD_PATH.is_file()
    _load()


def test_title_locked():
    assert _load()["title"] == "sovereign-os — selfdef nftables + conntrack (kernel perimeter)"


def test_uid_canonical():
    assert _load()["uid"] == "sovereign-os-selfdef-nftables"


def test_tags_include_kernel_perimeter_marker():
    tags = set(_load()["tags"])
    for required in ("sovereign-os", "selfdef", "nftables", "conntrack",
                     "IPS-spine", "security", "kernel-perimeter"):
        assert required in tags


def test_every_canonical_gauge_appears():
    exprs = " ".join(
        t.get("expr", "")
        for p in _load()["panels"]
        for t in p.get("targets", [])
    )
    for gauge in CANONICAL_GAUGES:
        assert gauge in exprs


def test_rules_panel_red_at_zero():
    dash = _load()
    for panel in dash["panels"]:
        if "rules in ruleset" not in panel.get("title", "").lower():
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
    raise AssertionError("rules-in-ruleset panel must mark red at 0")


def test_conntrack_panel_yellow_at_75_red_at_90():
    dash = _load()
    for panel in dash["panels"]:
        if "conntrack used %" != panel.get("title", "").lower():
            continue
        steps = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("thresholds", {})
            .get("steps", [])
        )
        colors = {s.get("color"): s.get("value") for s in steps}
        assert colors.get("yellow") == 75
        assert colors.get("red") == 90
        return
    raise AssertionError("conntrack used % panel missing thresholds")


def test_ruleset_shape_panel_charts_all_three():
    dash = _load()
    for panel in dash["panels"]:
        if "ruleset shape" not in panel.get("title", "").lower():
            continue
        exprs = " ".join(t.get("expr", "") for t in panel.get("targets", []))
        for gauge in (
            "selfdef_nftables_tables_total",
            "selfdef_nftables_chains_total",
            "selfdef_nftables_rules_total",
        ):
            assert gauge in exprs
        return
    raise AssertionError("dashboard missing ruleset-shape timeseries panel")


def test_refresh_30s():
    assert _load()["refresh"] == "30s"


def test_panel_count_locked():
    assert len(_load()["panels"]) == 7


def test_links_to_selfdef_producer():
    urls = " ".join(link.get("url", "") for link in _load().get("links", []))
    assert "selfdef-nftables-textfile.sh" in urls


def test_links_to_fail2ban_pair():
    urls = " ".join(link.get("url", "") for link in _load().get("links", []))
    assert "fail2ban" in urls


def test_anchors_to_selfdef_producer_commit():
    assert "2c303c4" in _load().get("_comment", "")
