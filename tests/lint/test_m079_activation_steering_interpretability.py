"""M079 activation-steering interpretability-surface contract lint.

Locks `config/observability/m079-activation-steering-interpretability.yaml` to
the M079 spec: the intervention-class taxonomy (E0758), the surjectivity
formalism (E0759), the formal proof (E0760), empirical validation (E0761),
eval-protocol separation (E0762), the use-case bounds (E0763/E0764), and the
integrations (E0765-E0767). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "observability" / "m079-activation-steering-interpretability.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M079-activation-steering-interpretability-surface.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M079"


def test_three_intervention_classes():
    c = _c()["intervention_classes"]["classes"]
    assert c == ["black-box prompt", "white-box activation-steer", "white-box weight-edit"]


def test_surjectivity_formalism_and_proof():
    s = _c()["surjectivity"]
    assert "off the manifold of states reachable from discrete prompts" in s["formalism"]
    assert "no prompt can reproduce" in s["proof"]


def test_empirical_three_llms():
    assert "three widely used LLMs" in _c()["empirical_validation"]


def test_eval_protocol_separation_non_negotiable():
    e = _c()["eval_protocol_separation"]
    assert "decouple white-box and black-box interventions" in e["rule"]
    assert "formal separation between white-box steerability and black-box prompting" in e["formal_separation"]


def test_use_case_bounds():
    ub = _c()["use_case_bounds"]
    assert "!= prompt-based interpretability" in ub["interpretability"]["bound"]
    assert "!= prompt-based vulnerability" in ub["safety"]["bound"]


def test_integrations_guardian_tool_authority():
    i = _c()["integrations"]
    assert i["guardian"]["ref"] == "selfdef MS044"
    assert "interpretability_intervention_class" in i["tool_authority"]["scope"]
    assert "L4-tier authority" in i["authority_levels"]["scope"]


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M01309", "M01310", "M01315", "M01316", "M01317", "M01323", "M01325"):
        assert mod in body, f"{mod} not in the M079 milestone (must trace to spec)"
