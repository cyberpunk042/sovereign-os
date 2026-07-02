"""Gate the avx512-advisor /proc/cpuinfo flag mapping.

Every flag in AVX512_FLAGS must map to the real /proc/cpuinfo flag name. Three
of them (VAES / VPCLMULQDQ / GFNI) are AVX-512-capable but are separate CPUID
bits the kernel exposes WITHOUT the `avx512` prefix; the computed default
("avx512vaes" …) is wrong for them, so without explicit overrides the advisor
reports them missing on a CPU (e.g. Zen5) that actually has them.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ADVISOR = REPO_ROOT / "scripts" / "hardware" / "avx512-advisor.py"


def _load():
    spec = importlib.util.spec_from_file_location("avx512_advisor", ADVISOR)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_every_flag_is_mapped():
    m = _load()
    for flag in m.AVX512_FLAGS:
        assert flag in m.FLAG_LOWERCASE, f"{flag} has no cpuinfo mapping"


def test_separate_cpuid_bits_have_no_avx512_prefix():
    # The real /proc/cpuinfo flags for these three carry no avx512 prefix.
    m = _load()
    assert m.FLAG_LOWERCASE["VAES"] == "vaes"
    assert m.FLAG_LOWERCASE["VPCLMULQDQ"] == "vpclmulqdq"
    assert m.FLAG_LOWERCASE["GFNI"] == "gfni"


def test_avx512_family_flags_keep_their_prefix():
    # The genuine AVX-512 sub-extensions DO carry the prefix.
    m = _load()
    assert m.FLAG_LOWERCASE["F"] == "avx512f"
    assert m.FLAG_LOWERCASE["VNNI"] == "avx512_vnni"
    assert m.FLAG_LOWERCASE["BF16"] == "avx512_bf16"
    # VP2INTERSECT (the note's T2 correlation op) must be in the map.
    assert m.FLAG_LOWERCASE["VP2INTERSECT"] == "avx512_vp2intersect"


def test_m085_tier_instructions_map_to_real_flags():
    # Every instruction in the operator's three-tier note maps to a flag that
    # exists in AVX512_FLAGS, and VP2INTERSECT is the only one Zen 5 lacks.
    m = _load()
    for entry in m.TIER_INSTRUCTIONS:
        assert entry["flag"] in m.AVX512_FLAGS, entry
        for key in ("tier", "instruction", "operator_mnemonic", "engine", "note"):
            assert key in entry, entry
    assert m.ZEN5_ABSENT_FLAGS == {"VP2INTERSECT"}
    # T1 is the wired tier (INT8 + BF16 in the model path).
    t1 = [e for e in m.TIER_INSTRUCTIONS if e["tier"] == "T1"]
    assert t1 and all(e["engine"] == "wired" for e in t1), t1
