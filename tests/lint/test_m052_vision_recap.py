"""M052 vision-recap contract lint.

Locks `config/agent/m052-vision-recap.yaml` to the M052 spec: the highest-level
definition (E0499), the Hardware Vision (E0500), the OS Vision (E0501), the
Runtime Vision (E0502), the Intelligence Vision (E0503), the Continuity Vision
(E0504), the Fine-Tuning Vision (E0505), the Sovereign Vision (E0506), and the
core definition + implementation transition (E0507). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m052-vision-recap.yaml"
MILESTONE = (REPO_ROOT / "backlog" / "milestones" /
             "M052-vision-recap-ultimate-ai-workstation.md")


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M052"


def test_highest_level_definition_eight_components():
    comps = _c()["highest_level_definition"]["components"]
    assert comps == ["hardware-aware intelligence OS", "sovereign user control",
                     "local model ecology", "deterministic runtime", "memory/continuity",
                     "safe execution", "adaptive learning",
                     "later fine-tuning / LoRA / retraining"], f"definition drift: {comps}"


def test_hardware_vision_five_tiers():
    tiers = [x["tier"] for x in _c()["hardware_vision"]]
    assert tiers == ["Ryzen 9900X / Zen 5 AVX-512", "RTX PRO 6000 Blackwell 96GB",
                     "RTX 4090 24GB", "256GB RAM", "NVMe + ZFS"]
    ryzen = _c()["hardware_vision"][0]
    assert len(ryzen["roles"]) == 8 and "deterministic cortex" in ryzen["roles"]


def test_os_vision_ten_primitives():
    ov = _c()["os_vision"]
    assert ov["primitives"] == ["systemd", "cgroup v2", "AppArmor", "eBPF",
                                "LUKS+TPM+FIDO2", "Podman+Quadlet", "VFIO+IOMMU",
                                "ZFS", "OpenTelemetry", "DCGM"]
    assert ov["doctrine"] == "The OS is not just a platform. It governs intelligence"


def test_runtime_vision_design_law_loop_nine_bundles():
    rv = _c()["runtime_vision"]
    assert rv["design_law"] == ["Models propose", "Runtime routes", "AVX-512 enforces",
                                "Tools prove", "ZFS remembers", "User chooses"]
    assert rv["loop"] == ["MAP", "SPEC", "TEST", "ACT", "EVAL", "COMMIT", "LEARN"]
    assert len(rv["profile_bundles"]) == 9 and "communication-peace" in rv["profile_bundles"]


def test_intelligence_vision_six_model_types():
    iv = _c()["intelligence_vision"]
    t = [x["type"] for x in iv["model_types"]]
    assert t == ["LLM", "SLM", "RLM", "RM-PRM", "VLM", "LoRA-adapters"]
    assert iv["super_model"] == "The 'super-model' is the routed system, not a single checkpoint"


def test_continuity_vision_eleven_types():
    cv = _c()["continuity_vision"]
    assert len(cv["types"]) == 11 and "adapter lineage" in cv["types"]
    assert cv["closing"] == "Cloud has scale. This has situated intelligence"


def test_fine_tuning_seven_before_seven_then():
    ft = _c()["fine_tuning_vision"]
    assert len(ft["before_training"]) == 7 and "model selection" in ft["before_training"]
    assert len(ft["then"]) == 7 and "specialist SLMs" in ft["then"]
    assert "crystallizes proven behavior" in ft["doctrine"]


def test_sovereign_vision_nine_boundary_choices():
    sv = _c()["sovereign_vision"]
    assert len(sv["boundary_choices"]) == 9 and "scout or oracle" in sv["boundary_choices"]
    assert "peace machine" in sv["closing"]


def test_core_definition_and_transition():
    assert "continuous intelligence environment" in _c()["core_definition"]["statement"]
    assert "future implementation conversation" in _c()["implementation_transition"]["directive"]


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00868", "M00869", "M00874", "M00877", "M00878", "M00881", "M00882"):
        assert mod in body, f"{mod} not in the M052 milestone (must trace to spec)"
