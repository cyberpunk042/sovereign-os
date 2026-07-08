"""M006 deterministic-control-substrate (DCR v0) contract lint.

Locks `config/agent/m006-deterministic-control-substrate.yaml` to the M006 spec:
the 64-bit control word (E0047), the Deterministic Cortex Runtime v0 components
(E0048), the main loop (E0049), and CPU-as-deterministic-law (E0050). No
minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m006-deterministic-control-substrate.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M006-deterministic-ai-control-substrate.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M006"


def test_control_word_nine_fields():
    cw = {x["name"]: x["bits"] for x in _c()["control_word"]["fields"]}
    assert len(cw) == 9
    assert cw["route"] == "0..3" and cw["spec_depth"] == "48..55" and cw["lifecycle"] == "56..63"


def test_three_planes():
    p = [x["plane"] for x in _c()["planes"]]
    assert p == ["RTX PRO 6000", "RTX 4090", "Ryzen AVX-512"]
    arb = next(x for x in _c()["planes"] if x["plane"] == "Ryzen AVX-512")
    assert "deterministic executive" in arb["role"]


def test_population_evaluation():
    assert _c()["population_evaluation"] == "8 x u64 branches / 64 x u8 states / 512 boolean flags per ZMM"


def test_dcr_eight_components():
    comps = [x["component"] for x in _c()["dcr_components"]]
    assert comps == ["Branch Arena", "Token Candidate Queue", "Grammar/JSON Automata",
                     "Tool Permission Engine", "Memory Admission Policy",
                     "Speculation Verifier", "Replay Log Writer", "Metrics Emitter"]


def test_main_loop_seven_steps():
    steps = _c()["main_loop"]["steps"]
    assert len(steps) == 7
    assert steps[0] == "user task enters control plane"
    assert steps[-1] == "memory update"


def test_cpu_law_six():
    law = _c()["cpu_law"]
    assert law == ["masks invalid tokens", "rejects forbidden tools", "expires branches",
                   "enforces schema", "admits memory", "decides GPU routing"]


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00079", "M00081", "M00082", "M00083", "M00088", "M00090", "M00095"):
        assert mod in body, f"{mod} not in the M006 milestone (must trace to spec)"
