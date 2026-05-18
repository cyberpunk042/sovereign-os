"""R495 (SDD-011+ R161 R215) — Router Grafana dashboard contract lint.

Closes the router dashboard:FUTURE waiver and extends router surface-
map registration to 5 surfaces (core/cli/api/service/dashboard).

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

The router is the operator-§1g OpenAI-compatible front for the Trinity
inference stack. Every request gets R161 task-type classified + R215
model-class cross-tabbed and the routing decision surfaces as Layer-B
metrics.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ROUTER_DASHBOARD_JSON = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-router.json"
)


def test_dashboard_json_exists():
    assert ROUTER_DASHBOARD_JSON.is_file(), (
        f"missing router dashboard: {ROUTER_DASHBOARD_JSON}"
    )


def test_dashboard_json_parseable():
    data = json.loads(ROUTER_DASHBOARD_JSON.read_text(encoding="utf-8"))
    assert "panels" in data
    assert data.get("title")
    assert data.get("uid")


def test_dashboard_references_route_total_metric():
    body = ROUTER_DASHBOARD_JSON.read_text(encoding="utf-8")
    assert "sovereign_os_inference_route_total" in body, (
        "router dashboard doesn't reference route_total metric"
    )


def test_dashboard_references_r161_task_type_metric():
    body = ROUTER_DASHBOARD_JSON.read_text(encoding="utf-8")
    assert "sovereign_os_inference_router_task_type_total" in body, (
        "router dashboard missing R161 task_type metric"
    )


def test_dashboard_references_r215_class_metric():
    body = ROUTER_DASHBOARD_JSON.read_text(encoding="utf-8")
    assert "sovereign_os_inference_router_class_total" in body, (
        "router dashboard missing R215 model-class metric"
    )


def test_dashboard_references_freshness_gauge():
    body = ROUTER_DASHBOARD_JSON.read_text(encoding="utf-8")
    assert "sovereign_os_inference_router_last_route_timestamp" in body, (
        "router dashboard missing last_route_timestamp freshness gauge"
    )


def test_dashboard_documents_four_task_types():
    """R161 4-task-type taxonomy MUST appear verbatim in §1g panel
    (operator-§1g sacrosanct: code / math / conversational / creative)."""
    body = ROUTER_DASHBOARD_JSON.read_text(encoding="utf-8")
    for tt in ("code", "math", "conversational", "creative"):
        assert tt in body, (
            f"router dashboard missing R161 task_type: {tt!r}"
        )


def test_dashboard_documents_r215_class_taxonomy():
    """R215 13-class model-class taxonomy MUST appear in §1g panel."""
    body = ROUTER_DASHBOARD_JSON.read_text(encoding="utf-8")
    for cls in ("llm", "slm", "rlm", "ternary-lm", "lora-adapter",
                "embed", "vision", "multimodal", "mixture",
                "speculative", "reranker"):
        assert cls in body, (
            f"router dashboard missing R215 model-class: {cls!r}"
        )


def test_dashboard_quotes_operator_standing_rule_verbatim():
    body = ROUTER_DASHBOARD_JSON.read_text(encoding="utf-8")
    assert "We do not minimize anything" in body, (
        "router dashboard missing §1g verbatim standing rule"
    )


def test_dashboard_listed_in_readme():
    readme = (ROUTER_DASHBOARD_JSON.parent / "README.md").read_text(encoding="utf-8")
    assert "sovereign-os-router.json" in readme, (
        "dashboards/README.md missing sovereign-os-router.json entry"
    )


def test_dashboard_tagged_sovereign_os():
    data = json.loads(ROUTER_DASHBOARD_JSON.read_text(encoding="utf-8"))
    tags = data.get("tags") or []
    assert "sovereign-os" in tags
    assert "router" in tags


def test_router_surface_map_extended_to_dashboard():
    """R495 extends router surface-map to 5 surfaces — dashboard MUST
    appear in the shipped surfaces list, NOT as a FUTURE waiver."""
    sm_path = REPO_ROOT / "scripts" / "operator" / "surface-map.py"
    result = subprocess.run(
        ["python3", str(sm_path), "coverage", "--module",
         "router", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, (
        f"surface-map coverage router failed: {result.stderr[:300]}"
    )
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    surface_count = entry.get("surface_count", 0)
    assert surface_count >= 5, (
        f"router must be at >=5 surfaces post-R495; got {surface_count}"
    )
    matrix = entry.get("matrix", [])
    dashboard_row = next(
        (r for r in matrix if r.get("surface") == "dashboard"), None
    )
    assert dashboard_row is not None, (
        "router coverage matrix missing 'dashboard' row"
    )
    assert dashboard_row.get("state") == "shipped", (
        f"router dashboard surface must be shipped; got {dashboard_row}"
    )
