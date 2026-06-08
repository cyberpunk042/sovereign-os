"""Selfdef audit-chain integrity alerts — contract test.

Locks the tamper-detection alerts: one per subsystem (guardian /
perimeter / scheduler), each firing on the SHA-256 chain integrity
sentinel `== -1`. Drift on the `-1` sentinel or the subsystem set would
silently drop tamper detection from the cockpit.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES = REPO_ROOT / "config" / "prometheus" / "alerts" / "selfdef-audit-chain.rules.yml"
SUBS = ("guardian", "perimeter", "scheduler")


def _rules() -> list[dict]:
    doc = yaml.safe_load(RULES.read_text())
    return [r for g in doc["groups"] for r in g["rules"]]


def test_one_critical_alert_per_subsystem():
    by_name = {r["alert"]: r for r in _rules()}
    for sub in SUBS:
        name = f"Selfdef{sub.capitalize()}AuditChainBroken"
        a = by_name.get(name)
        assert a is not None, f"missing {name}"
        assert a["labels"]["severity"] == "critical"
        assert a["labels"]["subsystem"] == "selfdef-audit-chain"


def test_each_alert_uses_the_minus_one_integrity_sentinel():
    for r in _rules():
        sub = r["labels"]["audit_chain_link"]
        expr = " ".join(r["expr"].split())
        assert expr == f"selfdef_{sub}_audit_chain_events == -1", (
            f"audit-chain alert must fire on the `== -1` integrity sentinel; got: {expr}"
        )
