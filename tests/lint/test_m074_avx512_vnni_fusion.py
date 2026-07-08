"""M074 AVX-512 VNNI hardware-fusion contract lint.

Locks `config/hardware/m074-avx512-vnni-fusion.yaml` to the M074 spec: the Zen 5
true 512-bit ZMM (E0708), the ZMM register layout (E0709/E0710), the VNNI
extension (E0711), the VPDPBUSD single-cycle MAC (E0712), the LUT matrix ops
(E0713), CPU-local inference + throughput (E0714/E0715), PCIe bypass (E0716), and
boot verification (E0717). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "hardware" / "m074-avx512-vnni-fusion.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M074-avx-512-vnni-hardware-fusion.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M074"


def test_zen5_true_512bit_not_double_pumped():
    z = _c()["zen5_zmm"]
    assert "true 512-bit wide ZMM registers" in z["claim"]
    assert "double-pump two 256-bit" in z["legacy_contrast"]


def test_zmm_layout_64_int8_128_int4():
    zl = _c()["zmm_layout"]
    assert zl["width_bits"] == 512
    packs = {x["elements"]: x["type"] for x in zl["packings"]}
    assert packs[64] == "8-bit integer (INT8)"
    assert "BitNet v2" in packs[128]


def test_vnni_and_vpdpbusd():
    assert "Vector Neural Network Instructions" in _c()["vnni"]["extension"]
    v = _c()["vpdpbusd"]
    assert "packed ternary weights" in v["operation"] and "32-bit destination registers" in v["operation"]
    assert v["speed"] == "a fraction of a clock cycle"
    assert "Multiply-Accumulate" in v["equivalence"]


def test_lut_no_dequant():
    lo = _c()["lut_matrix_ops"]["property"]
    assert "no de-quantization" in lo and "M073 ternary packing" in lo


def test_cpu_local_throughput_and_pcie_bypass():
    ci = _c()["cpu_local_inference"]
    assert "5-12 tokens/sec" in ci["throughput"]
    assert "GPU memory unencumbered" in ci["pcie_bypass"]


def test_boot_verification_check01():
    bv = _c()["boot_verification"]["rule"]
    assert "M072 Check 01" in bv and "avx512_vnni" in bv and "avx512_bf16" in bv


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M01224", "M01225", "M01226", "M01227", "M01229", "M01231", "M01233"):
        assert mod in body, f"{mod} not in the M074 milestone (must trace to spec)"
