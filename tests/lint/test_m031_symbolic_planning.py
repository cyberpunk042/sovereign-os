"""M031 symbolic-planning-plane contract lint.

Locks `config/agent/m031-symbolic-planning.yaml` to the M031 spec: the 7 symbolic
sub-parts (E0290), the PDDL Objects/Predicates/Actions (E0292), the predicate
bitset + action masks + applicability formula (E0294), and the LTL catalog
(E0293). No minimization of the spec.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m031-symbolic-planning.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M031-symbolic-planning-plane-pddl-sat-smt-ltl.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M031"


def test_seven_symbolic_subparts_verbatim():
    s = _c()["symbolic_plane_subparts"]["subparts"]
    assert s == ["PDDL-planners", "SAT-SMT-solvers", "Prolog/Datalog-rules",
                 "temporal-logic-monitors", "finite-state-machines",
                 "type-schema-checkers", "policy-engines"], f"subpart drift: {s}"
    assert len(s) == 7


def test_pddl_compilation_verbatim():
    pc = _c()["planning_compilation"]
    assert pc["objects"]["items"] == ["repo", "files", "test_cmd", "patch",
                                      "network_permission"]
    assert pc["actions"]["items"] == ["inspect_repo", "infer_test_command",
                                      "run_tests", "analyze_failure", "draft_patch",
                                      "apply_patch", "rerun_tests", "request_network"]


def test_predicate_bitset_eight_verbatim():
    p = _c()["predicate_bitset"]["predicates"]
    assert p == ["inspected_repo", "tests_known", "failure_known", "patch_exists",
                 "patch_valid", "rollback_exists", "network_allowed",
                 "human_approved"], f"predicate-bitset drift: {p}"
    assert len(p) == 8


def test_action_mask_catalog_four():
    m = _c()["action_mask_catalog"]["masks"]
    assert m == ["precondition_mask", "add_effect_mask", "delete_effect_mask",
                 "forbidden_mask"], f"action-mask drift: {m}"


def test_applicability_formula_verbatim():
    f = _c()["applicability_formula"]["formula"]
    assert f == ("(state & precondition_mask) == precondition_mask & "
                 "(state & forbidden_mask) == 0")


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00510", "M00516", "M00517", "M00519", "M00521", "M00522", "M00523"):
        assert mod in body, f"{mod} not in the M031 milestone (must trace to spec)"
