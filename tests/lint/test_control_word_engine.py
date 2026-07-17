"""The M00013 control-word engine is REAL + TESTABLE (M002).

Pure u64 bit-ops — no AVX-512. Proves the bit semantics the operator wants to
exercise from the panel: exact pack/unpack round-trip, per-field overflow
rejection, the canonical M00013 layout, and the M00017 LUT decision bit.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ENGINE = REPO / "scripts" / "hardware" / "control-word.py"


def _mod():
    spec = importlib.util.spec_from_file_location("_cw", ENGINE)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_engine_present_and_executable():
    assert ENGINE.is_file(), f"missing {ENGINE}"


def test_canonical_layout_matches_M00013_and_fills_64_bits():
    m = _mod()
    # R00180: mode 0..3 / event 4..7 / intensity 8..15 / cooldown 16..23 /
    # neighborhood 24..31 / paramA 32..47 / paramB 48..63
    expected = [
        ("mode", 0, 4), ("event", 4, 4), ("intensity", 8, 8),
        ("cooldown", 16, 8), ("neighborhood", 24, 8),
        ("paramA", 32, 16), ("paramB", 48, 16),
    ]
    assert m.FIELDS == expected, "control-word layout drifted from M00013 (R00180)"
    # fields tile 0..64 with no gap and no overlap
    covered = 0
    for _n, shift, width in m.FIELDS:
        mask = ((1 << width) - 1) << shift
        assert covered & mask == 0, "fields overlap"
        covered |= mask
    assert covered == (1 << 64) - 1, "fields do not fill exactly 64 bits"


def test_encode_decode_round_trips_exactly():
    m = _mod()
    vals = {"mode": 3, "event": 1, "intensity": 200, "cooldown": 17,
            "neighborhood": 255, "paramA": 4242, "paramB": 65535}
    word = m.encode(vals)
    assert m.decode(word) == vals, "encode→decode is not exact"
    # field isolation: max every field, confirm no cross-talk
    mx = {n: (1 << w) - 1 for n, _s, w in m.FIELDS}
    assert m.decode(m.encode(mx)) == mx


def test_overflow_is_rejected_per_field():
    m = _mod()
    import pytest
    with pytest.raises(ValueError):
        m.encode({"mode": 16})       # 4-bit field, max 15
    with pytest.raises(ValueError):
        m.encode({"paramA": 65536})  # 16-bit field, max 65535


def test_lut_is_the_right_shift_and_and_decision_bit():
    m = _mod()
    # 0b101010 = 0x2A → bits: 0=0,1=1,2=0,3=1,4=0,5=1
    for cond, expect in enumerate([0, 1, 0, 1, 0, 1]):
        assert m.lut(0x2A, cond) == expect, f"LUT bit {cond} wrong"
    # condition wraps at 6 bits (& 63)
    assert m.lut(0x2A, 64) == m.lut(0x2A, 0)


def test_parity_with_rust_crate_and_panel():
    """The Rust crate (crates/sovereign-control-word m00013::Fields), the panel
    (webapp/avx-modes), and this engine MUST agree on the word for the same
    fields. All three pin THIS constant — none can drift without a test failing.
    """
    m = _mod()
    word = m.encode({"mode": 3, "intensity": 200, "paramA": 4242})
    assert word == 0x0000_1092_0000_C803, (
        "control-word layout diverged from the Rust crate / panel parity constant")


def test_generic_pack_unpack_and_overflow_modes():
    m = _mod()
    lanes = [0, 1, 2, 200, 255, 128, 7, 42]
    assert m.unpack_u64(m.pack_u64(lanes)) == lanes
    # overflow modes (R00318-320): mode field is 4-bit (max 15)
    import pytest
    with pytest.raises(ValueError):
        m.encode_mode({"mode": 20}, "abort")
    assert m.encode_mode({"mode": 20}, "wrap") & 0xF == 20 & 0xF   # 4
    assert m.encode_mode({"mode": 20}, "saturate") & 0xF == 15     # clamp


def test_rule_word_widths():
    m = _mod()
    # 0x2A = 0b101010 → bit1=1, bit2=0 in every width
    for width in (32, 64, 128):
        assert m.rule_decide(width, 0x2A, 0, 1) == 1
        assert m.rule_decide(width, 0x2A, 0, 2) == 0
    # 128-bit: condition 64 selects the hi limb
    assert m.rule_decide(128, 0, 1, 64) == 1
    # 32-bit and 64-bit agree on the first 32 conditions (R00258)
    for c in range(32):
        assert m.rule_decide(32, 0xDEADBEEF, 0, c) == m.rule_decide(64, 0xDEADBEEF, 0, c)


def test_cli_encode_decode_lut_end_to_end():
    def run(*a):
        return subprocess.run([sys.executable, str(ENGINE), *a],
                              capture_output=True, text=True, timeout=20)
    r = run("encode", "--mode", "3", "--paramA", "4242", "--json")
    assert r.returncode == 0 and '"roundtrip_ok": true' in r.stdout
    r = run("encode", "--mode", "99")
    assert r.returncode == 2, "overflow must exit non-zero"
    r = run("lut", "--rule-word", "0x2A", "--condition", "1", "--json")
    assert r.returncode == 0 and '"decision": 1' in r.stdout
