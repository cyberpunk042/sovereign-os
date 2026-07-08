"""M080 HRM fourth-model-class contract lint.

Locks `config/inference/m080-hrm-model-class.yaml` to the M080 spec: HRM as a
novel recurrent architecture (E0768/E0769), the high/low modules (E0770/E0771),
single-forward-pass (E0772), training efficiency (E0773), the variants
(E0774/E0775), the benchmarks (E0776), and portfolio integration (E0777). No
minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "inference" / "m080-hrm-model-class.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M080-hrm-hierarchical-reasoning-model-architectural-class.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M080"


def test_architecture_fourth_class_brain_inspired():
    a = _c()["architecture"]
    assert "4th class beyond Transformer/Mamba/BitNet" in a["class"]
    assert "human brain" in a["inspiration"]


def test_two_recurrent_modules():
    m = _c()["modules"]
    assert [x["module"] for x in m] == ["high-level", "low-level"]
    assert m[0]["responsibility"] == "slow, abstract planning"
    assert m[1]["responsibility"] == "rapid, detailed computations"
    assert all(x["recurrent"] for x in m)


def test_single_forward_pass_no_cot():
    assert "single forward pass" in _c()["single_forward_pass"]
    assert "no CoT" in _c()["single_forward_pass"]


def test_training_efficiency_27m_1000_samples():
    te = _c()["training_efficiency"]
    assert "27 million parameters" in te["canonical_params"]
    assert "1000 training samples" in te["samples"]


def test_three_variants():
    names = [x["name"] for x in _c()["variants"]]
    assert names == ["HRM (canonical)", "HRM-Text-1B", "TRM"]
    hrm_text = next(x for x in _c()["variants"] if x["name"] == "HRM-Text-1B")
    assert hrm_text["params"] == "1182.8M" and hrm_text["arch_class"] == "hrm_text"
    trm = next(x for x in _c()["variants"] if x["name"] == "TRM")
    assert trm["params"] == "7M" and trm["layers"] == 2


def test_benchmarks_arc_agi():
    b = _c()["benchmarks"]
    assert "Sudoku" in b["hrm"] and "ARC" in b["hrm"]
    assert "45% test accuracy on ARC-AGI-1" in b["trm"]


def test_portfolio_fourth_class_does_not_replace():
    pi = _c()["portfolio_integration"]
    assert "fourth model class alongside Trinity" in pi["role"]
    assert "Oracle stays uncompromised FP16/NVFP4" in pi["does_not_replace"]


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M01326", "M01327"):
        assert mod in body, f"{mod} not in the M080 milestone (must trace to spec)"
