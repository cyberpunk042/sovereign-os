"""M078 HolderPO + GRPO post-training contract lint.

Locks `config/agent/m078-holderpo-grpo.yaml` to the M078 spec: the GRPO baseline
(E0748), the HolderPO framework (E0749), the Holder parameter p (E0750), the
theoretical proof (E0751), the dynamic annealing (E0752), the benchmarks
(E0753/E0754), and the integrations (E0755-E0757). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m078-holderpo-grpo.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M078-holderpo-grpo-post-training-pipeline.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M078"


def test_grpo_baseline():
    g = _c()["grpo_baseline"]
    assert "Group Relative Policy Optimisation" in g["name"]
    assert "group of sampled trajectories" in g["mechanism"]
    assert "fixed aggregation mechanism" in g["limitation"]


def test_holderpo_framework_and_p():
    h = _c()["holderpo"]
    assert "Holder mean" in h["framework"]
    assert "gradient concentration and variance bounds" in h["parameter_p"]


def test_theoretical_proof_large_and_small_p():
    tp = _c()["theoretical_proof"]
    assert "amplify sparse learning signals" in tp["large_p"]["effect"]
    assert "bounds gradient variance" in tp["small_p"]["effect"]


def test_dynamic_annealing_schedules_p():
    assert "progressively schedules p across the training lifecycle" in _c()["dynamic_annealing"]["algorithm"]


def test_benchmarks_math_and_alfworld():
    b = _c()["benchmarks"]
    assert "54.9%" in b["math"] and "7.2%" in b["math"]
    assert "93.8%" in b["alfworld"] and "ALFWorld" in b["alfworld"]


def test_integrations_lora_eval_learn():
    i = _c()["integrations"]
    assert i["lora_foundry"]["ref"] == "M046"
    assert i["eval_value"]["ref"] == "M048"
    assert "M057 step 11 Learn" in i["learn_step"]["ref"]


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M01292", "M01294", "M01295", "M01296", "M01298", "M01302", "M01303"):
        assert mod in body, f"{mod} not in the M078 milestone (must trace to spec)"
