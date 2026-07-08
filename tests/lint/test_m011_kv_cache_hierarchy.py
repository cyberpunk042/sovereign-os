"""M011 KV-cache-hierarchy contract lint.

Locks `config/inference/m011-kv-cache-hierarchy.yaml` to the M011 milestone spec:
the 4-tier cache hierarchy (E0087), the KvBlockMeta 64-byte SoA row + SIMD scan
predicates (E0088), content-addressing + prefill caches (E0089), the TokenNode
row (E0090), the branch-row KV refs (E0091), the admission bitfield (E0092), and
the 8 Cortex-runtime organs (E0093). No minimization of the spec.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "inference" / "m011-kv-cache-hierarchy.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M011-kv-cache-memory-hierarchy.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M011"


def test_cache_hierarchy_four_tiers():
    h = _c()["cache_hierarchy"]
    assert [t["module"] for t in h] == ["M00164", "M00165", "M00166", "M00167"]
    assert [t["tier"] for t in h] == ["L1/L2", "L3", "cold", "controller"]


def test_kv_block_meta_64byte_soa_eight_fields():
    m = _c()["kv_block_meta"]
    assert m["module"] == "M00169" and m["row_bytes"] == 64 and m["layout"] == "SoA"
    assert m["fields"] == ["hash_hi", "hash_lo", "model_id", "token_range",
                           "trust_flags", "heat", "last_used", "owner_policy"], (
        f"KvBlockMeta field drift: {m['fields']}")


def test_simd_scan_six_predicates():
    p = _c()["simd_scan_predicates"]["predicates"]
    assert len(p) == 6 and "block-hash-match" in p and "allowed-for-session" in p


def test_content_addressing_hash_inputs_verbatim():
    ca = _c()["content_addressing"]
    assert ca["module"] == "M00173"
    assert ca["hash_inputs"] == ["model_id", "tokenizer_id", "prompt_bytes",
                                 "schema_version"], f"hash-input drift: {ca['hash_inputs']}"


def test_token_node_and_branch_row_verbatim():
    assert _c()["token_node"]["fields"] == ["token", "parent", "depth", "child_mask",
                                            "score", "flags"]
    assert _c()["branch_row"]["fields"] == ["branch_id", "parent_branch_id",
                                            "kv_prefix_ref", "kv_delta_ref",
                                            "control_word", "budget", "score"]


def test_admission_bitfield_flagged_proposed():
    b = _c()["memory_admission_bitfield"]
    assert b.get("bit_layout_proposed") is True, "bit widths must be flagged agent-proposed (SB-095)"
    assert b["fields"] == ["cache-tier", "trust", "reuse-count", "token-cost",
                           "owner-session", "flags"]


def test_cortex_runtime_eight_organs():
    o = _c()["cortex_runtime_organs"]["organs"]
    assert o == ["Branch", "Policy", "Grammar", "Memory-Router", "Speculation",
                 "Tool-Gate", "Replay-Log", "KV-Cache-Controller"], f"organ drift: {o}"


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00164", "M00167", "M00169", "M00173", "M00175", "M00177",
                "M00179", "M00180"):
        assert mod in body, f"{mod} not in the M011 milestone (must trace to spec)"
