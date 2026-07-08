"""M077 NVFP4-pipeline contract lint.

Locks `config/inference/m077-nvfp4-pipeline.yaml` to the M077 spec: the NVFP4
format (E0738), the 4 method components (E0739-E0742), the hardware target
(E0743), the training + inference pipelines (E0744/E0745), the LoRA path (E0746),
and ecosystem awareness (E0747), plus the validation run. No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "inference" / "m077-nvfp4-pipeline.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M077-nvfp4-pretraining-and-inference-pipeline.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M077"


def test_nvfp4_format_e2m1_block16_e4m3():
    f = _c()["nvfp4_format"]
    assert "E2M1" in f["element_format"]
    assert f["block_size"] == 16
    assert "E4M3" in f["block_scale_format"]
    assert "16 FP4 values (E2M1) shares a scale represented in E4M3" in f["spec_quote"]


def test_four_method_components_verbatim():
    comps = [x["component"] for x in _c()["method_components"]]
    assert comps == ["Random Hadamard transforms (RHT)", "two-dimensional quantization scheme",
                     "stochastic rounding", "selective high-precision layers"]
    rht = next(x for x in _c()["method_components"] if "RHT" in x["component"])
    assert rht["purpose"] == "bound block-level outliers"
    sr = next(x for x in _c()["method_components"] if x["component"] == "stochastic rounding")
    assert sr["purpose"] == "unbiased gradient estimation"


def test_hardware_target_blackwell_sm120():
    ht = _c()["hardware_target"]
    assert "Blackwell" in ht["gpu"] and "96GB" in ht["gpu"]
    assert ht["cuda_arch"] == "sm_120"


def test_training_and_inference_pipelines():
    assert "fully NVFP4 forward + backward pass" in _c()["training_pipeline"]["scope"]
    assert "weight + activation quantization" in _c()["inference_pipeline"]["scope"]


def test_lora_path_4bit_quartet():
    assert "adapter training in 4-bit" in _c()["lora_path"]["scope"]
    assert "Quartet II" in _c()["lora_path"]["scope"]


def test_ecosystem_recipes_and_speedup():
    e = _c()["ecosystem"]
    assert "Quartet II" in e["alternative_recipes"] and "nGPT-NVFP4" in e["alternative_recipes"]
    assert "4.2x speedup over BF16" in e["blackwell_speedup"]


def test_validation_12b_10t_tokens():
    v = _c()["validation"]
    assert "12-billion-parameter" in v["run"] and "10 trillion tokens" in v["run"]
    assert "comparable to an FP8 baseline" in v["result"]


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M01275", "M01277", "M01279", "M01280", "M01283", "M01285", "M01287"):
        assert mod in body, f"{mod} not in the M077 milestone (must trace to spec)"
