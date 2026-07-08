"""M045 Linux-intelligence-governor contract lint.

Locks `config/server/m045-linux-intelligence-governor.yaml` to the M045 spec:
the 8 OS primitives (E0428), Linux Resource Intelligence (E0429), Pressure As
Sensation (E0430), adaptive reactions (E0431), eBPF As Truth Sensor (E0432),
Systemd As Agent Lifecycle Manager (E0433), Sovereign Profiles As OS Profiles
(E0434), Hardware Meets OS (E0435), and the anti-war 8-virtue-to-primitive
mapping (E0436). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "server" / "m045-linux-intelligence-governor.yaml"
MILESTONE = (REPO_ROOT / "backlog" / "milestones" /
             "M045-linux-as-intelligence-governor-cgroup-v2-systemd-psi-ebpf.md")


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M045"


def test_eight_os_primitives_verbatim():
    p = [x["primitive"] for x in _c()["os_primitives"]]
    assert p == ["cgroup v2", "systemd", "PSI", "eBPF / LSM", "AppArmor",
                 "namespaces", "ZFS", "LUKS/TPM/FIDO2"], f"primitive drift: {p}"
    assert _c()["substrate_note"] == "This is not incidental. This is the peace-machine substrate"


def test_resource_intelligence_knobs_and_boundaries():
    ri = _c()["resource_intelligence"]
    assert ri["systemd_knobs"] == ["CPUWeight", "MemoryMax", "IOWeight",
                                   "task limits", "slices", "scopes"]
    units = [x["unit"] for x in ri["workload_boundaries"]]
    assert units == ["oracle.service", "scout.slice", "sandbox.slice", "eval.slice",
                     "gateway.service"]
    assert ri["note"] == "This is how 'profiles' become real OS behavior"


def test_six_pressure_questions_three_sources():
    ps = _c()["pressure_sensing"]
    assert len(ps["pressure_questions"]) == 6 and "GPU pressure" in ps["pressure_questions"]
    src = [x["source"] for x in ps["pressure_sources"]]
    assert src == ["PSI", "DCGM", "runtime"]


def test_five_adaptive_reaction_rules():
    r = _c()["adaptive_reactions"]["rules"]
    triggers = [x["trigger"] for x in r]
    assert triggers == ["memory pressure high", "IO pressure high", "CPU pressure high",
                        "GPU oracle idle", "4090 idle"]
    mem = next(x for x in r if x["trigger"] == "memory pressure high")
    assert "hibernate branches" in mem["actions"]


def test_ebpf_truth_pattern():
    e = _c()["ebpf_truth_sensor"]
    tp = e["truth_pattern"]
    assert tp["model_claims"] == "I only read files"
    assert tp["ebpf_observes"] == "process opened network socket"
    assert tp["runtime"] == ["block", "log", "alert", "quarantine"]
    assert e["peace_feature"] == "This is a peace feature: reality over claims"


def test_agent_lifecycle_seven_units_eight_ops():
    al = _c()["agent_lifecycle"]
    assert len(al["unit_examples"]) == 7 and "gateway.service" in al["unit_examples"]
    assert al["os_operations"] == ["start", "stop", "restart", "limit", "observe",
                                   "journal", "kill zombies", "freeze/hibernate"]
    assert "AgentRM" in al["agentrm_mapping"]


def test_five_enforceable_profiles():
    p = [x["profile"] for x in _c()["enforceable_profiles"]["profiles"]]
    assert p == ["Offline Peace Mode", "Research Mode", "Autonomous Code Mode",
                 "High-Risk Mode", "Fast Local Mode"], f"profile drift: {p}"
    assert "OS policies + runtime policies" in _c()["enforceable_profiles"]["doctrine"]


def test_hardware_meets_os_seven_mappings():
    m = _c()["hardware_meets_os"]["mappings"]
    hw = [x["hardware"] for x in m]
    assert hw == ["AVX-512", "cgroup-systemd", "PSI-DCGM", "AppArmor-eBPF", "ZFS",
                  "VFIO", "Gateway"], f"mapping drift: {hw}"
    assert "social trust" in _c()["hardware_meets_os"]["bridge"]


def test_anti_war_eight_virtues():
    v = [x["virtue"] for x in _c()["anti_war_virtues"]["mappings"]]
    assert v == ["clarity", "consent", "reversibility", "proportionality",
                 "containment", "memory", "communication", "truth"], f"virtue drift: {v}"
    truth = next(x for x in _c()["anti_war_virtues"]["mappings"] if x["virtue"] == "truth")
    assert truth["primitive"] == "tests/eBPF/PSI/evals"
    assert "opaque power" in _c()["anti_war_virtues"]["key_line"]


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00748", "M00755", "M00757", "M00760", "M00761", "M00762", "M00764"):
        assert mod in body, f"{mod} not in the M045 milestone (must trace to spec)"
