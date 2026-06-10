"""Contract tests for the sovereign-gatewayd Prometheus alert rules.

Locks the never-cloud-spill tripwire alerts to the metric surface
`sovereign-gatewayd` actually serves on `GET /metrics`, so the paging
layer can't silently drift from the daemon. Unlike the textfile-collector
families, the emitted-metric set here is read straight out of the
daemon's source (`crates/sovereign-gatewayd/src/lib.rs`) rather than
hand-copied — a rename in the exporter fails this gate immediately.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = (
    REPO_ROOT / "config" / "prometheus" / "alerts" / "sovereign-gatewayd.rules.yml"
)
EXPORTER_SRC = REPO_ROOT / "crates" / "sovereign-gatewayd" / "src" / "lib.rs"

METRIC_RE = re.compile(r"\bsovereign_gateway_[a-z][a-z0-9_]*\b")


def _rules() -> list[dict]:
    doc = yaml.safe_load(RULES_PATH.read_text(encoding="utf-8"))
    groups = doc["groups"]
    assert len(groups) == 1 and groups[0]["name"] == "sovereign-gatewayd"
    return groups[0]["rules"]


def _emitted_metrics() -> set[str]:
    """Every sovereign_gateway_* series named in the daemon's exporter."""
    return set(METRIC_RE.findall(EXPORTER_SRC.read_text(encoding="utf-8")))


def test_rules_file_exists_and_parses():
    assert RULES_PATH.is_file()
    assert _rules(), "at least one alert rule"


def test_expected_alerts_present():
    names = {r["alert"] for r in _rules()}
    assert {
        "SovereignGatewayCloudSpill",
        "SovereignGatewayTripwireUnmonitored",
    } <= names


def test_every_expr_references_only_emitted_metrics():
    emitted = _emitted_metrics()
    assert "sovereign_gateway_never_cloud_spill_holds" in emitted, (
        "exporter source no longer names the tripwire gauge — renamed?"
    )
    for r in _rules():
        for metric in METRIC_RE.findall(r["expr"]):
            assert metric in emitted, (
                f"{r['alert']} expr references {metric}, which the daemon's "
                f"exporter ({EXPORTER_SRC.name}) never emits — dead alert"
            )


def test_every_alert_has_severity_and_runbook():
    for r in _rules():
        assert r["labels"]["severity"] in {"warning", "critical"}, r["alert"]
        assert r["annotations"]["runbook_url"].startswith("https://"), r["alert"]
        # runbook anchor matches the alert name, lower-cased + severity.
        anchor = r["annotations"]["runbook_url"].rsplit("#", 1)[-1]
        assert r["alert"].lower() in anchor, (r["alert"], anchor)


def test_cloud_spill_pages_immediately():
    """The spill tripwire is deliberately `for:`-less — one confirmed
    scrape pages. The spill already happened and cannot un-happen for the
    process lifetime, so any delay only postpones the incident response."""
    rule = next(r for r in _rules() if r["alert"] == "SovereignGatewayCloudSpill")
    assert rule["labels"]["severity"] == "critical"
    assert "sovereign_gateway_never_cloud_spill_holds" in rule["expr"]
    assert "for" not in rule, "spill tripwire must page on the first scrape"


def test_tripwire_unmonitored_tolerates_restarts():
    """The absence watcher MUST have a `for:` window — a daemon restart or
    one missed scrape must not page; sustained silence must."""
    rule = next(
        r for r in _rules() if r["alert"] == "SovereignGatewayTripwireUnmonitored"
    )
    assert rule["labels"]["severity"] == "warning"
    assert "absent(sovereign_gateway_never_cloud_spill_holds)" in rule["expr"]
    assert "for" in rule, "absence watcher needs a tolerance window"
