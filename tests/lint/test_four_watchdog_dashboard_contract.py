"""Four-watchdog Grafana dashboard — contract test.

Locks the structural shape of
`docs/observability/dashboards/sovereign-os-four-watchdog.json` —
the cockpit panel rendering the selfdef-side
`selfdef_four_watchdog_*` gauges shipped by
selfdef-four-watchdog-doctor.{service,timer} (selfdef commits
`7869a45` + `a009b39`).

Same drift-protection pattern as
test_m060_cli_mirror_dashboard_contract.py — every gauge appears on
≥1 panel, thresholds match the alert rules, dashboard title/uid/tags
are locked, refresh interval is sensible, panel count is locked,
links to producer source + runbook present.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_PATH = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-four-watchdog.json"
)

CANONICAL_GAUGES = {
    "selfdef_four_watchdog_worst_severity",
    "selfdef_four_watchdog_severity",
    "selfdef_four_watchdog_last_run_unix",
    "selfdef_four_watchdog_textfile_emit_failed",
}


def _load() -> dict:
    return json.loads(DASHBOARD_PATH.read_text())


def _all_panel_exprs(dash: dict) -> list[str]:
    return [
        t.get("expr", "")
        for p in dash["panels"]
        for t in p.get("targets", [])
    ]


def test_dashboard_file_present_and_valid_json():
    assert DASHBOARD_PATH.is_file(), f"missing dashboard: {DASHBOARD_PATH}"
    _load()  # parses → asserts JSON valid


def test_dashboard_title_locked():
    dash = _load()
    assert dash["title"] == "sovereign-os — four-watchdog (IPS spine)", (
        f"dashboard title drift: got {dash['title']!r}"
    )


def test_dashboard_uid_canonical():
    dash = _load()
    assert dash["uid"] == "sovereign-os-four-watchdog"


def test_dashboard_tags_include_ips_spine_marker():
    """Tags MUST include the IPS-spine marker so operators can find
    this dashboard in Grafana's tag-filter UI."""
    dash = _load()
    tags = set(dash["tags"])
    for required in ("sovereign-os", "selfdef", "four-watchdog", "IPS-spine"):
        assert required in tags, (
            f"dashboard tags missing required marker {required!r}; "
            f"got {sorted(tags)}"
        )


def test_every_canonical_gauge_appears_on_at_least_one_panel():
    """Each of the 4 producer-shipped gauges MUST appear on ≥1 panel.
    Drift = the operator can't see one of the gauges in Grafana."""
    dash = _load()
    all_exprs = " ".join(_all_panel_exprs(dash))
    for gauge in CANONICAL_GAUGES:
        assert gauge in all_exprs, (
            f"dashboard missing canonical gauge {gauge!r} on any panel"
        )


def test_worst_severity_panel_red_threshold_at_2():
    """The worst-severity rollup panel MUST visualize the red
    threshold at 2 (CRITICAL) matching the alert rule. Drift here =
    the dashboard turns red at a different severity than the alert
    pages."""
    dash = _load()
    found_red_at_2 = False
    for panel in dash["panels"]:
        if "worst severity" not in panel.get("title", "").lower():
            continue
        steps = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("thresholds", {})
            .get("steps", [])
        )
        for s in steps:
            if s.get("color") == "red" and s.get("value") == 2:
                found_red_at_2 = True
                break
    assert found_red_at_2, (
        "worst-severity panel must render the red threshold at value=2 "
        "(matching the FourWatchdogWorstSeverityCritical alert)"
    )


def test_observer_age_panel_red_threshold_at_300s():
    """The observer-age panel MUST visualize the red threshold at
    300s matching the FourWatchdogObserverSilent alert. Locked by
    the cross-surface threshold-lockstep contract."""
    dash = _load()
    found_red_at_300 = False
    for panel in dash["panels"]:
        title = panel.get("title", "").lower()
        if "observer age" not in title and "observer-age" not in title:
            continue
        steps = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("thresholds", {})
            .get("steps", [])
        )
        for s in steps:
            if s.get("color") == "red" and s.get("value") == 300:
                found_red_at_300 = True
                break
        if found_red_at_300:
            break
    assert found_red_at_300, (
        "observer-age panel must render the red threshold at 300s "
        "(matching FourWatchdogObserverSilent + cross-surface lockstep)"
    )


def test_emit_failed_panel_has_fail_mapping():
    """The emit-failed sentinel panel MUST display 'FAILED' on
    value=1 so operators see a human label instead of a raw 1.
    Drift = operator misreads the sentinel."""
    dash = _load()
    for panel in dash["panels"]:
        title = panel.get("title", "").lower()
        if "emit-failed" not in title and "emit_failed" not in title:
            continue
        mappings = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("mappings", [])
        )
        # value mappings include text=FAILED for value=1.
        found = False
        for m in mappings:
            opts = m.get("options", {})
            if opts.get("1", {}).get("text", "").upper() == "FAILED":
                found = True
                break
        assert found, (
            "emit-failed panel must map value=1 → text='FAILED'"
        )
        return
    # If we get here, no emit-failed panel exists at all.
    raise AssertionError("dashboard missing the emit-failed sentinel panel")


def test_per_alert_severity_panel_groups_by_ms_label():
    """The per-alert timeseries MUST use the `ms` label in the
    legendFormat — that's how operators get the milestone-family
    breakdown (MS046/MS047/MS044/MS048) in Grafana. Drift = legend
    only shows alert-name without IPS-family context."""
    dash = _load()
    for panel in dash["panels"]:
        title = panel.get("title", "").lower()
        if "per-alert severity" not in title:
            continue
        legend = " ".join(
            t.get("legendFormat", "")
            for t in panel.get("targets", [])
        )
        assert "{{ms}}" in legend, (
            "per-alert panel legendFormat must include {{ms}} for "
            "milestone-family grouping; got: " + legend
        )
        return
    raise AssertionError(
        "dashboard missing the per-alert-severity timeseries panel"
    )


def test_dashboard_links_to_selfdef_producer_source():
    """The dashboard MUST link to the selfdef-side producer source.
    Drift = operators inspecting the dashboard can't find the
    canonical producer location."""
    dash = _load()
    all_urls = " ".join(link.get("url", "") for link in dash.get("links", []))
    assert "four-watchdog-textfile.sh" in all_urls, (
        "dashboard must link to the selfdef producer source"
    )
    assert "selfdef" in all_urls.lower()


def test_dashboard_refresh_interval_set():
    dash = _load()
    assert "refresh" in dash and dash["refresh"], (
        "dashboard must declare a refresh interval"
    )


def test_dashboard_panel_count_locked():
    """Panel count is a structural integrity check — drift either
    way means the dashboard's design changed. Locking forces the
    operator to update this test when the design intentionally
    evolves."""
    dash = _load()
    assert len(dash["panels"]) == 9, (
        f"dashboard panel count drift: expected 9, got {len(dash['panels'])}"
    )


def test_dashboard_links_to_deployment_guide_runbook():
    """The dashboard MUST link to the deployment-guide runbook
    sections so operators looking at a fired alert in Grafana can
    click through to the operator-actionable Diagnosis + Fix."""
    dash = _load()
    all_urls = " ".join(link.get("url", "") for link in dash.get("links", []))
    assert "m060-deployment-guide.md" in all_urls, (
        "dashboard must link to the deployment-guide runbook sections"
    )


def test_dashboard_anchors_to_selfdef_producer_commits():
    """The dashboard's _comment MUST cite the selfdef producer
    commits so future drift catches show up in the audit trail.
    Same anchor pattern as the alert rules file."""
    dash = _load()
    comment = dash.get("_comment", "")
    assert "7869a45" in comment or "a009b39" in comment, (
        "dashboard comment must cite the selfdef-side producer "
        "commits 7869a45 / a009b39"
    )


def test_dashboard_anchors_ips_spine_milestones():
    """The dashboard MUST anchor MS046+MS047+MS044+MS048 in its
    comment block so operators reading the dashboard understand
    which production-shipped IPS milestones it observes."""
    dash = _load()
    comment = dash.get("_comment", "")
    for ms in ("MS046", "MS047", "MS044", "MS048"):
        assert ms in comment, (
            f"dashboard comment must anchor IPS-spine milestone {ms}"
        )
