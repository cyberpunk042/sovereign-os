"""M010 deterministic-data-plane contract lint.

Locks `config/inference/m010-deterministic-data-plane.yaml` to the M010 spec: the
3 SIMD libraries (E0078), the token-law masks (E0081), the AVX-512 branch
primitives (E0080), the memory bitmap index + six-sketch row (E0082), the 8-stage
tool-call transaction (E0083), and the CPU-pipeline stages (E0084). The
transaction + pipeline stage ORDER is verbatim (no reordering / minimization).

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "inference" / "m010-deterministic-data-plane.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M010-deterministic-data-plane.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M010"


def test_three_simd_libraries_verbatim():
    libs = _c()["simd_libraries"]
    assert [l["library"] for l in libs] == ["simdjson", "Hyperscan", "CRoaring"]
    assert [l["module"] for l in libs] == ["M00147", "M00148", "M00149"]


def test_token_law_four_masks():
    assert _c()["token_law_masks"]["masks"] == ["grammar", "schema", "tool", "safety"]


def test_avx512_branch_primitives():
    prims = {p["primitive"] for p in _c()["avx512_branch_primitives"]}
    assert "VPCONFLICT" in prims and "VPCOMPRESS/VPEXPAND" in prims


def test_memory_bitmap_five_dimensions():
    dims = _c()["memory_bitmap_index"]["intersect_dimensions"]
    assert dims == ["project", "topic", "freshness", "trust", "permissions"], (
        f"bitmap-dimension drift: {dims}")


def test_memory_item_sketch_six_fields():
    s = _c()["memory_item_sketch"]
    assert s["fields"] == ["topic", "entity", "tool", "trust_flags", "freshness",
                           "permissions"], f"sketch field drift: {s['fields']}"


def test_tool_call_transaction_eight_stages_in_order():
    stages = _c()["tool_call_transaction"]["stages"]
    assert stages == ["parse-json", "validate-schema", "scan-policy",
                      "check-permission-bits", "check-workspace-bounds",
                      "check-branch-budget", "classify-risk", "commit-or-reject"], (
        f"tool-call transaction stage drift (order matters): {stages}")


def test_cpu_pipeline_six_stages_in_order():
    stages = _c()["cpu_pipeline_stages"]["stages"]
    assert stages == ["Fetch", "Decode", "Execute", "Validate", "Retire", "Commit"], (
        f"CPU-pipeline stage drift (order matters): {stages}")


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00147", "M00149", "M00155", "M00158", "M00161", "M00162", "M00163"):
        assert mod in body, f"{mod} not in the M010 milestone (must trace to spec)"
