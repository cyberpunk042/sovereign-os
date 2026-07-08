"""M054 11-typed-interfaces contract lint.

Locks `config/agent/m054-typed-interfaces.yaml` to the M054 spec: the 11 typed
interface contracts (Gateway / Profile Resolver / Router / Model Adapter /
Policy / Tool / Memory / Workflow / Eval / Observability / AVX Cortex, E0519-
E0525) and the Architectural Replaceability Rule (E0526). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m054-typed-interfaces.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M054-11-typed-interfaces.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def _iface(iid: int) -> dict:
    return next(x for x in _c()["interfaces"] if x["id"] == iid)


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M054"


def test_eleven_interfaces_present_and_ordered():
    ids = [x["id"] for x in _c()["interfaces"]]
    assert ids == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11], f"interface id drift: {ids}"
    names = [x["name"] for x in _c()["interfaces"]]
    assert names == ["Gateway", "Profile Resolver", "Router", "Model Adapter", "Policy",
                     "Tool", "Memory", "Workflow", "Eval", "Observability", "AVX Cortex"]


def test_gateway_five_inputs_runtime_request_fields():
    # The E0519 header labels RuntimeRequest "9 fields" but its own enumeration
    # (features F04517-F04526) lists 10 distinct fields. Per operator §1g ("We do
    # not minimize anything") the contract keeps ALL 10 enumerated fields verbatim.
    g = _iface(1)
    assert len(g["inputs"]) == 5 and "MCP/tool" in g["inputs"]
    assert g["output"] == "RuntimeRequest"
    assert g["output_fields"] == ["request_id", "client_id", "profile_hint",
                                  "model_alias", "messages", "attachments", "tools",
                                  "privacy_context", "budget", "streaming"]


def test_profile_resolver_ten_fields():
    p = _iface(2)
    assert len(p["output_fields"]) == 10 and "autonomy_level" in p["output_fields"]
    assert "user sovereignty becomes executable" in p["note"]


def test_router_eleven_execution_route_fields():
    r = _iface(3)
    assert len(r["output_fields"]) == 11 and "verification_required" in r["output_fields"]
    assert "4090 scout" in r["route_reason_example"]


def test_model_adapter_five_verbs_seven_backends():
    ma = _iface(4)
    assert ma["verbs"] == ["generate", "embed", "rerank", "verify", "perceive"]
    assert len(ma["backends"]) == 7 and "TensorRT-LLM" in ma["backends"]
    assert ma["rule"] == "No workflow should depend directly on a vendor SDK"


def test_policy_eight_inputs_seven_decisions_seven_sites():
    p = _iface(5)
    assert len(p["inputs"]) == 8 and "side_effect_class" in p["inputs"]
    assert p["decision_values"] == ["allow", "deny", "ask_user", "sandbox",
                                    "escalate_to_oracle", "require_snapshot", "require_test"]
    assert len(p["call_sites"]) == 7


def test_tool_four_state_pipeline_nine_metadata_ten_substrates():
    t = _iface(6)
    assert t["pipeline"] == ["ToolIntent", "PolicyDecision", "ToolExecution", "ToolObservation"]
    assert len(t["metadata_fields"]) == 9 and "rollback_strategy" in t["metadata_fields"]
    assert len(t["substrates"]) == 10 and "WASM" in t["substrates"]


def test_memory_five_verbs_eight_fields():
    m = _iface(7)
    assert m["verbs"] == ["search", "read", "write", "promote", "forget"]
    assert len(m["item_fields"]) == 8 and "value_score" in m["item_fields"]


def test_workflow_eight_node_types_seven_operations():
    w = _iface(8)
    assert w["doctrine"] == "A workflow is a durable graph"
    assert w["node_types"] == ["model", "tool", "memory", "policy", "eval",
                               "human_gate", "checkpoint", "commit"]
    assert w["operations"] == ["pause", "resume", "cancel", "fork", "merge",
                               "rollback", "recompile"]


def test_eval_ten_scores():
    e = _iface(9)
    assert len(e["scores"]) == 10 and "learning_value" in e["scores"]
    assert e["note"] == "Evals feed the router and model registry"


def test_observability_ten_required_fields_six_enablement():
    o = _iface(10)
    assert len(o["required_fields"]) == 10 and "parent_span_id" in o["required_fields"]
    assert len(o["enablement"]) == 6 and "user trust" in o["enablement"]


def test_avx_cortex_five_inputs_six_operations_portability():
    a = _iface(11)
    assert len(a["inputs"]) == 5 and "PolicyMaskTable" in a["inputs"]
    assert a["operations"] == ["filter_alive", "score_candidates", "intersect_memory",
                               "merge_policy_masks", "compress_ready", "route_batches"]
    assert "without AVX, just slower" in a["portability"]


def test_replaceability_rule_six_examples_contracts_remain():
    rr = _c()["replaceability_rule"]
    assert len(rr["examples"]) == 6 and "Replace vLLM with SGLang" in rr["examples"]
    assert rr["invariant"] == "The contracts remain"


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00904", "M00905", "M00908", "M00910", "M00911", "M00914", "M00915"):
        assert mod in body, f"{mod} not in the M054 milestone (must trace to spec)"
