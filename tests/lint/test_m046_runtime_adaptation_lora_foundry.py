"""M046 runtime-adaptation + LoRA-foundry contract lint.

Locks `config/agent/m046-runtime-adaptation-lora-foundry.yaml` to the M046 spec:
the local advantage (E0439), the 12-mechanism runtime adaptation (E0440), the 4
LoRA serving anchors (E0441), LoRA As Profiles (E0442), Do Not Merge Too Early
(E0443), Adapter Memory (E0444), the 6-stage adaptation progression (E0445),
LoRA hardware mapping (E0446), and Better Than Cloud + Peace Machine + Hyper
Loop (E0447). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m046-runtime-adaptation-lora-foundry.yaml"
MILESTONE = (REPO_ROOT / "backlog" / "milestones" /
             "M046-beat-the-cloud-runtime-adaptation-lora-foundry.md")


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M046"


def test_local_advantage_five_cloud_thirteen_station():
    la = _c()["local_advantage"]
    assert len(la["cloud_sees"]) == 5 and "a request" in la["cloud_sees"]
    assert len(la["station_sees"]) == 13 and "the cost ledger" in la["station_sees"]
    assert "situated intelligence" in la["doctrine"]


def test_runtime_adaptation_twelve_mechanisms():
    m = _c()["runtime_adaptation"]["mechanisms"]
    assert len(m) == 12 and "trace learning" in m and "routing" in m
    assert "Runtime adaptation comes first" in _c()["runtime_adaptation"]["doctrine"]


def test_four_lora_serving_anchors_verbatim():
    a = [x["source"] for x in _c()["lora_serving_anchors"]]
    assert a == ["vLLM", "SGLang", "S-LoRA", "Ray Serve"], f"anchor drift: {a}"


def test_eight_candidate_adapters_six_actions():
    lp = _c()["lora_as_profiles"]
    assert len(lp["candidate_adapters"]) == 8 and "selfdef/security LoRA" in lp["candidate_adapters"]
    assert len(lp["runtime_actions"]) == 6 and "ask oracle instead" in lp["runtime_actions"]
    assert lp["note"] == "This is adapter governance"


def test_merge_timing_three_modes_three_principles():
    mt = _c()["merge_timing"]
    modes = [x["mode"] for x in mt["adoption_modes"]]
    assert modes == ["development", "production stable", "model lab"]
    assert mt["adapter_principles"] == ["Adapters are behavioral overlays",
                                        "Profiles decide overlays", "Evals promote overlays"]


def test_adapter_memory_crystallization_and_pipeline():
    am = _c()["adapter_memory"]
    assert am["crystallization"] == ["Memory learns behavior", "Evals validate behavior",
                                     "LoRA crystallizes behavior into weights"]
    assert len(am["pipeline"]) == 7 and am["pipeline"][0] == "trace collection"
    assert am["pipeline"][-1] == "monitored deployment"


def test_adaptation_progression_six_stages():
    s = _c()["adaptation_progression"]["stages"]
    assert [x["stage"] for x in s] == [1, 2, 3, 4, 5, 6]
    assert s[3]["name"] == "LoRA/domain adaptation"
    assert _c()["adaptation_progression"]["note"] == "This is the correct order"


def test_lora_hardware_mapping_four_roles():
    r = [x["hardware"] for x in _c()["lora_hardware_mapping"]["roles"]]
    assert r == ["Blackwell", "4090", "CPU AVX-512", "ZFS"], f"role drift: {r}"
    assert _c()["lora_hardware_mapping"]["note"] == "The station becomes an adapter foundry"


def test_better_than_cloud_twelve_capabilities():
    c = _c()["better_than_cloud"]["capabilities"]
    assert len(c) == 12 and "operate offline" in c and "rollback side effects" in c


def test_peace_machine_eight_specializations():
    s = _c()["peace_machine_lora_specializations"]
    assert len(s) == 8 and "clearer communication" in s and "coherence" in s


def test_hyper_loop_six_steps():
    h = _c()["hyper_loop"]
    assert h["steps"] == ["Observe", "Adapt", "Evaluate", "Crystallize", "Govern", "Repeat"]
    assert "before a single full retrain" in h["closing"]


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00765", "M00768", "M00774", "M00778", "M00779", "M00780", "M00781"):
        assert mod in body, f"{mod} not in the M046 milestone (must trace to spec)"
