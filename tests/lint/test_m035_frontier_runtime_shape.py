"""M035 frontier runtime-shape capstone contract lint.

Locks `config/agent/m035-frontier-runtime-shape.yaml` to the M035 spec: the 5
budget tiers (E0331), the 9-layer runtime shape (E0335) that unifies the M010-M034
stack, the 9-axis cost ledger + stopping rule (E0334), and the Profile System
aliases (R05900). No minimization of the spec.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m035-frontier-runtime-shape.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M035-frontier-inference-time-intelligence.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M035"


def test_five_budget_tiers_verbatim():
    t = [x["tier"] for x in _c()["budget_tiers"]]
    assert t == ["reflex", "deliberate", "deep", "autonomous", "high-assurance"], (
        f"budget-tier drift: {t}")


def test_nine_runtime_layers_in_order():
    layers = _c()["runtime_layers"]
    assert [x["layer"] for x in layers] == list(range(1, 10))
    names = [x["name"] for x in layers]
    assert names == ["Anthropic-first Gateway", "Cognitive Compiler",
                     "AVX-512 Cortex", "Model Fabric", "World Model",
                     "Execution Plane", "Memory OS", "Observability",
                     "Profile System"], f"runtime-layer drift: {names}"


def test_layers_map_to_materialized_milestones():
    """The capstone's 9 layers each cite a materialized milestone."""
    maps = {x["layer"]: x["maps_to"] for x in _c()["runtime_layers"]}
    assert maps[1] == "M034" and maps[3] == "M010" and maps[7] == "M028"
    assert maps[8] == "M013"


def test_cost_ledger_nine_axes():
    a = _c()["cost_ledger"]["axes"]
    assert a == ["tokens", "gpu_seconds", "cloud_dollars", "energy_estimate",
                 "latency", "cache_hits", "branch_acceptance", "tool_retries",
                 "oracle_calls"], f"cost-ledger drift: {a}"


def test_stopping_rule_five_conditions():
    c = _c()["stopping_rule"]["conditions"]
    assert c == ["confidence-high-enough", "verification-passed",
                 "marginal-gain-low", "budget-exhausted", "risk-requires-human"], (
        f"stopping-rule drift: {c}")


def test_profile_system_five_claude_jean_aliases():
    a = _c()["profile_system_aliases"]["aliases"]
    assert a == ["claude-jean-reflex", "claude-jean-deliberate", "claude-jean-deep",
                 "claude-jean-autonomous", "claude-jean-high-assurance"], (
        f"profile-alias drift: {a}")


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00578", "M00584", "M00585", "M00586", "M00591", "M00594"):
        assert mod in body, f"{mod} not in the M035 milestone (must trace to spec)"
