"""M086 AVX-512 scalar-to-SIMD lift-plan contract lint.

Locks `config/hardware/m086-avx512-simd-lift-plan.yaml` to the M086 spec: the
9-flag inventory, the 5-step lift, and the 5 epics E0817-E0821 with status. No
minimization; VP2INTERSECT-has-no-Zen5-hardware fact preserved.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "hardware" / "m086-avx512-simd-lift-plan.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M086-avx512-scalar-reference-to-simd-lift-plan.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def _flag(name: str) -> dict:
    return next(x for x in _c()["flag_inventory"] if x["flag"] == name)


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M086"


def test_nine_flag_inventory():
    fi = _c()["flag_inventory"]
    assert [x["n"] for x in fi] == list(range(1, 10))
    flags = [x["flag"] for x in fi]
    assert "avx512_vnni" in flags and "avx512_bf16" in flags and "avx512_vp2intersect" in flags


def test_vnni_and_bf16_wired():
    assert "wired (Precision::Int8)" in _flag("avx512_vnni")["engine"]
    assert "wired (Precision::Bf16)" in _flag("avx512_bf16")["engine"]
    assert _flag("avx512_vnni")["intrinsic"] == "_mm512_dpbusd_epi32"


def test_vp2intersect_no_zen5_hardware():
    vp = _flag("avx512_vp2intersect")
    assert vp["zen5"] is False
    assert "no Zen 5 hardware" in vp["intrinsic"]
    assert "scalar-only forever" in _c()["vp2intersect_note"]


def test_five_step_lift_verbatim():
    steps = _c()["five_step_lift"]
    assert [x["step"] for x in steps] == [1, 2, 3, 4, 5]
    names = [x["name"] for x in steps]
    assert names == ["Intrinsic kernel", "Runtime dispatch", "Build flags",
                     "Differential tests", "Capability + profile gate"]
    assert "is_x86_feature_detected!" in steps[1]["detail"]
    assert "target-cpu=znver5" in steps[2]["detail"]


def test_five_epics_status():
    e = {x["id"]: x["status"] for x in _c()["epics"]}
    assert e["E0817"] == "done" and e["E0818"] == "done" and e["E0819"] == "done"
    assert e["E0820"] == "open" and e["E0821"] == "open"


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for tag in ("avx512_vnni", "avx512_bf16", "avx512_vp2intersect", "E0820", "E0821",
                "target-cpu=znver5"):
        assert tag in body, f"{tag} not in the M086 milestone (must trace to spec)"
