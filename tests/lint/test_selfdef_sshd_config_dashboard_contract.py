"""Selfdef sshd-config hardening Grafana dashboard — contract test."""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_PATH = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-selfdef-sshd-config.json"
)

CANONICAL_GAUGES = {
    "selfdef_sshd_permit_root_login",
    "selfdef_sshd_permit_empty_passwords",
    "selfdef_sshd_password_authentication",
    "selfdef_sshd_challenge_response",
    "selfdef_sshd_x11_forwarding",
    "selfdef_sshd_use_pam",
    "selfdef_sshd_protocol_v2_only",
    "selfdef_sshd_config_hash",
    "selfdef_sshd_config_textfile_emit_failed",
}


def _load():
    return json.loads(DASHBOARD_PATH.read_text())


def test_dashboard_present_and_valid_json():
    assert DASHBOARD_PATH.is_file()
    _load()


def test_title_locked():
    assert _load()["title"] == "sovereign-os — selfdef sshd-config (SSH hardening baseline)"


def test_uid_canonical():
    assert _load()["uid"] == "sovereign-os-selfdef-sshd-config"


def test_tags_include_attack_surface_marker():
    tags = set(_load()["tags"])
    for required in ("sovereign-os", "selfdef", "sshd-config",
                     "IPS-spine", "security", "attack-surface"):
        assert required in tags


def test_every_canonical_gauge_appears():
    exprs = " ".join(
        t.get("expr", "")
        for p in _load()["panels"]
        for t in p.get("targets", [])
    )
    for gauge in CANONICAL_GAUGES:
        assert gauge in exprs


def test_permit_root_login_panel_red_at_one():
    dash = _load()
    for panel in dash["panels"]:
        if "permitrootlogin" not in panel.get("title", "").lower():
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
    raise AssertionError("PermitRootLogin panel must mark red at 1")


def test_password_auth_panel_yellow_at_one():
    """PasswordAuthentication is warning-level (fail2ban mitigates),
    not critical — so yellow, not red."""
    dash = _load()
    for panel in dash["panels"]:
        if "passwordauthentication" not in panel.get("title", "").lower():
            continue
        steps = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("thresholds", {})
            .get("steps", [])
        )
        for s in steps:
            if s.get("color") == "yellow" and s.get("value") == 1:
                return
    raise AssertionError("PasswordAuthentication panel must mark yellow at 1")


def test_hazard_panel_charts_all_five_hazards():
    dash = _load()
    for panel in dash["panels"]:
        if "hazard toggles" not in panel.get("title", "").lower():
            continue
        exprs = " ".join(t.get("expr", "") for t in panel.get("targets", []))
        for gauge in (
            "selfdef_sshd_permit_root_login",
            "selfdef_sshd_permit_empty_passwords",
            "selfdef_sshd_password_authentication",
            "selfdef_sshd_challenge_response",
            "selfdef_sshd_x11_forwarding",
        ):
            assert gauge in exprs
        return
    raise AssertionError("dashboard missing hazard-toggles timeseries panel")


def test_refresh_30s():
    assert _load()["refresh"] == "30s"


def test_panel_count_locked():
    assert len(_load()["panels"]) == 7


def test_links_to_selfdef_producer():
    urls = " ".join(link.get("url", "") for link in _load().get("links", []))
    assert "selfdef-sshd-config-textfile.sh" in urls


def test_links_to_auth_events_pair():
    urls = " ".join(link.get("url", "") for link in _load().get("links", []))
    assert "auth-events" in urls


def test_anchors_to_selfdef_producer_commit():
    assert "c86e4e4" in _load().get("_comment", "")
