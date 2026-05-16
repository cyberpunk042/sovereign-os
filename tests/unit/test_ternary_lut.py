"""Layer 2 unit tests for scripts/pulse/lib/ternary_lut.py (R164).

Locks in correctness of the reference implementation of master spec
§§ 15-16 (SDD-027). The reference module is documentation-grade, not
a hot path — but the round-trip + naive-equivalence properties MUST
hold or the documented algorithm is wrong.
"""

from __future__ import annotations

import pathlib
import random
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "scripts" / "pulse" / "lib"
sys.path.insert(0, str(LIB_DIR))

from ternary_lut import (  # noqa: E402
    accumulate,
    accumulate_from_planes,
    bit_plane_transpose,
    pack_ternary,
    unpack_ternary,
)


# ---------- pack / unpack round-trip ----------

@pytest.mark.parametrize(
    "weights",
    [
        [],
        [0],
        [1],
        [-1],
        [0, 1, -1, 0],
        [0] * 4,
        [1] * 4,
        [-1] * 4,
        [1, 0, -1, 1, 0, -1, 1, 0],  # 8 weights = 2 bytes
        [1, 0, -1, 1, 0, -1, 1],     # 7 weights = 2 bytes (partial)
    ],
)
def test_pack_unpack_roundtrip(weights):
    packed = pack_ternary(weights)
    assert unpack_ternary(packed, len(weights)) == weights


def test_pack_rejects_non_ternary():
    with pytest.raises(ValueError):
        pack_ternary([2])
    with pytest.raises(ValueError):
        pack_ternary([-2])
    with pytest.raises(ValueError):
        pack_ternary([0.5])


def test_unpack_rejects_invalid_pattern():
    # 0b11 is the reserved/invalid pattern; corrupt a byte
    bad = bytes([0b11])
    with pytest.raises(ValueError):
        unpack_ternary(bad, 1)


def test_unpack_short_buffer_raises():
    with pytest.raises(ValueError):
        unpack_ternary(b"", 4)


def test_unpack_negative_n_raises():
    with pytest.raises(ValueError):
        unpack_ternary(b"\x00", -1)


# ---------- accumulate semantics (master spec § 15.1 verbatim) ----------

def test_accumulate_plus_one_adds():
    assert accumulate([1, 1, 1], [10, 20, 30]) == 60


def test_accumulate_minus_one_subtracts():
    assert accumulate([-1, -1, -1], [10, 20, 30]) == -60


def test_accumulate_zero_is_noop():
    assert accumulate([0, 0, 0], [99, 99, 99]) == 0


def test_accumulate_mixed_matches_naive():
    weights = [1, -1, 0, 1, -1, 0]
    acts = [10, 20, 30, 40, 50, 60]
    naive = sum(w * a for w, a in zip(weights, acts))
    assert accumulate(weights, acts) == naive


def test_accumulate_length_mismatch_raises():
    with pytest.raises(ValueError):
        accumulate([1, 0], [1, 2, 3])


def test_accumulate_rejects_non_ternary():
    with pytest.raises(ValueError):
        accumulate([2], [10])


# ---------- bit-plane transpose ----------

def test_bit_plane_transpose_zero_weights():
    packed = pack_ternary([0] * 8)
    pn, pg = bit_plane_transpose(packed, 8)
    assert pn == b"\x00"
    assert pg == b"\x00"


def test_bit_plane_transpose_all_plus_one():
    packed = pack_ternary([1] * 8)
    pn, pg = bit_plane_transpose(packed, 8)
    assert pn == b"\xff"  # all nonzero
    assert pg == b"\x00"  # none negative


def test_bit_plane_transpose_all_minus_one():
    packed = pack_ternary([-1] * 8)
    pn, pg = bit_plane_transpose(packed, 8)
    assert pn == b"\xff"  # all nonzero
    assert pg == b"\xff"  # all negative


def test_accumulate_from_planes_matches_reference():
    weights = [1, -1, 0, 1, 0, -1, 1, -1, 0, 1, -1, 0]
    acts = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60]
    packed = pack_ternary(weights)
    pn, pg = bit_plane_transpose(packed, len(weights))
    assert accumulate_from_planes(pn, pg, acts) == accumulate(weights, acts)


# ---------- Property test: 50 random trials ----------

def test_property_random_trials_all_paths_agree():
    rng = random.Random(20260516)
    for trial in range(50):
        n = rng.randint(1, 300)
        weights = [rng.choice([-1, 0, 1]) for _ in range(n)]
        acts = [rng.randint(-128, 127) for _ in range(n)]
        packed = pack_ternary(weights)
        assert unpack_ternary(packed, n) == weights, f"trial {trial}: roundtrip"
        pn, pg = bit_plane_transpose(packed, n)
        naive = sum(w * a for w, a in zip(weights, acts))
        ref = accumulate(weights, acts)
        from_planes = accumulate_from_planes(pn, pg, acts)
        assert naive == ref == from_planes, (
            f"trial {trial} n={n}: naive={naive} ref={ref} planes={from_planes}"
        )


# ---------- SDD-027 cross-reference ----------

def test_sdd_027_present():
    sdd = REPO_ROOT / "docs" / "sdd" / "027-pulse-algorithmic-foundation.md"
    assert sdd.exists(), "SDD-027 must exist (codifies this module's reason)"
    text = sdd.read_text()
    # Verbatim master spec citations
    assert "master spec § 15" in text
    assert "master spec § 16" in text
    assert "bit-plane transposition" in text
