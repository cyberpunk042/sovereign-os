"""M004 Oracle/Scout/Vector-Arbiter role-split contract lint.

Locks `config/inference/m004-oracle-scout-arbiter.yaml` to the M004 spec: the 5
planes/roles (E0032-E0036), the boundary transport policy (E0037), the
speculative-decoding pipeline (E0038), the constraint-automata principle (E0039),
and bitset routing (E0040). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "inference" / "m004-oracle-scout-arbiter.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M004-oracle-scout-vector-arbiter-roles.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M004"


def test_five_planes_verbatim():
    p = [x["role"] for x in _c()["planes"]]
    assert p == ["Oracle Core", "Scout", "Vector Arbiter", "Memory Plane", "Storage Plane"]
    oracle = next(x for x in _c()["planes"] if x["role"] == "Oracle Core")
    assert oracle["hardware"] == "RTX PRO 6000"
    arbiter = next(x for x in _c()["planes"] if x["role"] == "Vector Arbiter")
    assert "Ryzen 9900X AVX-512" in arbiter["hardware"]


def test_boundary_transport_move_vs_prohibit():
    bt = _c()["boundary_transport"]
    assert bt["move"] == ["tokens", "scores", "refs", "summaries"]
    assert "KV tensors" in bt["prohibit"] and "activations" in bt["prohibit"]


def test_speculative_decoding_pipeline():
    assert "4090 drafts" in _c()["speculative_decoding"]["pipeline"]
    assert "RTX PRO verify" in _c()["speculative_decoding"]["pipeline"]


def test_constraint_automata_principle():
    ca = _c()["constraint_automata"]
    assert ca["principle"] == "model = creative engine / CPU = deterministic law"
    assert len(ca["per_branch_contract_masks"]) == 7


def test_bitset_routing_512():
    assert _c()["bitset_routing"] == "512 candidate memories per ZMM"


def test_cortex_lane_fields_and_law():
    lf = _c()["cortex_lane_fields"]["fields"]
    assert len(lf) == 8 and "agent type" in lf and "grammar" in lf
    law = _c()["cortex_law"]["enforces"]
    assert len(law) == 6 and "GPU routing" in law


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00045", "M00048", "M00051", "M00052", "M00053", "M00058", "M00060"):
        assert mod in body, f"{mod} not in the M004 milestone (must trace to spec)"
