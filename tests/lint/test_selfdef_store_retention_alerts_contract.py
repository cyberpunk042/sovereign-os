"""Selfdef SDD-081 hot-store retention alert — contract test.

The SelfdefStoreRetentionStalled alert must keep its `_enabled == 1`
guard: without it, a host that deliberately opts out of retention
(hot_retention_days=0 → sweeps stay 0 by design) would false-page
forever. This locks that load-bearing guard + the alert envelope.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = (
    REPO_ROOT / "config" / "prometheus" / "alerts"
    / "selfdef-store-retention.rules.yml"
)


def _rules() -> list[dict]:
    doc = yaml.safe_load(RULES_PATH.read_text())
    return [r for g in doc["groups"] for r in g["rules"]]


def test_rules_file_present_and_valid():
    assert RULES_PATH.is_file()
    assert _rules()


def test_stalled_alert_present_with_full_envelope():
    by_name = {r["alert"]: r for r in _rules()}
    a = by_name.get("SelfdefStoreRetentionStalled")
    assert a is not None, "SelfdefStoreRetentionStalled alert missing"
    for f in ("expr", "for", "labels", "annotations"):
        assert f in a, f"alert missing {f}"
    assert a["labels"]["subsystem"] == "selfdef-store-retention"
    assert a["labels"]["severity"] == "warning"
    assert a["annotations"].get("runbook_url", "").endswith(
        "#selfdefstoreretentionstalled-warning"
    )


def test_stalled_alert_keeps_enabled_guard_and_sweep_window():
    """Load-bearing: the `_enabled == 1` guard prevents false-paging hosts
    that opted out of retention; the sweeps-window catches a stalled loop."""
    by_name = {r["alert"]: r for r in _rules()}
    expr = by_name["SelfdefStoreRetentionStalled"]["expr"]
    norm = " ".join(expr.split())
    assert "selfdef_store_retention_enabled == 1" in norm, (
        "the opt-out guard `selfdef_store_retention_enabled == 1` must stay "
        f"or opt-out hosts false-page; got: {norm}"
    )
    assert "increase(selfdef_store_retention_sweeps_total[13h]) == 0" in norm, (
        f"the stalled-sweep condition must stay; got: {norm}"
    )
