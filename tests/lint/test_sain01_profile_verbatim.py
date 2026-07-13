"""R387 (E10.M31) — sain-01 profile operator-verbatim content lint.

The default profile `profiles/sain-01.yaml` IS the operator's
reference workstation. Operator-verbatim content from master spec
§1 (hardware) + §2.2 (KCFLAGS) + §1b hardware-spec drop lives in
this YAML. If silent drift occurs (e.g., agent shortens the KCFLAGS
list or rephrases a vendor SKU), the build pipeline ships a kernel
that doesn't match operator intent.

R387 pins specific operator-verbatim strings in sain-01.yaml so
silent drift fails at push.

Pinned content (revised 2026-06-10 after the first real hardware build —
the original §2.2 avx512-KCFLAGS list caused early boot failures because
the kernel cannot use vector ISA, and avx512_fp16 is absent on the
physical 9900X; the secondary GPU procured is an RTX 4090, not the
originally-spec'd RTX 4090):
  - §2.2 KCFLAGS string (11-flag list: -march=znver5 + 6 -mno-* vector
    ISA opt-outs + -O3 -pipe -mabm -madx)
  - §2.2 KCPPFLAGS (-march=znver5)
  - §1.1 hardware SKUs: Ryzen 9 9900X / RTX PRO 6000 Blackwell /
    RTX 4090 / ASUS ProArt X870E-CREATOR / Marvell AQC113C
  - §1.2 PCIe rule: M.2_2 slot empty constraint mentioned
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILE = REPO_ROOT / "profiles" / "sain-01.yaml"


def _read_profile() -> str:
    assert PROFILE.is_file(), f"missing {PROFILE}"
    return PROFILE.read_text(encoding="utf-8")


def test_sain01_profile_exists():
    assert PROFILE.is_file(), f"missing {PROFILE}"


def test_kcflags_verbatim_preserved():
    """§2.2 KCFLAGS MUST appear verbatim in profile — as revised
    2026-06-10 (first real build): the kernel cannot use vector ISA
    (no kernel_fpu_begin around compiler-emitted SIMD), so the original
    -mavx512* list SIGILL'd at early boot. The operator-approved list
    now EXPLICITLY OPTS OUT of every vector ISA tier."""
    body = _read_profile()
    # Operator-verbatim §2.2 KCFLAGS string (11 flags, 2026-06-10)
    must_have = [
        "-march=znver5",
        "-mno-mmx",
        "-mno-sse",
        "-mno-sse2",
        "-mno-avx",
        "-mno-avx2",
        "-mno-avx512f",
        "-O3",
        "-pipe",
        "-mabm",
        "-madx",
    ]
    missing = [f for f in must_have if f not in body]
    assert not missing, (
        f"profiles/sain-01.yaml KCFLAGS missing operator-verbatim §2.2 "
        f"flags: {missing}. The operator's exact 11-flag list (revised "
        f"2026-06-10 — kernel builds must disable vector ISA to avoid "
        f"early-boot SIGILL) MUST be preserved so make bindeb-pkg emits "
        f"a kernel matching operator intent."
    )
    # Guard against the original avx512-enabling list silently coming
    # back: no -mavx512* may appear on the KCFLAGS line itself.
    for line in body.splitlines():
        if "KCFLAGS" in line:
            assert "-mavx512" not in line, (
                f"KCFLAGS line re-enables avx512 ({line!r}) — the kernel "
                f"cannot use vector ISA; this caused the 2026-06-10 "
                f"early-boot failure"
            )


def test_kcppflags_verbatim_preserved():
    """KCPPFLAGS=-march=znver5 (operator-verbatim §2.2)."""
    body = _read_profile()
    assert "KCPPFLAGS" in body, "profile missing KCPPFLAGS"
    # The KCPPFLAGS line should contain -march=znver5
    for line in body.splitlines():
        if "KCPPFLAGS" in line:
            assert "-march=znver5" in line, (
                f"KCPPFLAGS line doesn't contain -march=znver5: {line!r}"
            )


def test_hardware_skus_present():
    """Operator §1.1 hardware-spec SKUs present in profile (operator-
    verbatim form OR normalized lowercase-slug form — both acceptable
    in YAML identifiers; the canonical verbatim form lives in the
    inventory catalog + C-16 concept)."""
    body = _read_profile()
    # Check for either operator-verbatim OR slug form per SKU
    # CPU acceptable forms: full SKU "Ryzen 9 9900X", or architecture
    # identifier "amd-zen5" / "znver5" (operator's exact 9900X SKU lives
    # in inventory-catalog + C-16 concept; profile uses architecture-level)
    sku_alternatives = [
        ("Ryzen 9 9900X", "znver5"),          # CPU (verbatim OR znver5)
        ("RTX 5090", "rtx-5090"),             # internal primary GPU (SDD-993, power-limited ~350W)
        ("RTX 4090", "rtx-4090"),             # now the OcuLink eGPU (was internal-VFIO secondary)
        ("RTX PRO 6000", "rtx-pro-6000"),    # future large-VRAM Oracle-Core path (kept, not discarded)
        ("ProArt X870E", "x870e"),            # motherboard
        ("Marvell AQC113C", "marvell"),       # 10GbE NIC vendor
    ]
    missing = []
    for verbatim, slug in sku_alternatives:
        if verbatim not in body and slug.lower() not in body.lower():
            missing.append((verbatim, slug))
    assert not missing, (
        f"profiles/sain-01.yaml missing §1.1 hardware SKUs (in either "
        f"verbatim or slug form): {missing}"
    )


def test_kernel_version_target():
    """Master spec §2.1 target: Linux Kernel 6.12+ for Blackwell/Zen 5."""
    body = _read_profile()
    # Should reference 6.12 or higher (linux-image-${KERNEL_VERSION}…
    # may have variable substitution; check the raw string)
    has_version = "6.12" in body or "6.1" in body or "KERNEL_VERSION" in body
    assert has_version, (
        "profiles/sain-01.yaml doesn't reference kernel 6.12+ "
        "(operator §2.1 target for Blackwell/Zen 5 native support)"
    )


def test_avx512_extensions_complete():
    """All 6 required avx512 CPU features present in the profile's
    hardware.cpu.features.required list (count check; not just any one
    of them — operator's exact list of 6, revised 2026-06-10:
    avx512_fp16 OUT — verified absent on the physical 9900X, AVX512-FP16
    is Intel-only; avx512_vnni IN). Userspace still gets the full AVX-512
    feature set; only the KERNEL build opts out of vector ISA."""
    import yaml

    profile = yaml.safe_load(_read_profile())
    required = profile["hardware"]["cpu"]["features"]["required"]
    expected = {"avx512f", "avx512_vnni", "avx512_bf16",
                "avx512dq", "avx512bw", "avx512vl"}
    missing = expected - set(required)
    assert not missing, (
        f"expected all 6 required avx512 CPU features; missing: "
        f"{sorted(missing)} (required list: {required})"
    )
    assert "avx512_fp16" not in required, (
        "avx512_fp16 re-entered features.required — it is ABSENT on the "
        "physical 9900X (verified /proc/cpuinfo 2026-06-10; Intel-only "
        "extension) and requiring it would fail the friction audit on "
        "the operator's own hardware"
    )


def test_no_silent_arch_corruption():
    """profile MUST NOT have any non-znver5 -march= value. Catches:
    agent silently changes -march=znver5 → -march=znver4 or generic."""
    body = _read_profile()
    import re
    march_values = re.findall(r"-march=(\w+)", body)
    bad = [v for v in march_values if v != "znver5"]
    assert not bad, (
        f"profile contains non-znver5 -march= values: {bad}. The operator's "
        f"§2.2 spec requires -march=znver5 only."
    )


def test_gpu_topology_present():
    """§1.1 GPU topology (SDD-993) MUST appear in profile hardware section
    (slug or verbatim form): all three installed cards — the RTX PRO 6000
    primary/main Oracle, the RTX 5090 internal secondary, and the RTX 4090
    OcuLink eGPU."""
    body_lower = _read_profile().lower()
    primary_present = "rtx pro 6000" in body_lower or "rtx-pro-6000" in body_lower
    secondary_present = "rtx 5090" in body_lower or "rtx-5090" in body_lower
    egpu_present = "rtx 4090" in body_lower or "rtx-4090" in body_lower
    assert primary_present, "primary/main Oracle GPU (RTX PRO 6000) missing"
    assert secondary_present, "internal secondary GPU (RTX 5090) missing"
    assert egpu_present, "OcuLink eGPU (RTX 4090) missing"
    # the RTX PRO 6000 is the declared role: primary (main card)
    assert "role: primary" in _read_profile(), "no role: primary GPU declared"


def test_m2_2_empty_constraint_documented():
    """§1.2 (SDD-993): with TWO internal cards (PRO 6000 + 5090) running x8/x8,
    M.2_2 (which shares lanes with PCIEX16_2, the 5090's slot) MUST remain empty
    or the 5090 drops to x4. The OcuLink 4090 eGPU is on a separate chipset M.2
    slot — NOT M.2_2. The profile MUST document the M.2_2-empty constraint."""
    body = _read_profile()
    assert "M.2_2" in body, (
        "profile missing M.2_2 slot constraint documentation"
    )
    body_lower = body.lower()
    assert "m2_2_empty" in body_lower or "m.2_2 must" in body_lower or "m.2_2 must remain empty" in body_lower, (
        "profile mentions M.2_2 but not the must-remain-empty constraint (SDD-993)"
    )
    # the OcuLink eGPU is still documented (on a chipset slot, not M.2_2)
    assert "oculink" in body_lower, "profile missing the OcuLink eGPU (RTX 4090) documentation"
