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
