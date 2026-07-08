"""M039 AVX-512-cortex-hot-path contract lint.

Locks `config/hardware/m039-avx512-cortex-hot-path.yaml` to the M039 spec: the
workload shape (E0369), the 9 hot-path SoA arrays + Zen 5 lane counts (E0370), the
brainstem principle (E0371), and the ops-to-roles mapping (E0372). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "hardware" / "m039-avx512-cortex-hot-path.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M039-avx512-cortex-hot-path.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M039"


def test_nine_hot_path_soa_arrays_verbatim():
    a = _c()["hot_path_soa"]["arrays"]
    assert a == ["branch_id", "control_u64", "budget_u16", "risk_u8", "score_q16",
                 "route_u8", "model_id_u16", "memory_ref_u64", "kv_ref_u64"], (
        f"hot-path SoA drift: {a}")
    assert len(a) == 9


def test_zen5_lane_counts_verbatim():
    l = _c()["zen5_lane_counts"]["lanes"]
    assert l == {"u64": 8, "u32": 16, "u16": 32, "u8": 64, "boolean_flags": 512}, (
        f"lane-count drift: {l}")


def test_workload_shape_bursts_not_giant_burn():
    s = _c()["workload_shape"]["shape"]
    assert "bursts" in s and "NOT one giant burn" in s


def test_brainstem_principle():
    assert _c()["brainstem_principle"]["statement"] == "CPU is the goldilocks brainstem"


def test_ops_to_roles_five_mappings():
    m = _c()["ops_to_roles"]["mapping"]
    ops = {x["op"]: x["role"] for x in m}
    assert ops["simdjson"] == "parsing" and ops["VPTERNLOG"] == "policy-fusion"
    assert len(m) == 5


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00646", "M00648", "M00656", "M00657", "M00658", "M00659"):
        assert mod in body, f"{mod} not in the M039 milestone (must trace to spec)"
