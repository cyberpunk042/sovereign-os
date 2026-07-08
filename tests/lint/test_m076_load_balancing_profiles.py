"""M076 three-load-balancing-profiles contract lint.

Locks `config/inference/m076-load-balancing-profiles.yaml` to the M076 spec: the
3 workload-aware runtime profiles (E0728-E0737) — Ultra-Sovereign Efficiency /
High-Concurrency Burst / Deep Context Synthesis — each with purpose + hardware
allocation + orchestration vector. Exactly 3 (verbatim-locked; no 4th). No
minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "inference" / "m076-load-balancing-profiles.yaml"
MILESTONE = (REPO_ROOT / "backlog" / "milestones" /
             "M076-three-load-balancing-profiles-ultra-sovereign-burst-deep-context.md")


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def _p(pid: int) -> dict:
    return next(x for x in _c()["profiles"] if x["id"] == pid)


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M076"


def test_exactly_three_profiles_verbatim():
    p = _c()["profiles"]
    assert [x["id"] for x in p] == [1, 2, 3], "must be EXACTLY 3 profiles (verbatim-locked)"
    names = [x["name"] for x in p]
    assert names == ["Ultra-Sovereign Efficiency Mode", "High-Concurrency Agent Burst Mode",
                     "Deep Context Synthesis Mode"], f"profile-name drift: {names}"


def test_profile1_cpu_focused_bitnet():
    p1 = _p(1)
    assert p1["focus"] == "CPU Focused"
    assert "CPU cores 0-7" in p1["allocation"] and "BitNet-b1.58-3B" in p1["allocation"]
    assert "taskset -c 0-7 bitnet-cli" in p1["orchestration"]
    assert "ggml-model-i2.gguf" in p1["orchestration"]


def test_profile2_asymmetric_three_agents():
    p2 = _p(2)
    assert p2["focus"] == "Asymmetric Load Balancing"
    assert "conductor_01" in p2["allocation"]
    assert "translator_01" in p2["allocation"] and "Qwen-32B-Ternary-Quant" in p2["allocation"]
    assert "deep_reasoner_01" in p2["allocation"] and "DeepSeek-R1-Distill-Llama-70B-FP16" in p2["allocation"]


def test_profile3_deep_context_layer_split():
    p3 = _p(3)
    assert p3["focus"] == "Unified Memory Span"
    assert "layers 0-30 pinned to GPU 0" in p3["allocation"]
    assert "layers 31-80 pinned to GPU 1" in p3["allocation"]
    assert "--tensor-parallel-size 2" in p3["orchestration"]
    assert "--kv-cache-dtype fp8" in p3["orchestration"]


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M01258", "M01259", "M01260", "M01261", "M01267", "M01268", "M01269"):
        assert mod in body, f"{mod} not in the M076 milestone (must trace to spec)"
