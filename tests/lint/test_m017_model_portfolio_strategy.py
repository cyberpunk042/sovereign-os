"""M017 model-portfolio-strategy contract lint.

Locks `config/inference/m017-model-portfolio-strategy.yaml` to the M017 spec: the
3 hardware role bindings (E0150), the Blackwell precision ladder (E0151), the 4
serving backends (E0152), the Zen 5 AVX-512 group (E0153), and the 7-role
taxonomy + telemetry scheduler + model-registry contract (E0155). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "inference" / "m017-model-portfolio-strategy.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M017-model-portfolio-strategy.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M017"


def test_three_role_bindings():
    rb = _c()["role_bindings"]
    assert [r["tier"] for r in rb] == ["Blackwell", "4090", "Ryzen 9900X AVX-512"]
    assert [r["module"] for r in rb] == ["M00271", "M00272", "M00273"]


def test_precision_ladder_three_levels():
    lv = _c()["precision_ladder"]["levels"]
    assert [l["precision"] for l in lv] == ["BF16/FP16", "FP8", "NVFP4-MXFP4"]


def test_four_serving_backends_verbatim():
    b = [s["backend"] for s in _c()["serving_backends"]]
    assert b == ["vLLM", "SGLang", "TensorRT-LLM", "llama.cpp"], f"backend drift: {b}"


def test_seven_role_taxonomy_verbatim():
    roles = _c()["role_taxonomy"]["roles"]
    assert roles == ["Oracle", "Executor", "Perception", "Scout", "Verifier",
                     "Retriever", "Fallback"], f"role-taxonomy drift: {roles}"


def test_zen5_avx512_group_has_vnni_and_bf16():
    ext = _c()["zen5_avx512_group"]["extensions"]
    # spec-critical AVX-512 features for AI (VNNI int8, BF16, VP2INTERSECT)
    for e in ("AVX512VNNI", "AVX512BF16", "AVX512VP2INTERSECT"):
        assert e in ext, f"{e} missing from Zen 5 AVX-512 group"


def test_telemetry_scheduler_six_rules():
    rules = _c()["telemetry_scheduler_rules"]["rules"]
    assert len(rules) == 6
    whens = {r["when"] for r in rules}
    assert "risk.high-or-commit.final" in whens and "oracle_idle" in whens


def test_model_registry_five_fields_verbatim():
    f = _c()["model_registry_fields"]["per_model_fields"]
    assert f == ["role", "strengths", "gpu", "precision", "context_policy"], (
        f"model-registry field drift: {f}")


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00271", "M00274", "M00275", "M00279", "M00281", "M00282",
                "M00283", "M00284"):
        assert mod in body, f"{mod} not in the M017 milestone (must trace to spec)"
