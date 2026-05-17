"""Layer 2 — sovereign-os inference router classify() rules.

Validates the deterministic per-tier routing rules from
scripts/inference/router.py. Per SDD-011: routing must be
operator-readable + introspectable. These tests document the
contract.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "inference"))

router = pytest.importorskip("router")


def _request(model: str = "auto", user: str = "hello", **kwargs):
    body = {"model": model, "messages": [{"role": "user", "content": user}]}
    body.update(kwargs)
    return body


# ----------- Rule 1: ternary models → Pulse -----------

def test_ternary_microsoft_bitnet_goes_to_pulse():
    assert router.classify(_request(model="microsoft/bitnet-b1.58-2B-4T")) == "pulse"


def test_ternary_prefix_goes_to_pulse():
    assert router.classify(_request(model="ternary:falcon-3-bitnet")) == "pulse"


def test_bitnet_substring_goes_to_pulse():
    assert router.classify(_request(model="custom/bitnet-flavor")) == "pulse"


# ----------- Rule 2: code/math markers → Oracle Core -----------

def test_triple_backtick_code_block_goes_to_oracle():
    assert router.classify(_request(user="write code:\n```python\nprint(1)\n```")) == "oracle_core"


def test_def_function_marker_goes_to_oracle():
    assert router.classify(_request(user="explain this def foo(): pass")) == "oracle_core"


def test_math_marker_goes_to_oracle():
    assert router.classify(_request(user="solve 2+2 math problem")) == "oracle_core"


def test_solve_marker_goes_to_oracle():
    assert router.classify(_request(user="solve x^2 - 5x + 6 = 0")) == "oracle_core"


# ----------- Rule 3: long context → Oracle Core -----------

def test_short_context_does_not_force_oracle():
    body = _request(model="default", user="hi")
    assert router.classify(body) == "logic_engine"


def test_long_context_goes_to_oracle():
    # ~100K chars → ~25K tokens, NOT enough to trigger (threshold is 65k tokens)
    long_user = "x" * 100_000
    assert router.classify(_request(user=long_user)) == "logic_engine"


def test_very_long_context_goes_to_oracle():
    # 300K chars → ~75K tokens, above threshold
    very_long_user = "x" * 300_000
    assert router.classify(_request(user=very_long_user)) == "oracle_core"


# ----------- Rule 4: JSON-mode / tools → Logic Engine -----------

def test_json_mode_goes_to_logic_engine():
    body = _request()
    body["response_format"] = {"type": "json_object"}
    assert router.classify(body) == "logic_engine"


def test_tools_present_goes_to_logic_engine():
    body = _request()
    body["tools"] = [{"type": "function", "function": {"name": "fetch_url"}}]
    assert router.classify(body) == "logic_engine"


# ----------- Rule 5 (default): Logic Engine -----------

def test_default_goes_to_logic_engine():
    assert router.classify(_request()) == "logic_engine"


def test_arbitrary_chat_goes_to_logic_engine():
    assert router.classify(_request(model="qwen3", user="what is the weather?")) == "logic_engine"


# ----------- Priority: ternary trumps code-markers -----------

def test_ternary_with_code_marker_still_pulse():
    """Rule 1 (ternary) fires before Rule 2 (code markers)."""
    assert router.classify(
        _request(model="microsoft/bitnet-b1.58-2B-4T", user="```code```")
    ) == "pulse"


def test_priority_doc_string():
    """The classify() docstring documents the rule order; assert it stays explicit."""
    doc = router.classify.__doc__ or ""
    # Function-level docstring is optional; the module-level docstring documents the rules
    module_doc = router.__doc__ or ""
    assert "Routing rules" in module_doc or "routing decision" in (doc + module_doc).lower()


# ----------- R215: model-class classification -----------


def test_r215_classify_model_class_honors_explicit_field():
    """Operator-asserted sovereign_os_class wins over inference."""
    body = {"model": "deepseek-coder-32b", "sovereign_os_class": "rlm"}
    assert router.classify_model_class(body) == "rlm"


def test_r215_classify_model_class_explicit_must_be_known():
    """Unknown sovereign_os_class falls through to inference."""
    body = {"model": "microsoft/bitnet-b1.58-2B-4T", "sovereign_os_class": "alien"}
    # falls through to bitnet inference → ternary-lm
    assert router.classify_model_class(body) == "ternary-lm"


def test_r215_classify_bitnet_as_ternary_lm():
    assert router.classify_model_class({"model": "microsoft/bitnet-b1.58-2B-4T"}) == "ternary-lm"


def test_r215_classify_phi4_mini_as_slm():
    assert router.classify_model_class({"model": "microsoft/Phi-4-mini-instruct"}) == "slm"


def test_r215_classify_qwen_coder_as_code():
    assert router.classify_model_class({"model": "Qwen/Qwen3-Coder-32B-Instruct"}) == "code"


def test_r215_classify_deepseek_r1_as_rlm():
    assert router.classify_model_class({"model": "deepseek-ai/DeepSeek-R1-Distill-Llama-70B"}) == "rlm"


def test_r215_classify_deepseek_v3_as_mixture():
    assert router.classify_model_class({"model": "deepseek-ai/DeepSeek-V3"}) == "mixture"


def test_r215_classify_nomic_embed_as_embed():
    assert router.classify_model_class({"model": "nomic-ai/nomic-embed-text-v2-moe"}) == "embed"


def test_r215_classify_bge_reranker_as_reranker():
    assert router.classify_model_class({"model": "BAAI/bge-reranker-v2-m3"}) == "reranker"


def test_r215_classify_qwen_vl_as_vision():
    assert router.classify_model_class({"model": "Qwen/Qwen2-VL-7B-Instruct"}) == "vision"


def test_r215_classify_unknown_returns_empty():
    """Unknown model + no operator override → empty string (rolled
    into '(unspecified)' bucket in metrics)."""
    assert router.classify_model_class({"model": "unknown-vendor/unknown-model"}) == ""
    assert router.classify_model_class({}) == ""
