"""M041 harness + canonical-contracts contract lint.

Locks `config/agent/m041-harness-and-canonical-contracts.yaml` to the M041 spec:
the 7-layer agent harness + station mapping (E0389/E0390), the MAP methodology
(E0391), the 7 canonical contracts + 10-step runtime compile pipeline + 6-tier
hardware overlay + 9-property North Star (E0397), and the adaptive Goldilocks
router (E0395). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m041-harness-and-canonical-contracts.yaml"
MILESTONE = (REPO_ROOT / "backlog" / "milestones" /
             "M041-spec-workflow-profiles-evals-policy-model-registry-hardware-profiles-contracts.md")


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M041"


def test_seven_harness_layers_verbatim():
    layers = _c()["harness_layers"]
    names = [x["name"] for x in layers]
    assert names == ["Execution environment", "Tool interface", "Context management",
                     "Lifecycle / orchestration", "Observability", "Verification",
                     "Governance"], f"harness-layer drift: {names}"
    assert [x["layer"] for x in layers] == [1, 2, 3, 4, 5, 6, 7]


def test_tool_interface_station_lists_claude_code():
    tool = next(x for x in _c()["harness_layers"] if x["name"] == "Tool interface")
    assert "Claude Code" in tool["station"] and "MCP" in tool["station"]


def test_map_methodology_seven_steps_verbatim():
    m = _c()["map_methodology"]
    assert m["rule"] == "MAP phase before ACT phase"
    assert m["steps"] == ["MAP", "SPEC", "TEST", "ACT", "EVAL", "COMMIT", "LEARN"]


def test_seven_canonical_contracts_verbatim():
    cc = _c()["canonical_contracts"]
    names = [x["contract"] for x in cc]
    assert names == ["SPEC.md", "WORKFLOW.md", "PROFILES.yaml", "EVALS.yaml",
                     "MAP.json", "MODEL_REGISTRY.yaml", "POLICY.yaml"], (
        f"canonical-contract drift: {names}")
    spec = next(x for x in cc if x["contract"] == "SPEC.md")
    assert spec["purpose"] == "What should be true"


def test_runtime_pipeline_ten_steps():
    p = _c()["runtime_compile_pipeline"]["steps"]
    assert p == ["Task", "MAP", "SPEC/TDD plan", "workflow DAG", "model/tool routing",
                 "sandbox execution", "tests/evals", "oracle/human review", "commit",
                 "memory update"], f"pipeline drift: {p}"
    assert len(p) == 10


def test_hardware_overlay_six_tiers():
    t = [x["tier"] for x in _c()["hardware_overlay"]["tiers"]]
    assert t == ["Ryzen 9900X AVX-512", "RTX PRO 6000 Blackwell", "RTX 4090",
                 "256GB RAM", "NVMe/ZFS", "10GbE / 2.5GbE"], f"overlay drift: {t}"


def test_north_star_nine_properties():
    ns = _c()["north_star"]
    assert ns["is"] == "a programmable intelligence harness"
    assert len(ns["properties"]) == 9 and "SMART routing" in ns["properties"]
    assert "hardware-aware scheduling" in ns["properties"]
    assert ns["next_artifact"] == "Jean Station Architecture Spec v0.1"


def test_router_six_classifiers():
    r = _c()["adaptive_goldilocks_router"]["classifiers"]
    assert len(r) == 6 and "profile selector" in r and "privacy classifier" in r


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00680", "M00686", "M00687", "M00693", "M00694", "M00695", "M00696"):
        assert mod in body, f"{mod} not in the M041 milestone (must trace to spec)"
