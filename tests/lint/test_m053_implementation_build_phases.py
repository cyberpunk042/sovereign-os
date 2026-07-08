"""M053 implementation-build-phases contract lint.

Locks `config/agent/m053-implementation-build-phases.yaml` to the M053 spec: the
3 intelligence organs + 7 enabling subsystems (E0509), the Core Runtime Sentence
(E0510), the thin vertical slice (E0511), the 10-term Shared Vocabulary (E0512),
the 9 Core Data Objects + 6-property module standard (E0513), and the 11 build
phases (Phase 0..10) + 10-step Critical Build Order + final guiding question
(E0514-E0517). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m053-implementation-build-phases.yaml"
MILESTONE = (REPO_ROOT / "backlog" / "milestones" /
             "M053-implementation-language-11-build-phases.md")


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def _phase(n: int) -> dict:
    return next(x for x in _c()["build_phases"] if x["phase"] == n)


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M053"


def test_three_organs_seven_subsystems():
    o = [x["organ"] for x in _c()["intelligence_organs"]]
    assert o == ["Blackwell Oracle", "4090 Scout", "AVX-512 Cortex"]
    s = [x["subsystem"] for x in _c()["enabling_subsystems"]]
    assert s == ["Gateway", "Policy", "Memory", "Workflow", "Sandbox", "Observability", "Evals"]


def test_core_runtime_sentence_seven_propose_seven_decide():
    crs = _c()["core_runtime_sentence"]
    assert crs["sentence"] == "Models propose; the runtime commits"
    assert len(crs["model_proposes"]) == 7 and "tool calls" in crs["model_proposes"]
    assert crs["runtime_decides"] == ["allowed", "routed", "verified", "sandboxed",
                                      "escalated", "committed", "rejected"]


def test_vertical_slice_seven_steps_five_additions():
    vs = _c()["vertical_slice"]
    assert vs["steps"] == ["Client request", "local gateway", "profile resolution",
                           "model route", "tool/policy trace", "response", "replay record"]
    assert len(vs["later_additions"]) == 5 and "AVX hot path" in vs["later_additions"]


def test_shared_vocabulary_ten_terms():
    t = [x["term"] for x in _c()["shared_vocabulary"]["terms"]]
    assert t == ["Profile", "Policy", "Route", "Frame", "Trace", "Commit", "Memory",
                 "Oracle", "Scout", "Cortex"], f"vocab drift: {t}"


def test_nine_core_data_objects_six_property_standard():
    o = [x["object"] for x in _c()["core_data_objects"]["objects"]]
    assert o == ["Request", "Profile", "PolicyDecision", "ModelRoute", "Frame",
                 "ToolIntent", "TraceEvent", "MemoryRef", "EvalResult"]
    mes = _c()["module_exposure_standard"]
    assert mes["properties"] == ["state", "configuration", "events", "policy hooks",
                                 "observability", "fallback behavior"]
    assert "not ready for autonomy" in mes["doctrine"]


def test_eleven_build_phases_present():
    phases = [x["phase"] for x in _c()["build_phases"]]
    assert phases == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10], f"phase drift: {phases}"
    names = [x["name"] for x in _c()["build_phases"]]
    assert names == ["Platform Truth", "Gateway Spine", "Model Fabric", "Policy And Trace",
                     "Sandbox Execution", "Memory And MAP", "Evals And Goldilocks",
                     "AVX-512 Cortex", "Model Lab And LoRA Foundry", "Continuity", "Full Cockpit"]


def test_phase0_validates_five_things():
    p0 = _phase(0)
    assert p0["validate"] == ["CPU flags", "GPU topology", "Driver stack", "Storage", "OS security"]
    assert p0["output"] == "hardware capability report"


def test_phase1_model_aliases():
    p1 = _phase(1)
    assert p1["model_aliases"] == ["jean/local-fast", "jean/oracle", "jean/private"]
    assert "owning the front door" in p1["note"]


def test_phase7_avx_six_targets_do_not_start_here():
    p7 = _phase(7)
    assert len(p7["targets"]) == 6 and "policy mask fusion" in p7["targets"]
    assert "Do not start here" in p7["note"]


def test_phase10_eleven_ui_surfaces():
    p10 = _phase(10)
    assert len(p10["ui_surfaces"]) == 11 and "hardware pressure" in p10["ui_surfaces"]
    assert "cockpit of an intelligence machine" in p10["note"]


def test_critical_build_order_ten_steps_and_guiding_question():
    cbo = _c()["critical_build_order"]
    assert cbo["order"] == ["know hardware", "own gateway", "route models", "trace everything",
                            "gate tools", "add memory", "add evals", "optimize with AVX",
                            "adapt with LoRA", "deepen continuity"]
    assert "smallest vertical slice" in cbo["guiding_question"]


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00886", "M00888", "M00891", "M00892", "M00894", "M00899", "M00900"):
        assert mod in body, f"{mod} not in the M053 milestone (must trace to spec)"
