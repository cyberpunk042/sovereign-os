"""The M002 control-word SERVICE layer is REAL + TESTABLE.

Per-lane DNA fingerprints (FNV-1a, dependency-free per the replay-ledger
precedent), diversity index, quarantine on drift, and Prometheus metrics text.
The Python mirror is locked to the SAME fingerprint parity constants the crate
sovereign-control-word-service pins — crate + CLI + the gatewayd /v1/control-word
route all agree; none can drift.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ENGINE = REPO / "scripts" / "hardware" / "control-word-service.py"


def _mod():
    spec = importlib.util.spec_from_file_location("_cws", ENGINE)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_engine_present():
    assert ENGINE.is_file(), f"missing {ENGINE}"


def test_fingerprint_parity_with_the_crate():
    m = _mod()
    assert m.lane_fingerprint(1, 2, 3) == 0xDA2BFB225E0D1F05
    s = {
        "state": [0x8, 0x10, 0x18, 0x20, 0x28, 0x30, 0x38, 0x40],
        "memory": [0x2000000000000000, 0, 0x2000000000000000, 0,
                   0x2000000000000000, 0, 0x2000000000000000, 1],
        "rule": [1, 2, 3, 4, 5, 6, 7, 8],
        "random": [0] * 8,
    }
    assert m.round_fingerprints(s) == [
        0x4FC1E349A99A8D6C, 0x0F7ADBF7D55AF597, 0xDD6A7F6A7EB95FFE, 0x66810795 << 32 | 0x55FE7DE1,
        0x3470AB07FF5CE848, 0xF429A3B62B1D5073, 0xC2194728D47BBADA, 0x91CD071E974D82EC,
    ]
    assert m.diversity_index(m.round_fingerprints(s)) == 1.0


def test_fingerprint_is_deterministic_and_sensitive():
    m = _mod()
    assert m.lane_fingerprint(1, 2, 3) == m.lane_fingerprint(1, 2, 3)
    assert m.lane_fingerprint(1, 2, 3) != m.lane_fingerprint(1, 2, 4)
    assert m.diversity_index([7] * 8) == 0.125  # all identical → 1/8


def test_quarantine_flags_drift():
    m = _mod()
    prev = [0] * 8
    cur = [0] * 8
    cur[3] = 0xFF  # 8 bits of drift on lane 3
    r = m.quarantine(prev, cur, 4)
    assert r["flagged"] == [3]
    assert r["drift_bits"][3] == 8
    assert m.quarantine(prev, cur, 64)["flagged"] == []
    assert m.quarantine(prev, cur, 0)["flagged"] == [3]


def test_prometheus_text_has_all_four_gauges():
    m = _mod()
    text = m.render_prometheus(m.metrics(1.0, 10000.0, 1.8))
    for name in [
        "sovereign_os_per_lane_dna_diversity_index",
        "sovereign_os_round_update_steps_per_sec",
        "sovereign_os_variable_shift_cost_ratio",
        "sovereign_os_zmm_layout_register_assignment",
    ]:
        assert f"# TYPE {name} gauge" in text, f"missing {name}"
    assert 'plane="state",register="zmm0"' in text
    assert 'plane="random",register="zmm3"' in text


def test_avx_mode_gate_matches_the_crate():
    m = _mod()
    # parse + default (mirror crate AvxMode::parse / avx-mode.py DEFAULT_MODE)
    assert m.avx_mode_parse("custom") == "custom"
    assert m.avx_mode_parse(" hybrid\n") == "hybrid"
    assert m.avx_mode_parse("nonsense") == "builtin"
    assert m.avx_mode_parse("") == "builtin"
    # the bit-machine is opt-in: only custom + hybrid run it
    assert m.runs_bit_machine("custom") is True
    assert m.runs_bit_machine("hybrid") is True
    assert m.runs_bit_machine("builtin") is False
    assert m.runs_bit_machine("off") is False


def test_cli_fingerprint_quarantine_metrics():
    import json

    def run(*a):
        return subprocess.run([sys.executable, str(ENGINE), *a],
                              capture_output=True, text=True, timeout=20)
    r = run("fingerprint", "--json")
    assert r.returncode == 0 and len(json.loads(r.stdout)["fingerprints"]) == 8
    r = run("quarantine", "--prev", "0,0,0,0,0,0,0,0",
            "--cur", "255,0,0,0,0,0,0,0", "--threshold", "4", "--json")
    assert r.returncode == 0 and json.loads(r.stdout)["flagged"] == [0]
    r = run("metrics", "--diversity", "1.0")
    assert r.returncode == 0 and "sovereign_os_zmm_layout_register_assignment" in r.stdout
