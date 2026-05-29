"""Selfdef daemon process-state Grafana dashboard — contract test."""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_PATH = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-selfdef-daemon-process.json"
)

CANONICAL_GAUGES = {
    "selfdef_daemon_process_memory_rss_bytes",
    "selfdef_daemon_process_memory_vsize_bytes",
    "selfdef_daemon_process_open_fds",
    "selfdef_daemon_process_threads",
    "selfdef_daemon_process_uptime_seconds",
    "selfdef_daemon_process_restart_count",
    "selfdef_daemon_process_textfile_emit_failed",
}


def _load() -> dict:
    return json.loads(DASHBOARD_PATH.read_text())


def _all_exprs(dash: dict) -> str:
    return " ".join(
        t.get("expr", "")
        for p in dash["panels"]
        for t in p.get("targets", [])
    )


def test_dashboard_present_and_valid_json():
    assert DASHBOARD_PATH.is_file()
    _load()


def test_title_locked():
    assert _load()["title"] == "sovereign-os — selfdefd daemon process-state"


def test_uid_canonical():
    assert _load()["uid"] == "sovereign-os-selfdef-daemon-process"


def test_tags_include_canonical_markers():
    tags = set(_load()["tags"])
    for required in ("sovereign-os", "selfdef", "daemon-process", "observability"):
        assert required in tags


def test_every_canonical_gauge_appears():
    exprs = _all_exprs(_load())
    for gauge in CANONICAL_GAUGES:
        assert gauge in exprs, f"missing canonical gauge {gauge!r}"


def test_memory_panel_red_threshold_at_1_gib():
    """1 GiB = 1073741824 bytes matches SelfdefDaemonProcessMemoryHigh."""
    dash = _load()
    found = False
    for panel in dash["panels"]:
        if "memory" not in panel.get("title", "").lower():
            continue
        steps = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("thresholds", {})
            .get("steps", [])
        )
        for s in steps:
            if s.get("color") == "red" and s.get("value") == 1073741824:
                found = True
                break
        if found:
            break
    assert found, "memory panel must mark 1 GiB (1073741824) red threshold"


def test_fd_panel_red_threshold_at_819():
    dash = _load()
    found = False
    for panel in dash["panels"]:
        title = panel.get("title", "").lower()
        if "fd" not in title:
            continue
        steps = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("thresholds", {})
            .get("steps", [])
        )
        for s in steps:
            if s.get("color") == "red" and s.get("value") == 819:
                found = True
                break
        if found:
            break
    assert found, "FD panel must mark 819 (80% of 1024 ulimit) red threshold"


def test_restart_count_panel_uses_increase_function():
    """The restart-count panel (NOT the uptime saw-tooth panel) MUST
    chart `increase(...[10m])` so operators see the same window the
    alert evaluates over."""
    dash = _load()
    for panel in dash["panels"]:
        title = panel.get("title", "").lower()
        if "restart count" not in title:
            continue
        exprs = " ".join(t.get("expr", "") for t in panel.get("targets", []))
        assert "increase(" in exprs and "10m" in exprs, (
            "restart-count panel must chart increase()[10m] for "
            "alert-window parity"
        )
        return
    raise AssertionError("dashboard missing 'restart count' panel")


def test_emit_failed_panel_has_failed_mapping():
    dash = _load()
    for panel in dash["panels"]:
        title = panel.get("title", "").lower()
        if "emit-failed" not in title:
            continue
        mappings = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("mappings", [])
        )
        for m in mappings:
            opts = m.get("options", {})
            if opts.get("1", {}).get("text", "").upper() == "FAILED":
                return
    raise AssertionError("emit-failed panel missing value=1 → FAILED mapping")


def test_refresh_30s():
    assert _load()["refresh"] == "30s"


def test_panel_count_locked():
    assert len(_load()["panels"]) == 9


def test_links_to_selfdef_producer():
    urls = " ".join(link.get("url", "") for link in _load().get("links", []))
    assert "selfdef-daemon-process-textfile.sh" in urls


def test_anchors_to_selfdef_producer_commit():
    assert "09822c1" in _load().get("_comment", "")
