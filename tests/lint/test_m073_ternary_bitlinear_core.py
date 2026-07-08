"""M073 ternary-BitLinear-core contract lint.

Locks `config/inference/m073-ternary-bitlinear-core.yaml` to the M073 spec: the
ternary weight set (E0698), the 1.58-bit storage (E0699), multiplication
elimination (E0700), the energy + profile shift (E0701/E0702), the BitLinear core
(E0703), ternary packing (E0704), the frameworks (E0705), and the AVX-512 LUT
ops (E0706). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "inference" / "m073-ternary-bitlinear-core.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M073-one-bit-ternary-logic-bitlinear-core.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M073"


def test_ternary_weight_set_verbatim():
    t = _c()["ternary_weight_set"]
    assert t["set"] == [-1, 0, 1]
    assert "BitNet b1.58" in t["lineage"]


def test_storage_log2_3():
    s = _c()["storage"]
    assert "log2(3) ~ 1.585" == s["bits_per_parameter"]


def test_multiplication_elimination_mapping():
    m = {x["weight"]: x["op"] for x in _c()["multiplication_elimination"]["mapping"]}
    assert m[1] == "activation added to accumulator"
    assert m[-1] == "activation subtracted from accumulator"
    assert m[0] == "No-Op, bypassed entirely"


def test_energy_and_profile_shift():
    es = _c()["energy_shift"]
    assert "integer add/sub" in es["substitution"]
    ps = _c()["profile_shift"]
    assert ps["away_from"] == "raw TFLOPS throughput"
    assert "memory bandwidth optimization" in ps["toward"]


def test_bitlinear_replaces_gemm():
    bl = _c()["bitlinear_core"]
    assert "GEMM (Floating-Point General Matrix Multiplication)" in bl["replaces"]
    assert "GPU Tensor Core + CPU FPU saturation" in bl["eliminates"]


def test_packing_two_bits():
    p = _c()["packing"]
    assert p["bits_per_parameter"] == 2 and "byte boundary alignment" in p["note"]


def test_frameworks_bitnet_tmac():
    f = _c()["frameworks"]
    assert f["names"] == ["bitnet.cpp", "T-MAC"]
    assert f["property"] == "no de-quantization at execution"


def test_lut_operations_avx512():
    lo = _c()["lut_operations"]["mechanism"]
    assert "Bit-wise Lookup Table (LUT)" in lo and "AVX-512" in lo


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M01207", "M01208", "M01209", "M01212", "M01213", "M01214", "M01218"):
        assert mod in body, f"{mod} not in the M073 milestone (must trace to spec)"
