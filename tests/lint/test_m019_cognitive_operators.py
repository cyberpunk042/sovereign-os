"""M019 cognitive-operators contract lint.

Locks `config/agent/m019-cognitive-operators.yaml` to the M019 spec: the 12
cognitive operators (E0169), the composable recipes (E0172), the router
inputs/outputs (E0171), the anti-delusion law's 8 requirements (E0173), the
candidate/branch fields (E0174), and the Final Shape Cortex Runtime (E0177).
No minimization of the spec.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m019-cognitive-operators.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M019-intelligence-creation-composable-cognitive-operators.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M019"


def test_twelve_cognitive_operators_verbatim():
    ops = _c()["cognitive_operators"]["operators"]
    assert ops == ["route", "draft", "debate", "verify", "decompose", "retrieve",
                   "simulate", "reflect", "vote", "merge", "compress", "commit"], (
        f"cognitive-operator drift: {ops}")
    assert len(ops) == 12


def test_recipes_named_and_traced():
    r = _c()["recipes"]
    names = [x["name"] for x in r]
    assert "Fast Executor" in names and "Debate" in names and "Cascade" in names
    assert all(x.get("graph") for x in r), "every recipe must carry its graph"


def test_router_eleven_inputs_eight_outputs():
    assert len(_c()["router_inputs"]["inputs"]) == 11
    outs = _c()["router_outputs"]["outputs"]
    assert outs == ["model_choice", "precision", "backend", "speculation_depth",
                    "debate_width", "oracle_threshold", "human_gate_threshold",
                    "cache_policy"], f"router-output drift: {outs}"


def test_anti_delusion_law_eight_requirements_verbatim():
    req = _c()["anti_delusion_law"]["requirements"]
    assert req == ["diversity", "evidence", "independent-model", "external-tool",
                   "source-citation", "test-execution", "schema", "oracle-final"], (
        f"anti-delusion law drift: {req}")


def test_candidate_fields_ten_verbatim():
    f = _c()["candidate_fields"]["fields"]
    assert f == ["source_model", "recipe_id", "evidence_mask", "agreement_mask",
                 "disagreement_mask", "verification_state", "risk", "cost",
                 "latency", "score"], f"candidate-field drift: {f}"


def test_final_cortex_eleven_components():
    c = _c()["final_cortex_shape"]["components"]
    assert len(c) == 11 and "Human Gate" in c and "Replay Ledger" in c


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00302", "M00308", "M00309", "M00310", "M00317", "M00318", "M00319"):
        assert mod in body, f"{mod} not in the M019 milestone (must trace to spec)"
