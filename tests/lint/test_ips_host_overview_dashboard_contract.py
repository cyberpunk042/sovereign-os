"""IPS host overview Grafana dashboard — contract test.

The single-pane-of-glass cockpit dashboard #28 consolidating all 8
observability verticals shipped to date. Consumes the cross-vertical
recording rules from commit 594fd02 plus per-vertical headline
gauges from the 8 selfdef-side textfile observers.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_PATH = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-ips-host-overview.json"
)

CANONICAL_ROLLUPS = {
    "sovereign_os:critical_state_any",
    "sovereign_os:observer_fault_any",
    "sovereign_os:warn_state_any",
    "sovereign_os:textfile_observers_healthy_count",
}

CANONICAL_PER_VERTICAL_GAUGES = {
    "selfdef_four_watchdog_worst_severity",
    "selfdef_sse_subscribers_global_saturation",
    "selfdef_modules_total",
    "selfdef_daemon_process_memory_rss_bytes",
    "selfdef_daemon_process_open_fds",
    "selfdef_apparmor_profile_enforce",
    "selfdef_auth_events_login_failures",
    "selfdef_systemd_units_failed",
    "selfdef_systemd_units_active",
}

LINKED_DASHBOARD_UIDS = {
    "sovereign-os-m060-cli-mirror",
    "sovereign-os-m060-mirror-domains",
    "sovereign-os-ms022-sse-quota",
    "sovereign-os-four-watchdog",
    "sovereign-os-selfdef-modules",
    "sovereign-os-selfdef-daemon-process",
    "sovereign-os-selfdef-apparmor",
    "sovereign-os-selfdef-auth-events",
    "sovereign-os-selfdef-systemd-units",
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
    assert _load()["title"] == "sovereign-os — IPS host overview (single-pane-of-glass)"


def test_uid_canonical():
    assert _load()["uid"] == "sovereign-os-ips-host-overview"


def test_tags_include_canonical_markers():
    tags = set(_load()["tags"])
    for required in ("sovereign-os", "selfdef", "ips-host", "overview",
                     "single-pane", "observability"):
        assert required in tags


def test_all_cross_vertical_rollups_charted():
    """All 4 recording rules from commit 594fd02 MUST appear on ≥1
    panel — this is the dashboard's headline value proposition."""
    exprs = _all_exprs(_load())
    for rollup in CANONICAL_ROLLUPS:
        assert rollup in exprs, (
            f"dashboard missing rollup {rollup}"
        )


def test_all_per_vertical_headline_gauges_charted():
    """Each of the 8 verticals MUST contribute ≥1 headline gauge
    to the overview — operators see the full posture at a glance."""
    exprs = _all_exprs(_load())
    for gauge in CANONICAL_PER_VERTICAL_GAUGES:
        assert gauge in exprs, f"dashboard missing gauge {gauge}"


def test_links_to_all_per_vertical_dashboards():
    """Drill-down link to each of the 9 per-vertical dashboards."""
    dash = _load()
    link_urls = " ".join(link.get("url", "") for link in dash.get("links", []))
    for uid in LINKED_DASHBOARD_UIDS:
        assert uid in link_urls, f"missing drill-down link to {uid}"


def test_apparmor_targets_canonical_profile():
    """The AppArmor enforce panel MUST target the canonical profile
    path. Drift here = dashboard renders state for the wrong process."""
    dash = _load()
    apparmor_panel_exprs = []
    for panel in dash["panels"]:
        for t in panel.get("targets", []):
            if "apparmor" in t.get("expr", ""):
                apparmor_panel_exprs.append(t["expr"])
    assert any(
        "/usr/bin/selfdefd" in e for e in apparmor_panel_exprs
    ), "AppArmor panel must target /usr/bin/selfdefd profile"


def test_critical_rollup_panel_has_text_mappings():
    """The cross-vertical critical-rollup panel MUST map values to
    operator-readable text (ALL GREEN / CRITICAL) — drift = operator
    reads raw numbers instead of actionable label."""
    dash = _load()
    for panel in dash["panels"]:
        title = panel.get("title", "").lower()
        if "any vertical critical" not in title:
            continue
        mappings = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("mappings", [])
        )
        for m in mappings:
            opts = m.get("options", {})
            if (opts.get("0", {}).get("text", "").upper() == "ALL GREEN"
                    and opts.get("1", {}).get("text", "").upper() == "CRITICAL"):
                return
    raise AssertionError(
        "critical-rollup panel must map 0→ALL GREEN, 1→CRITICAL"
    )


def test_observer_count_panel_max_3():
    """Observer-healthy-count panel max value MUST be 3 — that's the
    healthy baseline. Drift to a larger number = miscalibrated panel."""
    dash = _load()
    for panel in dash["panels"]:
        if "observer healthy" not in panel.get("title", "").lower():
            continue
        max_val = panel.get("fieldConfig", {}).get("defaults", {}).get("max")
        if max_val == 3:
            return
    raise AssertionError("observer-healthy-count panel must have max=3")


def test_refresh_30s():
    assert _load()["refresh"] == "30s"


def test_panel_count_locked():
    """Single-pane-of-glass dashboard MUST stay tight — locked at
    exactly 15 panels (3 cross-vertical rollups + 9 per-vertical
    headlines + 1 timeseries + 1 healthy-count timeseries + 1
    spare slot for room)."""
    assert len(_load()["panels"]) == 15


def test_dashboard_links_count_matches_per_vertical_count():
    """9 dashboard-link slots matching the 9 per-vertical drill-down
    targets."""
    assert len(_load().get("links", [])) == 9


def test_anchors_to_recording_rules_commit():
    """Dashboard comment MUST cite the recording-rules commit
    594fd02 so the audit trail is traceable."""
    assert "594fd02" in _load().get("_comment", "")
