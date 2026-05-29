"""Selfdef kernel-modules Grafana dashboard — contract test."""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_PATH = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-selfdef-kernel-modules.json"
)

CANONICAL_GAUGES = {
    "selfdef_kernel_modules_total",
    "selfdef_kernel_modules_in_use",
    "selfdef_kernel_tainted",
    "selfdef_kernel_tainted_proprietary",
    "selfdef_kernel_tainted_unsigned",
    "selfdef_kernel_tainted_out_of_tree",
    "selfdef_kernel_modules_textfile_emit_failed",
}


def _load():
    return json.loads(DASHBOARD_PATH.read_text())


def test_dashboard_present_and_valid_json():
    assert DASHBOARD_PATH.is_file()
    _load()


def test_title_locked():
    assert _load()["title"] == "sovereign-os — selfdef kernel modules (rootkit detection)"


def test_uid_canonical():
    assert _load()["uid"] == "sovereign-os-selfdef-kernel-modules"


def test_tags_include_security_marker():
    tags = set(_load()["tags"])
    for required in ("sovereign-os", "selfdef", "kernel-modules",
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


def test_unsigned_panel_red_at_1():
    dash = _load()
    for panel in dash["panels"]:
        if "unsigned" not in panel.get("title", "").lower():
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
    raise AssertionError("unsigned panel must mark red at value=1")


def test_modules_count_panel_yellow_at_200():
    dash = _load()
    for panel in dash["panels"]:
        if "modules loaded" not in panel.get("title", "").lower():
            continue
        steps = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("thresholds", {})
            .get("steps", [])
        )
        for s in steps:
            if s.get("color") == "yellow" and s.get("value") == 200:
                return
    raise AssertionError("modules-loaded panel must mark yellow at 200")


def test_tainted_bits_timeseries_charts_all_3():
    dash = _load()
    for panel in dash["panels"]:
        if "tainted bits" not in panel.get("title", "").lower():
            continue
        exprs = " ".join(t.get("expr", "") for t in panel.get("targets", []))
        for gauge in (
            "selfdef_kernel_tainted_proprietary",
            "selfdef_kernel_tainted_unsigned",
            "selfdef_kernel_tainted_out_of_tree",
        ):
            assert gauge in exprs
        return
    raise AssertionError("dashboard missing tainted-bits timeseries panel")


def test_refresh_30s():
    assert _load()["refresh"] == "30s"


def test_panel_count_locked():
    assert len(_load()["panels"]) == 7


def test_links_to_selfdef_producer():
    urls = " ".join(link.get("url", "") for link in _load().get("links", []))
    assert "selfdef-kernel-modules-textfile.sh" in urls


def test_anchors_to_selfdef_producer_commit():
    assert "78a9e29" in _load().get("_comment", "")
