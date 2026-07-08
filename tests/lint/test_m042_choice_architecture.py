"""M042 choice-architecture contract lint.

Locks `config/agent/m042-choice-architecture.yaml` to the M042 spec: the 6
pillars (E0398), the 7-step methodology + definitions (E0399), the 7 map types +
6 inheritance contracts + vault-proxy + 7-axis routing + 8-slot model lab
(E0400), the choice envelope (E0404), the 4 profile bundles + profile/policy/
choice distinction (E0405), the 8 inheritance artifacts (E0406), the 8
transparency questions + 8 negotiation axes (E0407). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m042-choice-architecture.yaml"
MILESTONE = (REPO_ROOT / "backlog" / "milestones" /
             "M042-choice-architecture-sovereignty-as-policy-composable.md")


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M042"


def test_six_pillars_verbatim():
    p = [x["pillar"] for x in _c()["pillars"]]
    assert p == ["MAP / map-before-act", "Spec + workflow orchestration",
                 "Agent harness engineering", "Routing + cost-aware model selection",
                 "Sandboxes + secrets isolation",
                 "Model compression + hardware-aware model lab"], f"pillar drift: {p}"


def test_methodology_seven_steps_with_definitions():
    m = _c()["methodology"]["steps"]
    steps = [x["step"] for x in m]
    assert steps == ["MAP", "SPEC", "TEST", "ACT", "EVAL", "COMMIT", "LEARN"]
    learn = next(x for x in m if x["step"] == "LEARN")
    assert learn["definition"] == "update memory, model registry, profiles, skills"


def test_seven_map_types_verbatim():
    mt = _c()["map_types"]["maps"]
    assert mt == ["repo", "test", "tool", "risk", "memory", "GUI-world", "dependency"]


def test_six_inheritance_contracts_verbatim():
    c = _c()["inheritance_contracts"]["contracts"]
    assert c == ["SPEC.md", "WORKFLOW.md", "PROFILES.yaml", "EVALS.yaml",
                 "POLICY.yaml", "MODEL_REGISTRY.yaml"], f"contract drift: {c}"


def test_vault_proxy_stub_keys_and_gateway_ownership():
    vp = _c()["vault_proxy"]
    assert vp["agents_get_stub_keys"] == ["Claude Code", "OpenCode", "Cline"]
    assert "real keys" in vp["jean_gateway_owns"] and "routing" in vp["jean_gateway_owns"]


def test_seven_routing_axes_verbatim():
    a = _c()["routing_axes"]["axes"]
    assert a == ["simple/complex", "private/public", "safe/risky",
                 "coding/research/gui", "local/cloud", "fast/careful", "cheap/oracle"]


def test_model_lab_eight_slots_and_fast_blt_rules():
    ml = _c()["model_lab"]
    assert len(ml["slots"]) == 8 and "BF16 baseline" in ml["slots"]
    assert ml["fast_blt_rules"] == ["reduce forward passes", "speculate cheaply",
                                    "verify carefully", "avoid memory bandwidth waste"]


def test_nine_boundary_choices_and_sovereignty_closing():
    ca = _c()["choice_architecture"]
    assert len(ca["boundary_choices"]) == 9 and "local or cloud" in ca["boundary_choices"]
    assert ca["closing"] == "That is sovereignty"


def test_choice_envelope_model_route_requires():
    ex = _c()["choice_envelope"]["examples"]
    mr = next(x for x in ex if x["domain"] == "model_route")
    assert mr["default"] == "local_oracle"
    assert mr["requires"]["cloud_anthropic"] == ["user_approval", "cost_budget",
                                                 "privacy_clearance"]
    assert _c()["choice_envelope"]["closing"] == "the system becomes a choice compiler"


def test_four_profile_bundles_and_distinction():
    b = [x["profile"] for x in _c()["profile_bundles"]["bundles"]]
    assert b == ["private", "careful", "fast", "sovereign"], f"bundle drift: {b}"
    ppc = _c()["profile_policy_choice"]
    assert ppc["profile"] == "starting posture" and ppc["choice"] == "user agency"


def test_eight_inheritance_artifacts_verbatim():
    a = _c()["inheritance_artifacts"]["artifacts"]
    assert a == ["VISION.md", "ARCHITECTURE.md", "METHODOLOGY.md", "PROFILES.yaml",
                 "POLICY.yaml", "MODEL_REGISTRY.yaml", "HARDWARE_PROFILES.yaml",
                 "EVALS.yaml"], f"artifact drift: {a}"


def test_legible_control_questions_and_axes():
    lc = _c()["legible_control"]
    assert len(lc["transparency_questions"]) == 8
    assert lc["final_phrase"] == "User-sovereign adaptive intelligence runtime"
    assert lc["negotiation_axes"] == ["capability", "control", "cost", "privacy",
                                      "speed", "quality", "autonomy", "reversibility"]


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00697", "M00702", "M00703", "M00709", "M00710", "M00712", "M00713"):
        assert mod in body, f"{mod} not in the M042 milestone (must trace to spec)"
