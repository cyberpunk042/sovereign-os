"""The M00019/M00020 round-update engine is REAL + TESTABLE (M002).

Pure u64 bit-ops — the scalar mirror of crate sovereign-simd::round, whose
AVX-512 kernel is proven bit-identical to that scalar reference. This locks the
Python engine to the SAME parity constant the Rust crate pins, so the panel,
the CLI, the crate scalar, and the AVX-512 kernel all agree — none can drift
without a test failing.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ENGINE = REPO / "scripts" / "hardware" / "simd-round.py"


def _mod():
    spec = importlib.util.spec_from_file_location("_sr", ENGINE)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_engine_present():
    assert ENGINE.is_file(), f"missing {ENGINE}"


def test_five_step_semantics():
    m = _mod()
    # R00289 extract: 6-bit condition
    assert m.extract_features(0b111, 0, 0) == 0b111
    assert m.extract_features(0xFFFF_FFFF_FFFF_FFFF, 0, 0) == 0x3F  # masked to 6 bits
    # R00290 decision: (rule >> features) & 1
    assert m.decide(0b101010, 1) == 1
    assert m.decide(0b101010, 2) == 0
    # R00291 apply: state<<1 | decision
    assert m.apply_state(0b1, 1) == 0b11
    # R00292 memory: (memory>>1) | ((old_state&1)<<63)
    assert m.update_memory(0, 1) == (1 << 63)
    assert m.update_memory(0b10, 0) == 0b1
    # R00293 advance: xorshift64 is deterministic and non-identity for non-zero
    assert m.advance_rng(1) != 1
    assert m.advance_rng(0) == 0  # a zero lane locks at zero (seed non-zero)


def test_parity_constant_matches_the_rust_crate():
    m = _mod()
    s = {p: [1, 2, 3, 4, 5, 6, 7, 8] for p in ("state", "memory", "rule", "random")}
    cur = s
    for _ in range(3):
        cur = m.round_update(cur)
    assert cur["state"] == [0x8, 0x10, 0x18, 0x20, 0x28, 0x30, 0x38, 0x40]
    assert cur["memory"] == [
        0x2000000000000000, 0x0, 0x2000000000000000, 0x0,
        0x2000000000000000, 0x0, 0x2000000000000000, 0x1,
    ]
    assert cur["rule"] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert cur["random"] == [
        0x9B1E842F6E862629, 0x363D895AD50E6812, 0xAD230D75BB884E3B, 0x6C7B12B5AA1CD024,
        0xF765969AC49AF60D, 0x5A469BEF7F12B836, 0xC1581FC011949E1F, 0xD8F6256B5439A048,
    ]


def test_branchless_and_branchy_and_dna():
    m = _mod()
    # masked-op mode never changes output (F00110): decide is the single impl.
    assert m.decide(0xACE1, 5) == ((0xACE1 >> 5) & 1)
    # per-lane DNA (F00130): same rule, different state → divergent evolution.
    s = {"state": list(range(1, 9)), "memory": [0] * 8,
         "rule": [0xACE1] * 8, "random": [i | 1 for i in range(1, 9)]}
    cur = s
    for _ in range(20):
        cur = m.round_update(cur, per_lane_dna=True)
    assert len(set(cur["state"])) > 1, "DNA mode did not diverge per lane"


def test_variable_shift_semantics():
    m = _mod()
    # M00021 VPSLLVQ: per-lane shift, ≥64 → 0
    out = m.variable_shift_left([1, 1, 0xFF, 2], [0, 63, 8, 64] + [0] * 4)  # padded to 8
    assert out[0] == 1
    assert out[1] == (1 << 63)
    assert out[2] == 0xFF00
    assert out[3] == 0  # shift == 64 → 0


def test_lane_fields_round_trip_and_overflow():
    m = _mod()
    f = {"state_lo": 0x1234, "state_hi": 0x5678, "control": 0x9ABC, "scratch": 0xDEF0}
    assert m.lane_unpack(m.lane_pack(f)) == f
    assert m.lane_pack({"state_lo": 0xFFFF, "state_hi": 0xFFFF,
                        "control": 0xFFFF, "scratch": 0xFFFF}) == (1 << 64) - 1
    import pytest
    with pytest.raises(ValueError):
        m.lane_pack({"control": 0x1_0000})  # 16-bit field overflow


def test_round_config_resolution_matches_crate():
    m = _mod()
    # defaults — mirror crate RoundConfig::default()
    assert m.resolve_round_config(lambda _k: None) == {
        "masked_op": "branchless", "per_lane_dna": False}
    # both knobs hot-swap
    env = {"SOVEREIGN_CTRL_MASKED_OP_MODE": "branchy",
           "SOVEREIGN_CTRL_PER_LANE_DNA_ENABLED": "true"}
    assert m.resolve_round_config(lambda k: env.get(k)) == {
        "masked_op": "branchy", "per_lane_dna": True}
    # invalid → defaults
    bad = {"SOVEREIGN_CTRL_MASKED_OP_MODE": "sideways",
           "SOVEREIGN_CTRL_PER_LANE_DNA_ENABLED": "maybe"}
    assert m.resolve_round_config(lambda k: bad.get(k)) == {
        "masked_op": "branchless", "per_lane_dna": False}


def test_cli_config_verb_reads_env():
    import json
    import os
    e = dict(os.environ)
    e["SOVEREIGN_CTRL_PER_LANE_DNA_ENABLED"] = "on"
    r = subprocess.run([sys.executable, str(ENGINE), "config", "--json"],
                       capture_output=True, text=True, timeout=20, env=e)
    assert r.returncode == 0 and json.loads(r.stdout)["per_lane_dna"] is True


def test_cli_round_variable_shift_lane_fields():
    def run(*a):
        return subprocess.run([sys.executable, str(ENGINE), *a],
                              capture_output=True, text=True, timeout=20)
    r = run("round", "--rounds", "3", "--json")
    assert r.returncode == 0 and '"0x8"' not in r.stdout  # JSON emits ints, not hex strs
    import json
    got = json.loads(run("round", "--rounds", "3", "--json").stdout)["result"]
    assert got["state"] == [0x8, 0x10, 0x18, 0x20, 0x28, 0x30, 0x38, 0x40]
    r = run("variable-shift", "--values", "1,1,255,2,0,0,0,0",
            "--shifts", "0,63,8,64,0,0,0,0", "--json")
    assert r.returncode == 0 and json.loads(r.stdout)["result"][3] == 0
    r = run("lane-fields", "--control", "70000")  # overflow → exit 2
    assert r.returncode == 2
