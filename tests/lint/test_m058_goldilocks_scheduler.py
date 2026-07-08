"""M058 Goldilocks-scheduler contract lint.

Locks `config/inference/m058-goldilocks-scheduler.yaml` to the M058 spec: the 7
Resource Types (E0558), the 8 Queue Types + 8 item fields (E0559), the 6
Scheduling Policies (E0560), Blackwell/4090/CPU-AVX scheduling (E0561-E0563),
KV/Context scheduling (E0564), Memory + Tool scheduling (E0565), Backpressure
(E0566), and the Goldilocks Objective + Key Law (E0567). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "inference" / "m058-goldilocks-scheduler.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M058-hardware-aware-scheduling-goldilocks.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M058"


def test_seven_resource_types_verbatim():
    r = [x["resource"] for x in _c()["resource_types"]]
    assert r == ["CPU", "GPU-Blackwell", "GPU-4090", "RAM", "NVMe-ZFS", "Network", "Human"]
    bw = next(x for x in _c()["resource_types"] if x["resource"] == "GPU-Blackwell")
    assert bw["tracked"] == ["VRAM", "compute", "KV cache", "batch slots"]


def test_eight_queue_types_eight_item_fields():
    q = _c()["queues"]
    types = [x["queue"] for x in q["types"]]
    assert types == ["oracle_queue", "scout_queue", "embedding_queue", "tool_queue",
                     "eval_queue", "memory_queue", "human_gate_queue", "background_queue"]
    assert q["item_fields"] == ["priority", "deadline", "risk", "cost", "expected_value",
                                "profile", "hardware_affinity", "cache_affinity"]


def test_six_scheduling_policies_verbatim():
    p = [x["profile"] for x in _c()["scheduling_policies"]["policies"]]
    assert p == ["fast", "careful", "private", "autonomous", "experimental", "production"]


def test_blackwell_five_accept_four_avoid():
    bw = _c()["blackwell_scheduling"]
    assert len(bw["accept"]) == 5 and "final synthesis" in bw["accept"]
    assert len(bw["avoid"]) == 4 and "cheap classification" in bw["avoid"]
    assert bw["rule"] == "Keep the Blackwell hot with meaningful work, not busy with junk"


def test_4090_seven_uses_three_work_ahead():
    s = _c()["scheduling_4090"]
    assert len(s["use_for"]) == 7 and "failure classification" in s["use_for"]
    assert len(s["work_ahead"]) == 3


def test_avx_eight_hot_ops_and_batch_rule():
    a = _c()["avx_scheduling"]
    assert len(a["hot_ops"]) == 8 and "compute route masks" in a["hot_ops"]
    assert a["rule"] == "batch when useful, don't worship SIMD"


def test_kv_four_strategies():
    k = _c()["kv_scheduling"]["strategies"]
    assert k == ["prefix-cache awareness", "parent context sharing",
                 "prefill-vs-decode classification", "eviction-value calculation"]


def test_memory_staged_retrieval_and_tool_four_classes():
    m = _c()["memory_scheduling"]
    assert m["staged_retrieval"] == ["bitset", "popcount", "embedding", "graph", "oracle"]
    t = _c()["tool_scheduling"]
    assert len(t["classification"]) == 4 and "destructive human-gate" in t["classification"]


def test_backpressure_three_signals():
    b = _c()["backpressure"]
    assert b["signals"] == ["PSI", "DCGM", "trace metrics"]


def test_goldilocks_objective_six_units_and_key_law():
    go = _c()["goldilocks_objective"]
    assert go["objective"] == "maximize useful intelligence per unit of"
    assert go["per_unit_of"] == ["latency", "cost", "risk", "energy", "human attention",
                                 "hardware pressure"]
    kl = _c()["key_law"]["law"]
    assert "Never let expensive cognition wait on cheap preparation" in kl
    assert "cheap speculation commit without expensive verification" in kl


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00969", "M00970", "M00972", "M00974", "M00976", "M00981", "M00982"):
        assert mod in body, f"{mod} not in the M058 milestone (must trace to spec)"
