"""M034 Anthropic-first-gateway contract lint.

Locks `config/inference/m034-anthropic-first-gateway.yaml` to the M034 spec: the
Anthropic primary surface + OpenAI secondary surface (E0319) and the Claude Code
extension points (E0320). No minimization of the spec.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "inference" / "m034-anthropic-first-gateway.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M034-anthropic-first-gateway-mcp-claude-code-integration.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M034"


def test_anthropic_primary_six_surfaces():
    s = _c()["anthropic_primary_surface"]["surfaces"]
    assert len(s) == 6
    assert [x["module"] for x in s] == [f"M005{n}" for n in range(61, 67)]
    # /v1/messages is the primary
    assert "/v1/messages" in s[0]["surface"]


def test_openai_secondary_four_endpoints():
    e = _c()["openai_secondary_surface"]["endpoints"]
    assert e == ["/v1/chat/completions", "/v1/responses", "/v1/embeddings",
                 "/v1/models"], f"OpenAI secondary drift: {e}"


def test_claude_code_four_extension_points():
    ep = _c()["claude_code_extension_points"]
    points = [x["point"] for x in ep]
    assert points == ["Hooks", "MCP", "Subagents", "Agent SDK"], f"extension-point drift: {points}"


def test_hooks_intercept_tool_calls_and_completion():
    hooks = next(x for x in _c()["claude_code_extension_points"] if x["point"] == "Hooks")
    assert "tool calls" in hooks["intercepts"] and "completion" in hooks["intercepts"]


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00561", "M00566", "M00567", "M00570", "M00571", "M00574"):
        assert mod in body, f"{mod} not in the M034 milestone (must trace to spec)"
