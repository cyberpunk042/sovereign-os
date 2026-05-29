"""Selfdef apt/dpkg package-state Grafana dashboard — contract test."""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_PATH = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-selfdef-package-state.json"
)

CANONICAL_GAUGES = {
    "selfdef_apt_pending_security",
    "selfdef_dpkg_broken_packages",
    "selfdef_apt_update_age_days",
    "selfdef_apt_pending_total",
    "selfdef_dpkg_packages_total",
    "selfdef_package_state_textfile_emit_failed",
}


def _load():
    return json.loads(DASHBOARD_PATH.read_text())


def test_dashboard_present_and_valid_json():
    assert DASHBOARD_PATH.is_file()
    _load()


def test_title_locked():
    assert _load()["title"] == "sovereign-os — selfdef apt/dpkg package state (patch freshness)"


def test_uid_canonical():
    assert _load()["uid"] == "sovereign-os-selfdef-package-state"


def test_tags_include_patch_freshness_marker():
    tags = set(_load()["tags"])
    for required in ("sovereign-os", "selfdef", "package-state",
                     "apt", "dpkg", "IPS-spine", "security",
                     "patch-freshness"):
        assert required in tags


def test_every_canonical_gauge_appears():
    exprs = " ".join(
        t.get("expr", "")
        for p in _load()["panels"]
        for t in p.get("targets", [])
    )
    for gauge in CANONICAL_GAUGES:
        assert gauge in exprs


def test_security_panel_red_at_one():
    dash = _load()
    for panel in dash["panels"]:
        if "security updates pending" not in panel.get("title", "").lower():
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
    raise AssertionError("security-updates-pending panel must mark red at 1")


def test_apt_age_panel_yellow_at_7_red_at_30():
    dash = _load()
    for panel in dash["panels"]:
        if "apt-update age" not in panel.get("title", "").lower():
            continue
        steps = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("thresholds", {})
            .get("steps", [])
        )
        colors = {s.get("color"): s.get("value") for s in steps}
        assert colors.get("yellow") == 7
        assert colors.get("red") == 30
        return
    raise AssertionError("apt-update age panel missing thresholds")


def test_pending_panel_charts_both_total_and_security():
    dash = _load()
    for panel in dash["panels"]:
        if "pending upgrades" not in panel.get("title", "").lower():
            continue
        exprs = " ".join(t.get("expr", "") for t in panel.get("targets", []))
        assert "selfdef_apt_pending_total" in exprs
        assert "selfdef_apt_pending_security" in exprs
        return
    raise AssertionError("dashboard missing pending-upgrades multi-target panel")


def test_refresh_30s():
    assert _load()["refresh"] == "30s"


def test_default_window_is_7_days():
    """Patch state evolves over days, not minutes — wider default."""
    assert _load()["time"]["from"] == "now-7d"


def test_panel_count_locked():
    assert len(_load()["panels"]) == 7


def test_links_to_selfdef_producer():
    urls = " ".join(link.get("url", "") for link in _load().get("links", []))
    assert "selfdef-package-state-textfile.sh" in urls


def test_links_to_sshd_config_pair():
    urls = " ".join(link.get("url", "") for link in _load().get("links", []))
    assert "sshd-config" in urls


def test_anchors_to_selfdef_producer_commit():
    assert "0d05972" in _load().get("_comment", "")
