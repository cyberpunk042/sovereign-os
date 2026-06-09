"""Selfdef IPS detection-stream cockpit dashboard — contract test.

This dashboard surfaces selfdef's CORE output (events → findings). It is
the operator's primary "is the IPS detecting + correlating?" view, so its
key panels are locked against accidental removal. Metric existence is
covered cross-repo by test_selfdef_dashboard_metrics_lockstep; this locks
the panel SET.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASH = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-selfdef-detection-stream.json"
)


def _load() -> dict:
    return json.loads(DASH.read_text())


def test_dashboard_present_and_valid():
    assert DASH.is_file()
    _load()


def test_core_detection_exprs_present():
    exprs = {
        t.get("expr", "")
        for p in _load()["panels"]
        for t in p.get("targets", [])
    }
    blob = " ".join(exprs)
    for required in (
        "selfdef_events_total",
        "selfdef_findings_total",
        "selfdef_findings_by_severity_total",
        "selfdef_events_by_class_total",
    ):
        assert required in blob, f"core detection series {required!r} dropped from the dashboard"


def test_findings_by_severity_is_broken_down_by_severity_id():
    exprs = " ".join(
        t.get("expr", "") for p in _load()["panels"] for t in p.get("targets", [])
    )
    assert "by (severity_id)" in exprs, (
        "the findings panel must break down by severity_id so the operator sees "
        "critical vs informational, not just a total"
    )
