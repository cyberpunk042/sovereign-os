"""Selfdef listening-sockets Grafana dashboard — contract test."""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_PATH = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-selfdef-listening-sockets.json"
)

CANONICAL_GAUGES = {
    "selfdef_listening_sockets_tcp",
    "selfdef_listening_sockets_tcp6",
    "selfdef_listening_sockets_udp",
    "selfdef_listening_sockets_udp6",
    "selfdef_listening_sockets_total",
    "selfdef_listening_sockets_textfile_emit_failed",
}


def _load():
    return json.loads(DASHBOARD_PATH.read_text())


def test_dashboard_present_and_valid_json():
    assert DASHBOARD_PATH.is_file()
    _load()


def test_title_locked():
    assert _load()["title"] == "sovereign-os — selfdef listening sockets (backdoor detection)"


def test_uid_canonical():
    assert _load()["uid"] == "sovereign-os-selfdef-listening-sockets"


def test_tags_include_security_marker():
    tags = set(_load()["tags"])
    for required in ("sovereign-os", "selfdef", "listening-sockets",
                     "IPS-spine", "security"):
        assert required in tags


def test_every_canonical_gauge_appears():
    exprs = " ".join(
        t.get("expr", "")
        for p in _load()["panels"]
        for t in p.get("targets", [])
    )
    for gauge in CANONICAL_GAUGES:
        assert gauge in exprs


def test_per_protocol_timeseries_charts_all_4():
    dash = _load()
    for panel in dash["panels"]:
        if "per-protocol" not in panel.get("title", "").lower():
            continue
        exprs = " ".join(t.get("expr", "") for t in panel.get("targets", []))
        for proto in ("tcp", "tcp6", "udp", "udp6"):
            assert f"selfdef_listening_sockets_{proto}" in exprs, (
                f"per-protocol panel missing {proto} gauge"
            )
        return
    raise AssertionError("dashboard missing per-protocol timeseries panel")


def test_total_panel_yellow_at_15_red_at_20():
    """Total panel MUST mark yellow + red thresholds matching alert."""
    dash = _load()
    for panel in dash["panels"]:
        if "total" not in panel.get("title", "").lower():
            continue
        steps = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("thresholds", {})
            .get("steps", [])
        )
        values = {(s.get("color"), s.get("value")) for s in steps}
        # Either ("yellow", 15) AND ("red", 20) must both appear.
        if ("yellow", 15) in values and ("red", 20) in values:
            return
    raise AssertionError("total panel must mark yellow@15 + red@20")


def test_tcp_panel_red_at_0():
    """TCP panel MUST be red at value=0 (matches ZeroTcp alert)."""
    dash = _load()
    for panel in dash["panels"]:
        title = panel.get("title", "").lower()
        if "tcp listeners" not in title and "tcp listener count" not in title:
            continue
        exprs = " ".join(t.get("expr", "") for t in panel.get("targets", []))
        if "selfdef_listening_sockets_tcp" not in exprs:
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
    raise AssertionError("TCP panel must mark red at value=0 (ZeroTcp)")


def test_refresh_30s():
    assert _load()["refresh"] == "30s"


def test_panel_count_locked():
    assert len(_load()["panels"]) == 8


def test_links_to_selfdef_producer():
    urls = " ".join(link.get("url", "") for link in _load().get("links", []))
    assert "selfdef-listening-sockets-textfile.sh" in urls


def test_anchors_to_selfdef_producer_commit():
    assert "ca3cad1" in _load().get("_comment", "")
