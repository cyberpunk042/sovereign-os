"""The selfdef cockpit core dashboards must exist + render their defining
metric.

This session added the operator's primary cockpit views of selfdef's
producer metrics. Lock them as a set so none is silently deleted and each
keeps rendering its defining series (metric-existence vs selfdef is
covered cross-repo by test_selfdef_dashboard_metrics_lockstep; this locks
the dashboard ↔ purpose binding).
"""
from __future__ import annotations

import json
from pathlib import Path

DASH_DIR = Path(__file__).resolve().parents[2] / "docs" / "observability" / "dashboards"

# dashboard filename stem -> a defining metric it MUST render
CORE = {
    "sovereign-os-selfdef-detection-stream": "selfdef_findings_total",
    "sovereign-os-selfdef-responder-fleet": "selfdef_token_revocations_active_count",
    "sovereign-os-selfdef-audit-chain": "selfdef_guardian_audit_chain_events",
    "sovereign-os-selfdef-store-retention": "selfdef_store_retention_pruned_total",
    "sovereign-os-selfdef-storage-mounts": "selfdef_storage_mount_used_pct",
}


def _exprs(stem: str) -> str:
    data = json.loads((DASH_DIR / f"{stem}.json").read_text())
    return " ".join(
        t.get("expr", "") for p in data.get("panels", []) for t in p.get("targets", [])
    )


def test_each_core_cockpit_dashboard_exists():
    missing = [s for s in CORE if not (DASH_DIR / f"{s}.json").is_file()]
    assert not missing, f"core cockpit dashboards deleted: {missing}"


def test_each_core_cockpit_dashboard_renders_its_defining_metric():
    broken = [
        f"{stem} (expected {metric})"
        for stem, metric in CORE.items()
        if metric not in _exprs(stem)
    ]
    assert not broken, "core cockpit dashboards no longer render their defining metric:\n" + "\n".join(broken)
