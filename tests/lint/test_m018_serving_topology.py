"""M018 serving-topology contract lint.

Locks `config/inference/m018-serving-topology.yaml` to the M018 spec: the 6
serving roles (E0159), the 3 serving modes (E0161), the request envelope (E0162),
the 9 named queues + 6-axis weights (E0164), the backend abstraction surface
(E0165), and the Final Serving Fabric (E0166). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "inference" / "m018-serving-topology.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M018-serving-topology-local-inference-fabric.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M018"


def test_six_serving_roles():
    r = _c()["serving_roles"]
    assert [x["module"] for x in r] == [f"M00{n}" for n in range(285, 291)]
    names = [x["role"] for x in r]
    assert names == ["Oracle Server", "Scout Server", "Perception Server",
                     "Embedding/Rerank Server", "Control Runtime", "KV/Memory Service"], (
        f"serving-role drift: {names}")


def test_three_serving_modes_A_B_C():
    m = _c()["serving_modes"]
    assert [x["mode"] for x in m] == ["A", "B", "C"]
    assert [x["name"] for x in m] == ["Low-Latency Interactive", "Agentic Batch",
                                      "Long-Context Workbench"]


def test_nine_named_queues_verbatim():
    q = _c()["queues"]["names"]
    assert q == ["oracle_prefill", "oracle_decode", "oracle_verify", "scout_draft",
                 "scout_rerank", "perception", "embedding", "tool_intent",
                 "human_gate"], f"queue drift: {q}"
    assert len(q) == 9


def test_queue_weight_six_axes_verbatim():
    a = _c()["queue_weight_axes"]["axes"]
    assert a == ["priority", "deadline", "batchability", "risk", "cache_affinity",
                 "model_affinity"], f"queue-weight axis drift: {a}"


def test_backend_abstraction_five_ops():
    s = _c()["backend_abstraction"]["surface"]
    assert s == ["Generate", "Embed", "Rerank", "Perceive", "Verify"], (
        f"backend-abstraction surface drift: {s}")


def test_request_envelope_six_fields():
    f = _c()["request_envelope"]["fields"]
    assert f == ["model_id", "tokenizer_id", "prompt_hashes", "kv_ref_candidates",
                 "branch_parent", "cache_policy"], f"request-envelope drift: {f}"


def test_serving_fabric_six_components_and_rule():
    sf = _c()["serving_fabric"]
    assert len(sf["components"]) == 6 and "Model Gateway" in sf["components"]
    assert "dumb" in sf["rule"] and "runtime-smart" in sf["rule"]


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00285", "M00291", "M00294", "M00296", "M00297", "M00300", "M00301"):
        assert mod in body, f"{mod} not in the M018 milestone (must trace to spec)"
