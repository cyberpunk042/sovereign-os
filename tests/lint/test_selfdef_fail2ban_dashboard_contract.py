"""Selfdef fail2ban Grafana dashboard — contract test."""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_PATH = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-selfdef-fail2ban.json"
)

CANONICAL_GAUGES = {
    "selfdef_fail2ban_server_alive",
    "selfdef_fail2ban_jails_active",
    "selfdef_fail2ban_jail_current_bans",
    "selfdef_fail2ban_jail_total_bans",
    "selfdef_fail2ban_current_bans_sum",
    "selfdef_fail2ban_total_bans_sum",
    "selfdef_fail2ban_textfile_emit_failed",
}


def _load():
    return json.loads(DASHBOARD_PATH.read_text())


def test_dashboard_present_and_valid_json():
    assert DASHBOARD_PATH.is_file()
    _load()


def test_title_locked():
    assert _load()["title"] == "sovereign-os — selfdef fail2ban (defensive-response)"


def test_uid_canonical():
    assert _load()["uid"] == "sovereign-os-selfdef-fail2ban"


def test_tags_include_defensive_response_marker():
    tags = set(_load()["tags"])
    for required in ("sovereign-os", "selfdef", "fail2ban",
                     "IPS-spine", "security", "defensive-response"):
        assert required in tags


def test_every_canonical_gauge_appears():
    exprs = " ".join(
        t.get("expr", "")
        for p in _load()["panels"]
        for t in p.get("targets", [])
    )
    for gauge in CANONICAL_GAUGES:
        assert gauge in exprs


def test_server_panel_red_at_zero():
    dash = _load()
    for panel in dash["panels"]:
        if "fail2ban server" not in panel.get("title", "").lower():
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
    raise AssertionError("fail2ban-server panel must mark red at value=0")


def test_active_bans_panel_yellow_at_50():
    dash = _load()
    for panel in dash["panels"]:
        if "currently banned" != panel.get("title", "").lower():
            continue
        steps = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("thresholds", {})
            .get("steps", [])
        )
        for s in steps:
            if s.get("color") == "yellow" and s.get("value") == 50:
                return
    raise AssertionError("currently-banned panel must mark yellow at 50")


def test_per_jail_timeseries_panel_present():
    dash = _load()
    for panel in dash["panels"]:
        if "per jail" not in panel.get("title", "").lower():
            continue
        exprs = " ".join(t.get("expr", "") for t in panel.get("targets", []))
        assert "selfdef_fail2ban_jail_current_bans" in exprs
        legends = " ".join(t.get("legendFormat", "") for t in panel.get("targets", []))
        assert "{{jail}}" in legends
        return
    raise AssertionError("dashboard missing per-jail current-bans timeseries panel")


def test_refresh_30s():
    assert _load()["refresh"] == "30s"


def test_panel_count_locked():
    assert len(_load()["panels"]) == 8


def test_links_to_selfdef_producer():
    urls = " ".join(link.get("url", "") for link in _load().get("links", []))
    assert "selfdef-fail2ban-textfile.sh" in urls


def test_links_to_auth_events_pair():
    """The defensive-response dashboard MUST link to the auth-events
    (attack-detection) dashboard for IPS-pair correlation."""
    urls = " ".join(link.get("url", "") for link in _load().get("links", []))
    assert "auth-events" in urls


def test_anchors_to_selfdef_producer_commit():
    assert "098a45a" in _load().get("_comment", "")
