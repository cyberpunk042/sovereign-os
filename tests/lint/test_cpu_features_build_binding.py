"""SDD-043 Phase 1 — CPU-feature → build binding lockstep.

Locks the connective tissue authored in scripts/build/cpu-features.py:
every CPU feature any profile declares (hardware.cpu.features) MUST map
to a real rustc target-feature, every march MUST be a known target-cpu,
and the operator's exploited instructions (VNNI / BF16 / popcnt) MUST
actually reach the emitted userspace RUSTFLAGS for sain-01. Drift — a
new feature added to a profile with no mapping, or the exploit flags
silently dropped from the build — fails here at push instead of shipping
a build that doesn't use the hardware it claims.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILES_DIR = REPO_ROOT / "profiles"
SCRIPT = REPO_ROOT / "scripts" / "build" / "cpu-features.py"


def _mod():
    spec = importlib.util.spec_from_file_location("cpu_features", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _profile_files() -> list[Path]:
    return sorted(PROFILES_DIR.glob("*.yaml"))


def _declared_features(profile_path: Path) -> list[str]:
    d = yaml.safe_load(profile_path.read_text()) or {}
    feats = ((d.get("hardware") or {}).get("cpu") or {}).get("features") or {}
    return list(feats.get("required") or []) + list(feats.get("preferred") or [])


def test_script_present_and_executable():
    assert SCRIPT.is_file(), f"missing {SCRIPT}"
    assert SCRIPT.stat().st_mode & 0o111, "cpu-features.py must be executable"


def test_every_declared_feature_maps():
    """Every hardware.cpu.features entry in every profile has a rustc
    target-feature mapping (no typo'd / unmappable feature ships)."""
    m = _mod()
    missing: list[str] = []
    for p in _profile_files():
        for feat in _declared_features(p):
            if feat not in m.FEATURE_MAP:
                missing.append(f"{p.name}:{feat}")
    assert not missing, (
        "CPU features declared in profiles with NO rustc target-feature "
        f"mapping (add to FEATURE_MAP): {missing}"
    )


def test_every_march_is_known():
    m = _mod()
    bad: list[str] = []
    for p in _profile_files():
        d = yaml.safe_load(p.read_text()) or {}
        march = ((d.get("hardware") or {}).get("cpu") or {}).get("march")
        if march is not None and march not in m.MARCH_MAP:
            bad.append(f"{p.name}:{march}")
    assert not bad, f"profiles declare march with no target-cpu mapping: {bad}"


def test_feature_map_tokens_are_sane():
    """Mapped tokens look like rustc target-features: lowercase, no spaces,
    no leading +/- (the emitter adds the +)."""
    m = _mod()
    for name, tok in m.FEATURE_MAP.items():
        assert tok == tok.lower(), f"{name} → {tok!r} not lowercase"
        assert " " not in tok and not tok.startswith(("+", "-")), (
            f"{name} → {tok!r} malformed target-feature"
        )


def test_sain01_exploit_flags_reach_the_build():
    """The operator's headline exploited instructions — VNNI (VPDPBUSD),
    BF16 (VDPBF16PS), popcount — MUST appear in sain-01's emitted
    RUSTFLAGS, targeting znver5. This is the whole point of Phase 1:
    declaring them drives the build."""
    m = _mod()
    profile = yaml.safe_load((PROFILES_DIR / "sain-01.yaml").read_text())
    march, feats = m.cpu_features(profile)
    flags = m.rustflags(march, feats)
    assert "-C target-cpu=znver5" in flags, flags
    # T1 foundation + T2 compute + T3 byte/permute exploited instructions
    # (the tiered plan) must all reach the build.
    for must in (
        "+avx512f", "+avx512vnni", "+avx512bf16", "+popcnt",   # baseline + INT8/BF16
        "+avx512vpopcntdq", "+avx512vp2intersect",             # T2 vector popcount + intersect
        "+avx512vbmi", "+avx512vbmi2", "+avx512bitalg",        # T3 permute/shift/byte-bitalg
    ):
        assert must in flags, f"sain-01 RUSTFLAGS missing {must}: {flags}"


def test_kernel_stays_vector_disabled_userspace_opts_in():
    """SDD-043 Q-1 invariant: the feature→build overlay is USERSPACE
    (RUSTFLAGS enabling +avx512*), while the kernel KCFLAGS deliberately
    DISABLE vector ISA. Guard that the two directions don't get crossed:
    sain-01's KCFLAGS must still carry -mno-avx512f while its emitted
    RUSTFLAGS enable +avx512f."""
    m = _mod()
    body = (PROFILES_DIR / "sain-01.yaml").read_text()
    assert "-mno-avx512f" in body, "kernel KCFLAGS lost its vector-ISA opt-out"
    profile = yaml.safe_load(body)
    march, feats = m.cpu_features(profile)
    assert "+avx512f" in m.rustflags(march, feats), "userspace lost +avx512f"
