"""M085 Zen5 AVX-512 three-tier instruction contract lint.

Locks `config/hardware/m085-zen5-three-tier-instructions.yaml` to the M085 spec:
the 3 instruction tiers (E0808-E0813), the margin popcount + PAM-3 path
(E0814/E0815), and precision-as-flexible-profile (E0816), plus the runtime
status. No minimization; operator French labels + VPDOTBF16PLUS->VDPBF16PS
mapping preserved.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "hardware" / "m085-zen5-three-tier-instructions.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M085-zen5-avx512-three-tier-instruction-exploitation.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def _t(tid: str) -> dict:
    return next(x for x in _c()["tiers"] if x["id"] == tid)


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M085"


def test_driver_dual_512bit_pipes():
    assert "Dual Native 512-bit Pipes" in _c()["driver"]


def test_three_tiers_present():
    ids = [x["id"] for x in _c()["tiers"]]
    assert ids == ["T1", "T2", "T3"]


def test_t1_vpdpbusd_int8_and_bf16_mapping():
    t1 = _t("T1")
    mnemonics = [x["mnemonic"] for x in t1["instructions"]]
    assert "VPDPBUSD" in mnemonics and "VPDOTBF16PLUS" in mnemonics
    bf16 = next(x for x in t1["instructions"] if x["mnemonic"] == "VPDOTBF16PLUS")
    assert bf16["x86"] == "VDPBF16PS" and bf16["flag"] == "avx512_bf16"


def test_t2_ternlog_and_intersect():
    t2 = _t("T2")
    mn = [x["mnemonic"] for x in t2["instructions"]]
    assert "VPTERNLOGD/Q" in mn and "VP2INTERSECTD/Q" in mn


def test_t3_permb_and_compress():
    t3 = _t("T3")
    mn = [x["mnemonic"] for x in t3["instructions"]]
    assert "VPERMB/VPSHLDV" in mn and "VPCOMPRESSB/VPEXPANDB" in mn


def test_margin_popcount_and_pam3():
    m = _c()["margin"]
    assert "VPOPCNT" in m["popcount"] and "VPTERNLOG" in m["popcount"]
    assert "PAM-3" in m["signal"] and "GDDR7" in m["signal"]


def test_precision_profile_flexible():
    pp = _c()["precision_profile"]
    assert "PrecisionProfile" in pp["crate"]
    assert "per-layer precision" in pp["shape"]


def test_runtime_status_partitioned():
    rs = _c()["runtime_status"]
    assert any("E0808" in x for x in rs["built_and_running"])
    assert any("E0810" in x for x in rs["built_awaiting_consumer"])
    assert any("E0815" in x for x in rs["catalog_only"])


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for tag in ("E0808", "E0809", "E0812", "E0813", "VPDPBUSD", "VDPBF16PS", "VP2INTERSECT"):
        assert tag in body, f"{tag} not in the M085 milestone (must trace to spec)"
