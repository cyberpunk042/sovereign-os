"""M050 heterogeneous-intelligence-system contract lint.

Locks `config/hardware/m050-heterogeneous-intelligence-system.yaml` to the M050
spec: the 7-component hardware mapping (E0479), the 5-layer core architecture
(E0480), the AVX-512 role (E0481), the columnar hot-data layout + bulk masks
(E0482), the GPU roles (E0483), the DevOps stack (E0484), the AI Runtime Loop
(E0485), the Fullstack Surface (E0486), and the 6-line Design Law + cloud-vs-
station advantage (E0487). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "hardware" / "m050-heterogeneous-intelligence-system.yaml"
MILESTONE = (REPO_ROOT / "backlog" / "milestones" /
             "M050-architect-engineer-seat-heterogeneous-intelligence-system.md")


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M050"


def test_hardware_mapping_seven_components():
    comps = [x["component"] for x in _c()["hardware_mapping"]]
    assert comps == ["Ryzen 9900X AVX-512", "RTX PRO 6000 96GB", "RTX 4090 24GB",
                     "256GB RAM", "NVMe + ZFS", "Debian/Ubuntu base",
                     "Anthropic gateway"], f"hardware drift: {comps}"


def test_core_architecture_five_layers():
    lay = [x["layer"] for x in _c()["core_architecture"]["layers"]]
    assert lay == ["Clients", "Gateway", "Cognitive Runtime", "Hardware Execution",
                   "Persistence"], f"layer drift: {lay}"


def test_avx512_role_nine_use_cases():
    ar = _c()["avx512_role"]
    assert "logic accelerator" in ar["doctrine"]
    assert len(ar["use_cases"]) == 9 and "reward-vector scoring" in ar["use_cases"]


def test_columnar_nine_soa_six_masks():
    assert len(_c()["columnar_hot_data"]["soa_arrays"]) == 9
    m = _c()["bulk_eval_masks"]["masks"]
    assert m == ["alive_mask", "tool_allowed_mask", "oracle_needed_mask",
                 "sandbox_required_mask", "memory_hit_mask", "commit_allowed_mask"]


def test_gpu_roles_blackwell_six_4090_seven():
    gr = _c()["gpu_roles"]
    assert gr["doctrine"] == "Do not fuse the GPUs mentally"
    assert len(gr["blackwell"]) == 6 and "FP8/FP4 model lab" in gr["blackwell"]
    assert len(gr["gpu_4090"]) == 7 and "SLM swarm" in gr["gpu_4090"]
    assert gr["avoid_move"] == ["KV tensors", "activations", "layer-split traffic",
                                "huge intermediate states"]


def test_devops_stack_seven_primitives_eight_bundles():
    ds = _c()["devops_stack"]
    p = [x["primitive"] for x in ds["primitives"]]
    assert p == ["systemd", "cgroup v2", "AppArmor+seccomp", "eBPF", "ZFS",
                 "Podman/Quadlet", "VFIO"], f"primitive drift: {p}"
    assert len(ds["profile_bundles"]) == 8 and "experimental" in ds["profile_bundles"]


def test_ai_runtime_loop_seven_steps():
    s = [x["step"] for x in _c()["ai_runtime_loop"]["steps"]]
    assert s == ["MAP", "SPEC", "TEST", "ACT", "EVAL", "COMMIT", "LEARN"]
    learn = next(x for x in _c()["ai_runtime_loop"]["steps"] if x["step"] == "LEARN")
    assert learn["definition"] == "update memory, routing, profiles, later LoRAs"


def test_fullstack_surface_five_entry_points():
    e = [x["surface"] for x in _c()["fullstack_surface"]["entry_points"]]
    assert e == ["local web dashboard", "CLI", "API", "MCP/tools", "Project integration"]


def test_design_law_six_lines_and_advantage():
    dl = _c()["design_law"]
    assert dl["lines"] == ["Models propose.", "Runtime routes.", "CPU enforces.",
                           "Tools prove.", "ZFS remembers.", "User chooses."]
    assert dl["station_advantage"] == ["locality", "continuity", "hardware control",
                                       "private context", "rollback", "user sovereignty"]


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00834", "M00841", "M00842", "M00844", "M00845", "M00847", "M00849"):
        assert mod in body, f"{mod} not in the M050 milestone (must trace to spec)"
