"""M051 DevOps + Fullstack + AI-expert contract lint.

Locks `config/hardware/m051-devops-fullstack-ai-expert.yaml` to the M051 spec:
the AVX-512 Cortex (E0488), Hot Data Layout (E0489), CPU Feature Dispatch
(E0490), Blackwell Oracle Plane (E0491), 4090 Scout Plane (E0492), Memory
Hierarchy (E0493), DevOps Services + Slices (E0494), Container Strategy (E0495),
Policy+Observability+Fullstack+AI-Expert layers (E0496), and the Core
Engineering Law + architect view (E0497). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "hardware" / "m051-devops-fullstack-ai-expert.yaml"
MILESTONE = (REPO_ROOT / "backlog" / "milestones" /
             "M051-devops-fullstack-ai-expert-layer.md")


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M051"


def test_avx512_cortex_thirteen_groups_eight_owns():
    ac = _c()["avx512_cortex"]
    assert len(ac["instruction_groups"]) == 13 and "VP2INTERSECT" in ac["instruction_groups"]
    assert len(ac["cpu_owns"]) == 8 and "reward vectors" in ac["cpu_owns"]
    assert "belongs on CPU" in ac["design_rule"] and "belongs on GPU" in ac["design_rule"]


def test_hot_data_nine_soa_six_hot_loop():
    hd = _c()["hot_data_layout"]
    assert len(hd["soa_arrays"]) == 9 and "score_q16[]" in hd["soa_arrays"]
    assert hd["hot_loop"] == ["load 8-64 state elements", "compare budgets",
                              "merge policy masks", "score candidates",
                              "compress survivors", "enqueue model/tool work"]


def test_cpu_dispatch_four_paths():
    cd = _c()["cpu_feature_dispatch"]
    assert cd["build_paths"] == ["scalar baseline", "AVX2 path", "AVX-512 generic path",
                                 "Zen5 AVX-512 path"]
    assert "-march=znver5" in cd["zen5_flags"]


def test_blackwell_six_uses_and_duty():
    bo = _c()["blackwell_oracle_plane"]
    assert len(bo["uses"]) == 6 and "final code review" in bo["uses"]
    assert bo["duty"] == "The scheduler's duty is to protect the oracle"


def test_scout_4090_nine_uses():
    sp = _c()["scout_plane_4090"]
    assert len(sp["uses"]) == 9 and "rerankers" in sp["uses"]
    assert "separate local machine" in sp["vfio_note"]


def test_memory_hierarchy_six_tiers_eight_fields():
    mh = _c()["memory_hierarchy"]
    tiers = [x["tier"] for x in mh["tiers"]]
    assert tiers == ["ZMM registers", "CPU cache", "RAM", "Blackwell VRAM",
                     "4090 VRAM", "NVMe-ZFS"]
    assert len(mh["memory_item_schema"]) == 8 and "privacy class" in mh["memory_item_schema"]


def test_devops_nine_services_five_slices():
    ds = _c()["devops_services"]
    assert len(ds["services"]) == 9 and "avx-cortex.service" in ds["services"]
    assert ds["slices"] == ["ai-critical.slice", "ai-models.slice", "ai-sandbox.slice",
                            "ai-evals.slice", "ai-background.slice"]


def test_container_strategy_six_classes():
    cs = _c()["container_strategy"]
    assert len(cs["container_classes"]) == 6 and "eval runners" in cs["container_classes"]
    assert "Kubernetes can be a later profile" in cs["doctrine"]


def test_policy_eight_checkpoints_and_runtime_law():
    po = _c()["policy_and_observability"]
    assert len(po["policy_checkpoints"]) == 8 and "adapter load" in po["policy_checkpoints"]
    assert po["policy_doctrine"] == "policy is runtime law, not documentation"


def test_fullstack_cockpit_seven_shows():
    fc = _c()["fullstack_cockpit"]
    assert len(fc["cockpit_shows"]) == 7 and "what can be rolled back" in fc["cockpit_shows"]
    assert "cockpit design" in fc["doctrine"]


def test_ai_expert_six_model_types():
    ae = _c()["ai_expert_layer"]
    assert ae["model_types"] == ["LLM synthesis", "SLM cheap reflex", "RLM recursive context",
                                 "RM-PRM value-process scoring", "VLM perception", "LoRA adapters"]


def test_core_law_three_lines_and_architect_view_six():
    cel = _c()["core_engineering_law"]
    assert len(cel["lines"]) == 3 and cel["lines"][-1] == "That is the advantage."
    av = _c()["architect_view"]["machine_should_feel_like"]
    assert len(av) == 6 and "an OS kernel for intelligence" in av


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00850", "M00853", "M00856", "M00860", "M00862", "M00864", "M00866"):
        assert mod in body, f"{mod} not in the M051 milestone (must trace to spec)"
