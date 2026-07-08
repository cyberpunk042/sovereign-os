"""M032 cloud-expert-plane contract lint.

Locks `config/inference/m032-cloud-experts.yaml` to the M032 spec: the local-owns/
cloud-provides split + invariant (E0301), the OpenAI + Anthropic adapters
(E0299/E0300), the Model Router schema + selection axes (E0303), and the 6
provider adapters (E0305). No minimization of the spec.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "inference" / "m032-cloud-experts.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M032-cloud-expert-plane-openai-anthropic-remote-experts.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M032"


def test_boundary_invariant_remote_propose_local_commit():
    b = _c()["boundary"]
    assert b["invariant"]["rule"] == "Remote models propose. Local runtime commits."
    assert b["local_owns"]["owns"] == ["state", "policy", "memory", "replay",
                                       "tools", "commit"]


def test_openai_and_anthropic_four_adapters_each():
    assert len(_c()["openai_adapters"]) == 4
    assert len(_c()["anthropic_adapters"]) == 4


def test_anthropic_models_discovered_dynamically_not_hardcoded():
    """M00537 discipline: Claude models are discovered dynamically, never
    hardcoded — the same rule sovereign-os applies project-wide."""
    dyn = next(a for a in _c()["anthropic_adapters"] if a["module"] == "M00537")
    assert "DYNAMICALLY" in dyn["capability"] and "NOT hardcoded" in dyn["capability"]


def test_model_router_nine_field_schema_verbatim():
    f = _c()["model_router_schema"]["fields"]
    assert f == ["id", "provider", "role", "strengths", "locality", "privacy",
                 "cost", "latency", "supports"], f"router-schema drift: {f}"


def test_router_selection_eight_axes():
    a = _c()["router_selection_axes"]["axes"]
    assert a == ["privacy", "cost", "latency", "risk", "task_type",
                 "local_model_confidence", "cloud_availability", "user_profile"], (
        f"selection-axis drift: {a}")


def test_six_provider_adapters_verbatim():
    ad = _c()["provider_adapters"]["adapters"]
    assert ad == ["openai_adapter", "anthropic_adapter", "local_vllm_adapter",
                  "sglang_adapter", "trtllm_adapter", "llama_cpp_adapter"], (
        f"provider-adapter drift: {ad}")


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00527", "M00529", "M00530", "M00537", "M00538", "M00539", "M00540"):
        assert mod in body, f"{mod} not in the M032 milestone (must trace to spec)"
