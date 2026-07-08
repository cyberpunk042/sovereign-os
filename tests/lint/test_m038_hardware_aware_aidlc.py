"""M038 hardware-aware-AIDLC contract lint.

Locks `config/hardware/m038-hardware-aware-aidlc.yaml` to the M038 spec: the
hardware inventory (E0359), the Hardware Law + IOMMU note (E0360), and the
compiler target + 7 AVX-512 instruction families (E0361). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "hardware" / "m038-hardware-aware-aidlc.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M038-hardware-aware-aidlc.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M038"


def test_hardware_inventory_four_components():
    inv = _c()["hardware_inventory"]
    comps = [x["component"] for x in inv]
    assert comps == ["Ryzen 9 9900X", "RTX PRO 6000 Blackwell", "RTX 4090",
                     "ProArt X870E-Creator"], f"inventory drift: {comps}"


def test_blackwell_96gb_and_fp4():
    bw = next(x for x in _c()["hardware_inventory"] if "Blackwell" in x["component"])
    assert "96GB" in bw["spec"] and "FP4" in bw["spec"]


def test_hardware_law_gpus_are_separate_experts():
    law = _c()["hardware_law"]["law"]
    assert "separate experts" in law and "one memory pool" in law


def test_compiler_target_znver5():
    assert _c()["compiler_target"]["march"] == "znver5"


def test_seven_avx512_instruction_families():
    instrs = [x["instr"] for x in _c()["avx512_instructions"]]
    assert instrs == ["k-masks", "VPTERNLOG", "VPCOMPRESS/VPEXPAND", "VPOPCNTDQ",
                      "VP2INTERSECT", "VBMI/VBMI2", "VNNI/BF16"], f"instr drift: {instrs}"
    assert len(instrs) == 7


def test_iommu_note_vfio_passthrough():
    n = _c()["iommu_note"]["note"]
    assert "VFIO" in n and "peer-to-peer" in n


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00629", "M00632", "M00633", "M00634", "M00635", "M00636", "M00642"):
        assert mod in body, f"{mod} not in the M038 milestone (must trace to spec)"
