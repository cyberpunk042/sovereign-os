"""M040 hyper-features contract lint.

Locks `config/hardware/m040-hyper-features.yaml` to the M040 spec: the 4 MIG
profiles (E0379), the FP4 roster + qualification axes (E0380), the 6 AVX-512 hot
tables + ops (E0381), and the GDS adoption phases (E0382). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "hardware" / "m040-hyper-features.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M040-hyper-features-mig-fp4-vfio-zfs-commit-gate.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M040"


def test_four_mig_profiles_verbatim():
    p = [x["profile"] for x in _c()["mig_profiles"]]
    assert p == ["Monolith", "Partition", "Sandbox", "Multi-tenant"], f"MIG drift: {p}"


def test_multi_tenant_includes_claude_code():
    mt = next(x for x in _c()["mig_profiles"] if x["profile"] == "Multi-tenant")
    assert "Claude Code" in mt["layout"]


def test_fp4_roster_five_candidates():
    c = _c()["fp4_roster"]["candidates"]
    assert c == ["BF16-baseline", "FP8", "NVFP4-MXFP4", "GPTQ-AWQ-SmoothQuant",
                 "KV-quantized"], f"FP4-roster drift: {c}"


def test_qualification_nine_axes():
    a = _c()["qualification_axes"]["axes"]
    assert len(a) == 9 and "agent_trajectory" in a and "vram" in a


def test_six_hot_tables_verbatim():
    t = _c()["hot_tables"]["tables"]
    assert t == ["BranchTable", "MemoryMetaTable", "ToolCapabilityTable",
                 "ModelRegistryTable", "EvalResultTable", "KVBlockTable"], (
        f"hot-table drift: {t}")


def test_avx512_ops_five():
    o = _c()["avx512_ops"]["ops"]
    assert o == ["filter", "intersect", "popcount-score", "compress-survivors",
                 "route-batches"], f"ops drift: {o}"


def test_gds_three_phases():
    p = _c()["gds_adoption_phases"]["phases"]
    assert [x["phase"] for x in p] == [1, 2, 3]


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00663", "M00666", "M00667", "M00668", "M00669", "M00675", "M00676"):
        assert mod in body, f"{mod} not in the M040 milestone (must trace to spec)"
