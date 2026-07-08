"""M059 sovereign-close peace-machine contract lint.

Locks `config/agent/m059-sovereign-close-peace-machine.yaml` to the M059 spec:
the sovereign workstation definition (E0568), the substrate bindings (E0569),
the Core Law 6-line (E0570), situated intelligence (E0571), the runtime loop
(E0572), the 8 user-choice dimensions (E0573), the adaptation ladder
(E0574/E0575), the super-model definition (E0576), and the peace-machine
properties (E0577). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m059-sovereign-close-peace-machine.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M059-sovereign-close-peace-machine.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M059"


def test_definition_local_intelligence_os():
    assert "local intelligence operating environment" in _c()["definition"]["statement"]
    assert "become one system" in _c()["definition"]["statement"]


def test_substrate_bindings_verbatim():
    comps = [x["component"] for x in _c()["substrate_bindings"]]
    assert comps == ["Ryzen 9900X AVX-512", "RTX PRO 6000 Blackwell", "RTX 4090",
                     "RAM + ZFS + NVMe", "Debian 13 / Ubuntu 24", "Gateway"]
    ryzen = _c()["substrate_bindings"][0]
    assert "deterministic cortex" in ryzen["role"]


def test_core_law_six_lines():
    lines = _c()["core_law"]["lines"]
    assert lines == ["Models propose.", "Runtime routes.", "CPU enforces.",
                     "Tools prove.", "ZFS remembers.", "User chooses."]


def test_situated_intelligence_nine_signals():
    si = _c()["situated_intelligence"]
    assert si["signals"] == ["repos", "tests", "memory", "hardware", "policies", "cost",
                             "continuity", "rollback", "consent"]


def test_runtime_loop_seven_steps():
    assert _c()["runtime_loop"]["steps"] == ["MAP", "SPEC", "TEST", "ACT", "EVAL",
                                             "COMMIT", "LEARN"]


def test_eight_user_choice_dimensions():
    d = _c()["user_choice_dimensions"]["dimensions"]
    assert d == ["fast/careful", "local/cloud", "scout/oracle", "sandbox/host",
                 "manual/autonomous", "private/shared", "cheap/best", "exploratory/spec-driven"]


def test_adaptation_ladder_six_pre_and_post():
    al = _c()["adaptation_ladder"]
    assert al["pre_fine_tune"] == ["routing", "memory", "evals", "profiles", "workflows",
                                   "tool feedback"]
    assert "crystallize proven behavior into weights" in al["post_crystallization"]


def test_super_model_definition():
    assert _c()["super_model"]["definition"] == ("The super-model is not one checkpoint. "
                                                 "The super-model is the whole governed machine")


def test_peace_machine_five_properties():
    p = _c()["peace_machine"]["properties"]
    assert p == ["powerful enough to act", "disciplined enough to explain itself",
                 "reversible enough to trust", "flexible enough to evolve",
                 "sovereign enough that intelligence remains in the user's hands"]


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00986", "M00987", "M00989", "M00990", "M00992", "M00993", "M00994"):
        assert mod in body, f"{mod} not in the M059 milestone (must trace to spec)"
