"""M044 Sovereign-OS-substrate contract lint.

Locks `config/server/m044-sovereign-os-substrate.yaml` to the M044 spec: the
sovereign substrate definition (E0418), Debian 13 + Ubuntu 24.04 reality
(E0419/E0420), the two-personalities profile choice (E0421), the peace machine
frame (E0422), the security substrate (E0423), secrets + identity (E0424),
NVIDIA reality (E0425), kernel/compiler + AVX build matrix (E0426), the 8
Sovereign-OS Planes + 8 accountability questions + peace-machine composition
(E0427). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "server" / "m044-sovereign-os-substrate.yaml"
MILESTONE = (REPO_ROOT / "backlog" / "milestones" /
             "M044-sovereign-os-substrate-debian-13-ubuntu-24.md")


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M044"


def test_sovereign_substrate_six_properties():
    s = _c()["sovereign_substrate"]
    assert s["properties"] == ["package policy", "kernel behavior", "GPU driver reality",
                               "sandbox security", "filesystem truth",
                               "user-controlled communication"]


def test_base_os_debian_and_ubuntu_reality():
    b = _c()["base_os"]
    assert b["debian_13"]["kernel"] == "Linux 6.12 LTS" and b["debian_13"]["python"] == "3.13"
    assert b["ubuntu_2404"]["glibc"] == "2.39" and b["ubuntu_2404"]["gcc"] == "14"


def test_two_personalities_profile_choice():
    tp = _c()["two_personalities"]
    assert "sovereign" in tp["debian"] and "AppArmor defaults" in tp["ubuntu"]
    assert tp["note"] == "That is not a contradiction. It is a profile choice"


def test_peace_machine_ten_coordination_properties():
    pm = _c()["peace_machine"]
    assert len(pm["coordination_properties"]) == 10 and "consent" in pm["coordination_properties"]
    assert pm["accountable_ai_model"] == ["AI proposes", "Policy checks",
                                          "Tools execute in bounded space", "Traces record",
                                          "User can inspect", "System learns"]
    assert pm["closing"] == "That is peace through legibility"


def test_security_substrate_six_vectors_four_profiles():
    ss = _c()["security_substrate"]
    assert len(ss["sandbox_vectors"]) == 6 and "rootless Podman" in ss["sandbox_vectors"]
    profiles = [x["profile"] for x in ss["profile_bundles"]]
    assert profiles == ["secure", "developer", "agent-lab", "high-risk"]
    assert ss["note"] == "Security is not one setting. It is a user-visible operating mode"


def test_secrets_seven_controls_and_cryptenroll():
    si = _c()["secrets_and_identity"]
    assert len(si["controls"]) == 7 and "LUKS2 full disk encryption" in si["controls"]
    assert si["cryptenroll"]["enrolls"] == ["TPM2", "FIDO2", "PKCS#11"]
    assert si["identity_triad"] == ["user presence", "device identity",
                                    "encrypted memory of the system"]


def test_nvidia_reality_driver_and_abstraction():
    nv = _c()["nvidia_reality"]
    assert nv["driver_listing"]["driver"] == "590.48.01"
    assert "Blackwell Server Edition" in nv["driver_listing"]["device"]
    assert nv["driver_profile_abstraction"]["core_base"] == "Debian-like sovereign policy"


def test_avx_build_matrix_four_paths_and_doctrine():
    kc = _c()["kernel_and_compiler"]
    assert kc["avx_build_matrix"]["paths"] == ["portable scalar baseline", "AVX2 path",
                                               "AVX-512 Zen5 path", "runtime CPUID dispatch"]
    assert kc["avx_build_matrix"]["doctrine"] == "Never assume. Detect"
    assert "znver5" in kc["zen5_note"]


def test_eight_sovereign_os_planes_verbatim():
    p = [x["plane"] for x in _c()["sovereign_os_planes"]["planes"]]
    assert p == ["Kernel", "Security", "Compute", "Storage", "Sandbox", "Gateway",
                 "Observability", "Choice"], f"plane drift: {p}"


def test_eight_accountability_questions():
    q = _c()["accountability_questions"]["questions"]
    assert len(q) == 8 and q[0] == "Who asked?" and q[-1] == "Should it become memory?"


def test_key_line_and_peace_machine_composition():
    assert "not a distro with AI installed" in _c()["key_line"]
    assert "permissioned, observable, reversible, and user-chosen" in _c()["key_line"]
    pmc = _c()["peace_machine_composition"]
    assert len(pmc["substrate"]) == 7
    assert pmc["doctrine"] == "powerful enough to act, disciplined enough to explain itself"


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00732", "M00733", "M00736", "M00739", "M00740", "M00745", "M00747"):
        assert mod in body, f"{mod} not in the M044 milestone (must trace to spec)"
