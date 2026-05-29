"""Selfdef AppArmor Grafana dashboard — contract test."""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_PATH = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-selfdef-apparmor.json"
)

CANONICAL_GAUGES = {
    "selfdef_apparmor_profile_loaded",
    "selfdef_apparmor_profile_enforce",
    "selfdef_apparmor_profile_complain",
    "selfdef_apparmor_profiles_loaded_total",
    "selfdef_apparmor_textfile_emit_failed",
}


def _load():
    return json.loads(DASHBOARD_PATH.read_text())


def _all_exprs(dash):
    return " ".join(
        t.get("expr", "")
        for p in dash["panels"]
        for t in p.get("targets", [])
    )


def test_dashboard_present_and_valid_json():
    assert DASHBOARD_PATH.is_file()
    _load()


def test_title_locked():
    assert _load()["title"] == "sovereign-os — selfdef AppArmor enforcement"


def test_uid_canonical():
    assert _load()["uid"] == "sovereign-os-selfdef-apparmor"


def test_tags_include_ips_spine_marker():
    tags = set(_load()["tags"])
    for required in ("sovereign-os", "selfdef", "apparmor", "IPS-spine"):
        assert required in tags


def test_every_canonical_gauge_appears():
    exprs = _all_exprs(_load())
    for gauge in CANONICAL_GAUGES:
        assert gauge in exprs, f"missing {gauge}"


def test_complain_mode_panel_red_at_1():
    """The complain-mode stat panel MUST be red at value=1 (operator
    drift hazard) — distinct from loaded/enforce which are red at 0."""
    dash = _load()
    for panel in dash["panels"]:
        if "complain" not in panel.get("title", "").lower():
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
    raise AssertionError(
        "complain-mode panel must mark red at value=1 (drift hazard)"
    )


def test_loaded_panel_red_at_0():
    """Loaded panel MUST be red at value=0 (profile absent =
    posture compromised)."""
    dash = _load()
    for panel in dash["panels"]:
        if "loaded" not in panel.get("title", "").lower():
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
    raise AssertionError("loaded panel must mark red at value=0")


def test_enforce_panel_red_at_0():
    dash = _load()
    for panel in dash["panels"]:
        if "enforce" not in panel.get("title", "").lower():
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
    raise AssertionError("enforce panel must mark red at value=0")


def test_profile_state_timeseries_charts_all_three():
    """The profile-state timeseries MUST chart all 3 per-profile
    gauges (loaded + enforce + complain) so operators see the
    correlated state transitions."""
    dash = _load()
    for panel in dash["panels"]:
        if "profile state over time" not in panel.get("title", "").lower():
            continue
        exprs = " ".join(t.get("expr", "") for t in panel.get("targets", []))
        assert "selfdef_apparmor_profile_loaded" in exprs
        assert "selfdef_apparmor_profile_enforce" in exprs
        assert "selfdef_apparmor_profile_complain" in exprs
        return
    raise AssertionError("dashboard missing profile-state timeseries panel")


def test_refresh_30s():
    assert _load()["refresh"] == "30s"


def test_panel_count_locked():
    assert len(_load()["panels"]) == 7


def test_links_to_selfdef_producer():
    urls = " ".join(link.get("url", "") for link in _load().get("links", []))
    assert "selfdef-apparmor-textfile.sh" in urls


def test_anchors_to_selfdef_producer_commit():
    assert "4680ed8" in _load().get("_comment", "")
