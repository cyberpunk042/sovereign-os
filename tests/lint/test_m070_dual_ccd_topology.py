"""M070 dual-CCD-topology contract lint.

Locks `config/hardware/m070-dual-ccd-topology.yaml` to the M070 spec: the
physical bottleneck (E0668), the two CCDs (E0669/E0670), the core-isolation SRP
strategy (E0671), the 3 CCD allocations (E0672-E0674), and CCD-aware
scheduling/memory/IO (E0675-E0677). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "hardware" / "m070-dual-ccd-topology.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M070-dual-ccd-cache-topology-and-core-pinning.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def _alloc(tenant: str) -> dict:
    return next(x for x in _c()["allocations"] if x["tenant"] == tenant)


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M070"


def test_bottleneck_infinity_fabric():
    b = _c()["bottleneck"]
    assert "Infinity Fabric" in b["cause"]
    assert "immediate L3 cache miss" in b["effects"]
    assert "massive cross-die latency penalty" in b["effects"]


def test_two_ccds_verbatim():
    ccds = _c()["ccds"]
    assert [x["ccd"] for x in ccds] == [0, 1]
    assert ccds[0]["cores"] == "0-5" and ccds[0]["threads"] == "0-11"
    assert ccds[1]["cores"] == "6-11" and ccds[1]["threads"] == "12-23"
    assert "32MB" in ccds[0]["l3_cache"] and "32MB" in ccds[1]["l3_cache"]


def test_strategy_srp_partition():
    s = _c()["strategy"]
    assert "partition the processor along CCD boundaries" in s["approach"]
    assert "Magician" in s["goal"]


def test_three_ccd_allocations_verbatim():
    tenants = [x["tenant"] for x in _c()["allocations"]]
    assert tenants == ["The Pulse", "The Weaver + Auditor", "System Host / OS Base"]
    pulse = _alloc("The Pulse")
    assert pulse["ccd"] == 0 and pulse["cores"] == "0-5" and pulse["thread_mask"] == "0xfff"
    weaver = _alloc("The Weaver + Auditor")
    assert weaver["ccd"] == 1 and weaver["cores"] == "6-9" and weaver["thread_mask"] == "0xff000"
    host = _alloc("System Host / OS Base")
    assert host["ccd"] == 1 and host["cores"] == "10-11" and host["thread_mask"] == "0xf00000"


def test_pulse_duties_bitnet_and_wasm_aot():
    d = _alloc("The Pulse")["duties"]
    assert "AVX-512" in d and "bitnet.cpp" in d and "Wasm AOT" in d


def test_ccd_aware_scheduling_memory_io():
    ca = _c()["ccd_aware"]
    assert "cgroup v2 cpuset" in ca["scheduling"]["mechanism"]
    assert "NUMA-style affinity" in ca["memory_placement"]["mechanism"]
    assert "interrupts pinned to System Host CCD 1 cores" in ca["io_routing"]["mechanism"]


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M01156", "M01157", "M01158", "M01159", "M01160", "M01165", "M01169"):
        assert mod in body, f"{mod} not in the M070 milestone (must trace to spec)"
