"""M067 custom-kernel-build-pipeline contract lint.

Locks `config/hardware/m067-kernel-build-pipeline.yaml` to the M067 spec: the
toolchain (E0649), vanilla fetch (E0650), config hardening (E0651), compilation
invocation (E0652), host deployment (E0653), AVX-512 subset (E0654), GGML backend
flags (E0655), bindeb-pkg output (E0656), and reproducibility (E0657). No
minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "hardware" / "m067-kernel-build-pipeline.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M067-custom-kernel-build-pipeline-znver5-avx512.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M067"


def test_toolchain_thirteen_packages():
    p = _c()["toolchain"]["packages"]
    assert p == ["build-essential", "libncurses-dev", "bison", "flex", "libssl-dev",
                 "libelf-dev", "xz-utils", "git", "bc", "systemd-dev", "pahole",
                 "gcc-14", "g++-14"], f"toolchain drift: {p}"


def test_source_fetch_tmpfs():
    sf = _c()["source_fetch"]
    assert "6.12+ LTS" in sf["kernel"]
    assert "tmpfs" in sf["build_mount"]


def test_config_hardening_strips_legacy():
    ch = _c()["config_hardening"]["strip_legacy"]
    assert ch == ["amateur radio", "obsolete filesystems", "debug options"]


def test_cflags_verbatim():
    assert _c()["cflags"] == ("-march=znver5 -mavx512f -mavx512dq -mavx512bw "
                              "-mavx512vl -mavx512bf16 -mavx512fp16")


def test_avx512_subset_six():
    assert _c()["avx512_subset"]["subsets"] == ["F", "DQ", "BW", "VL", "BF16", "FP16"]


def test_compilation_invocation_verbatim():
    c = _c()["compilation"]
    assert c["invocation"] == ('make -j$(nproc) KCFLAGS="-march=znver5 -O3" '
                               'KCPPFLAGS="-march=znver5 -O3" bindeb-pkg')
    assert c["kcflags"] == "-march=znver5 -O3"


def test_ggml_three_flags():
    assert _c()["ggml_flags"]["flags"] == ["GGML_AVX512", "GGML_AVX512_VBMI",
                                           "GGML_AVX512_VNNI"]


def test_build_output_debs():
    d = _c()["build_output"]["debs"]
    assert d == ["linux-image-6.12.*-znver5_*.deb", "linux-headers-6.12.*-znver5_*.deb"]


def test_reproducibility_signed_and_recorded():
    r = _c()["reproducibility"]["rule"]
    assert "signed via MS003" in r and "docs/decisions.md" in r


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M01122", "M01125", "M01127", "M01128", "M01130", "M01131", "M01132"):
        assert mod in body, f"{mod} not in the M067 milestone (must trace to spec)"
