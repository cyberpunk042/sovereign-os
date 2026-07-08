"""M075 SRP-hardware-topology contract lint.

Locks `config/inference/m075-srp-topology.yaml` to the M075 spec: the Vibe
Managing harness (E0718), the 3 SRP agents mapped to hardware (E0719-E0721) with
per-agent runtime (E0722-E0724) and justification (E0725-E0727), plus the
topology branches. No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
R12530: SRP topology = sovereign-os runtime owns.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "inference" / "m075-srp-topology.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M075-srp-hardware-topology-conductor-logic-oracle.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def _a(aid: str) -> dict:
    return next(x for x in _c()["agents"] if x["id"] == aid)


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M075"


def test_doctrinal_srp_to_hardware():
    assert "Single Responsibility Principle (SRP) directly to physical hardware layers" in _c()["doctrinal_anchor"]


def test_harness_vibe_managing():
    h = _c()["harness"]
    assert h["name"] == "Vibe Managing Orchestration Harness"


def test_three_agents_hardware_mapping():
    ids = [x["id"] for x in _c()["agents"]]
    assert ids == ["Conductor", "Logic Engine", "Oracle Core"]
    assert _a("Conductor")["hardware"] == "CPU"
    assert _a("Logic Engine")["hardware"] == "GPU 0 RTX 4090"
    assert _a("Oracle Core")["hardware"] == "GPU 1 Blackwell PRO 6000"


def test_srp_domains_verbatim():
    assert _a("Conductor")["srp_domain"] == "Routing & State Fabric"
    assert _a("Logic Engine")["srp_domain"] == "Ingestion & Translation"
    assert _a("Oracle Core")["srp_domain"] == "Long-Term Deep Reasoning"


def test_conductor_bitnet_runtime():
    c = _a("Conductor")
    assert "bitnet.cpp" in c["runtime"] and "high-priority CPU cores" in c["runtime"]
    assert "instantaneous branching" in c["justification"]


def test_logic_quantized_podman():
    lg = _a("Logic Engine")
    assert "Llama-3-70B Q4_K_M" in lg["runtime"] and "Podman" in lg["runtime"]
    assert "24GB VRAM ceiling" in lg["justification"]


def test_oracle_fp16_96gb():
    o = _a("Oracle Core")
    assert "FP16" in o["runtime"] and "96GB Blackwell pool" in o["runtime"]
    assert "quantization degradation" in o["justification"]


def test_topology_branches_three():
    b = [x["branch"] for x in _c()["topology_branches"]]
    assert b == ["Host CPU Threads", "Local GPU 0", "Local GPU 1"]


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M01241", "M01242", "M01243", "M01244", "M01248", "M01250", "M01252"):
        assert mod in body, f"{mod} not in the M075 milestone (must trace to spec)"
