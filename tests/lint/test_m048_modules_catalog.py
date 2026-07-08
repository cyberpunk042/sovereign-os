"""M048 module-organ catalog contract lint.

Locks `config/agent/m048-modules-catalog.yaml` to the M048 spec: the continuity
7-question standard (E0458), the 10 module organs (E0459-E0465), the 3-level
configuration surfaces (E0466), and the 6-layer Continuity Stack (E0467). No
minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m048-modules-catalog.yaml"
MILESTONE = (REPO_ROOT / "backlog" / "milestones" /
             "M048-modules-base-os-compute-fabric-sandbox-gateway-memory-workflow-eval-continuity-observability-policy-config-resolver-lora-foundry-hardware-profiler.md")


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def _organ(oid: int) -> dict:
    return next(x for x in _c()["module_organs"] if x["id"] == oid)


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M048"


def test_continuity_standard_seven_questions():
    cs = _c()["continuity_standard"]
    assert len(cs["questions"]) == 7 and cs["questions"][0] == "How does it start?"
    assert cs["questions"][-1] == "How does it prove what happened?"
    assert cs["closing"] == "That is the continuity standard"


def test_ten_module_organs_present():
    ids = [x["id"] for x in _c()["module_organs"]]
    assert ids == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], f"organ id drift: {ids}"
    names = [x["name"] for x in _c()["module_organs"]]
    assert names == ["Base OS", "Compute Fabric", "Container/Sandbox Fabric", "Gateway",
                     "Memory OS", "Workflow Compiler", "Eval/Value Plane",
                     "Continuity Manager", "Observability", "LoRA Foundry"]


def test_base_os_ten_responsibilities_five_modes():
    b = _organ(1)
    assert len(b["responsibilities"]) == 10 and "VFIO/IOMMU" in b["responsibilities"]
    assert b["config_modes"] == ["stable", "ai-driver-latest", "secure", "developer", "offline"]


def test_compute_fabric_four_workers_seven_caps_six_dests():
    cf = _organ(2)
    assert cf["workers"] == ["blackwell-oracle", "4090-scout", "cpu-avx-cortex", "cloud-optional"]
    assert len(cf["worker_capability_schema"]) == 7
    assert len(cf["dynamic_placement"]) == 6 and "human gate" in cf["dynamic_placement"]


def test_sandbox_fabric_eight_profiles_five_rules():
    sf = _organ(3)
    assert len(sf["sandbox_profiles"]) == 8 and "vfio-4090" in sf["sandbox_profiles"]
    assert len(sf["clean_pattern"]) == 5


def test_gateway_six_surfaces_seven_responsibilities():
    g = _organ(4)
    assert len(g["surfaces"]) == 6 and "MCP bridge" in g["surfaces"]
    assert g["responsibilities"] == ["cost", "privacy", "redaction", "routing",
                                     "profiles", "approval", "tracing"]
    assert "Sovereign Gateway" in g["provider_inversion"]


def test_memory_os_eight_types_four_rules_six_tools():
    m = _organ(5)
    assert len(m["memory_types"]) == 8 and "KV-prefix cache" in m["memory_types"]
    assert len(m["continuity_rules"]) == 4
    assert m["memory_as_tools"] == ["search", "write", "link", "verify", "forget", "promote"]


def test_workflow_compiler_seven_in_seven_out():
    w = _organ(6)
    assert len(w["inputs"]) == 7 and "hardware pressure" in w["inputs"]
    assert len(w["outputs"]) == 7 and "workflow DAG" in w["outputs"]
    assert "re-map / re-plan / re-route" in w["adaptive_recompile"]


def test_eval_plane_ten_dimensions_eight_profiles():
    e = _organ(7)
    assert len(e["dimensions"]) == 10 and "learning value" in e["dimensions"]
    assert len(e["profile_weights"]) == 8 and "communication-peace" in e["profile_weights"]


def test_continuity_manager_six_primitives_eight_states():
    cm = _organ(8)
    assert cm["note"] == "sleeper module"
    assert len(cm["primitives"]) == 6
    assert len(cm["states"]) == 8 and "rolled back" in cm["states"]


def test_observability_nine_sources_six_questions():
    o = _organ(9)
    assert len(o["sources"]) == 9 and "eBPF" in o["sources"]
    assert len(o["questions"]) == 6 and "which model decided?" in o["questions"]


def test_lora_foundry_six_before_six_deploy():
    lf = _organ(10)
    assert len(lf["before_training"]) == 6 and "router tuning" in lf["before_training"]
    assert len(lf["training_to_deployment"]) == 6


def test_configuration_surfaces_three_levels():
    cs = _c()["configuration_surfaces"]
    levels = [x["level"] for x in cs["levels"]]
    assert levels == ["User", "Power user", "System"], f"level drift: {levels}"


def test_continuity_stack_six_layers_and_key_line():
    cst = _c()["continuity_stack"]
    layers = [x["layer"] for x in cst["layers"]]
    assert layers == ["Hardware continuity", "OS continuity", "Agent continuity",
                      "Memory continuity", "Model continuity", "Human continuity"]
    assert "life/work continuity" in cst["difference"]
    assert "controlled continuation of user intent" in _c()["key_line"]


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00799", "M00800", "M00806", "M00807", "M00810", "M00814", "M00815"):
        assert mod in body, f"{mod} not in the M048 milestone (must trace to spec)"
