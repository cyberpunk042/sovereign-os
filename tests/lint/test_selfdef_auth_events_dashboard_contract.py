"""Selfdef auth-events Grafana dashboard — contract test."""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_PATH = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-selfdef-auth-events.json"
)

CANONICAL_GAUGES = {
    "selfdef_auth_events_login_failures",
    "selfdef_auth_events_login_successes",
    "selfdef_auth_events_sudo_invocations",
    "selfdef_auth_events_ssh_invalid_users",
    "selfdef_auth_events_ssh_refused_keys",
    "selfdef_auth_events_total",
    "selfdef_auth_events_textfile_emit_failed",
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
    assert _load()["title"] == "sovereign-os — selfdef auth events (brute-force detection)"


def test_uid_canonical():
    assert _load()["uid"] == "sovereign-os-selfdef-auth-events"


def test_tags_include_security_marker():
    """security tag is canonical for this dashboard since brute-force
    detection is the headline feature."""
    tags = set(_load()["tags"])
    for required in ("sovereign-os", "selfdef", "auth-events",
                     "IPS-spine", "security"):
        assert required in tags


def test_every_canonical_gauge_appears():
    exprs = _all_exprs(_load())
    for gauge in CANONICAL_GAUGES:
        assert gauge in exprs


def test_brute_force_threshold_at_20_on_failures_panel():
    dash = _load()
    for panel in dash["panels"]:
        if "login failures" not in panel.get("title", "").lower():
            continue
        steps = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("thresholds", {})
            .get("steps", [])
        )
        for s in steps:
            if s.get("color") == "red" and s.get("value") == 20:
                return
    raise AssertionError("login-failures panel must mark red at 20")


def test_ssh_invalid_users_threshold_at_5():
    dash = _load()
    for panel in dash["panels"]:
        if "ssh invalid" not in panel.get("title", "").lower():
            continue
        steps = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("thresholds", {})
            .get("steps", [])
        )
        for s in steps:
            if s.get("color") == "red" and s.get("value") == 5:
                return
    raise AssertionError("ssh-invalid-users panel must mark red at 5")


def test_sudo_threshold_at_10():
    dash = _load()
    for panel in dash["panels"]:
        if "sudo" not in panel.get("title", "").lower():
            continue
        steps = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("thresholds", {})
            .get("steps", [])
        )
        for s in steps:
            if s.get("color") == "red" and s.get("value") == 10:
                return
    raise AssertionError("sudo-invocations panel must mark red at 10")


def test_failures_vs_successes_timeseries_present():
    """The failures-vs-successes timeseries MUST chart both gauges
    side-by-side — that's the brute-force signature pattern."""
    dash = _load()
    for panel in dash["panels"]:
        title = panel.get("title", "").lower()
        if "failures vs successes" not in title:
            continue
        exprs = " ".join(t.get("expr", "") for t in panel.get("targets", []))
        assert "selfdef_auth_events_login_failures" in exprs
        assert "selfdef_auth_events_login_successes" in exprs
        return
    raise AssertionError("dashboard missing failures-vs-successes panel")


def test_refresh_30s():
    assert _load()["refresh"] == "30s"


def test_panel_count_locked():
    assert len(_load()["panels"]) == 8


def test_links_to_selfdef_producer():
    urls = " ".join(link.get("url", "") for link in _load().get("links", []))
    assert "selfdef-auth-events-textfile.sh" in urls


def test_anchors_to_selfdef_producer_commit():
    assert "e73dc61" in _load().get("_comment", "")
