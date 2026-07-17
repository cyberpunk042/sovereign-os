#!/usr/bin/env python3
"""scripts/hardware/control-word-service.py — the M002 service layer engine.

The scalar mirror of crate `sovereign-control-word-service`: per-lane DNA
fingerprints, diversity index, quarantine on drift, and the Prometheus metrics
text. Dependency-free FNV-1a (matching the crate + sovereign-replay-ledger
precedent — R00280 names blake3; the repo's stance is dependency-free
tamper-evidence). Pinned to the SAME fingerprint parity constant the crate
pins, so crate + CLI agree — neither can drift.

Verbs: fingerprint / diversity / quarantine / metrics. Stdlib-only.
"""
from __future__ import annotations

import argparse
import json
import sys

MASK64 = (1 << 64) - 1
FNV_OFFSET = 0xCBF29CE484222325
FNV_PRIME = 0x00000100000001B3


def fnv1a(data: bytes) -> int:
    h = FNV_OFFSET
    for b in data:
        h ^= b
        h = (h * FNV_PRIME) & MASK64
    return h


def lane_fingerprint(control_word: int, rule_word: int, state: int) -> int:
    """R00280 — hash(control_word ‖ rule_word ‖ state), FNV-1a, LE bytes."""
    buf = ((control_word & MASK64).to_bytes(8, "little")
           + (rule_word & MASK64).to_bytes(8, "little")
           + (state & MASK64).to_bytes(8, "little"))
    return fnv1a(buf)


def round_fingerprints(s: dict[str, list[int]]) -> list[int]:
    """Per-lane fingerprint: memory (control context) ‖ rule ‖ state."""
    return [lane_fingerprint(s["memory"][i], s["rule"][i], s["state"][i]) for i in range(8)]


def diversity_index(fps: list[int]) -> float:
    """F00129 — fraction of lanes with a distinct fingerprint (0.125..1.0)."""
    return len(set(fps)) / 8.0


def quarantine(prev: list[int], cur: list[int], threshold_bits: int) -> dict:
    """R00282 — flag lanes whose fingerprint drifted past threshold_bits."""
    drift = [bin((prev[i] ^ cur[i]) & MASK64).count("1") for i in range(8)]
    flagged = [i for i in range(8) if drift[i] > threshold_bits]
    return {"flagged": flagged, "drift_bits": drift, "threshold_bits": threshold_bits}


ZMM_ASSIGNMENT = [("state", "zmm0"), ("memory", "zmm1"), ("rule", "zmm2"), ("random", "zmm3")]


def metrics(dna_diversity_index: float, round_update_steps_per_sec: float,
            variable_shift_cost_ratio: float) -> dict:
    return {
        "dna_diversity_index": dna_diversity_index,
        "round_update_steps_per_sec": round_update_steps_per_sec,
        "variable_shift_cost_ratio": variable_shift_cost_ratio,
    }


def _fmt(v: float) -> str:
    return repr(v) if v == v and v not in (float("inf"), float("-inf")) else "0"


def render_prometheus(m: dict) -> str:
    """Hand-rolled Prometheus text exposition — mirrors Metrics::render_prometheus."""
    out = []
    out.append("# HELP sovereign_os_per_lane_dna_diversity_index Fraction of lanes with a distinct DNA fingerprint.")
    out.append("# TYPE sovereign_os_per_lane_dna_diversity_index gauge")
    out.append(f"sovereign_os_per_lane_dna_diversity_index {_fmt(m['dna_diversity_index'])}")
    out.append("# HELP sovereign_os_round_update_steps_per_sec Round-update steps executed per second.")
    out.append("# TYPE sovereign_os_round_update_steps_per_sec gauge")
    out.append(f"sovereign_os_round_update_steps_per_sec {_fmt(m['round_update_steps_per_sec'])}")
    out.append("# HELP sovereign_os_variable_shift_cost_ratio Variable-shift cost vs the AND/XOR baseline.")
    out.append("# TYPE sovereign_os_variable_shift_cost_ratio gauge")
    out.append(f"sovereign_os_variable_shift_cost_ratio {_fmt(m['variable_shift_cost_ratio'])}")
    out.append("# HELP sovereign_os_zmm_layout_register_assignment Strong-layout plane→ZMM register assignment (info).")
    out.append("# TYPE sovereign_os_zmm_layout_register_assignment gauge")
    for plane, reg in ZMM_ASSIGNMENT:
        out.append(f'sovereign_os_zmm_layout_register_assignment{{plane="{plane}",register="{reg}"}} 1')
    return "\n".join(out) + "\n"


# avx-mode gate — mirrors crate AvxMode (custom/builtin/hybrid/off, default
# builtin). The M002 bit-machine runs only under custom/hybrid (opt-in).
AVX_MODES = ("custom", "builtin", "hybrid", "off")


def avx_mode_parse(s: str) -> str:
    """Parse an avx-mode string; unknown → the honest default 'builtin'."""
    v = (s or "").strip()
    return v if v in AVX_MODES else "builtin"


def runs_bit_machine(mode: str) -> bool:
    """Whether the M00013 bit-machine is the active path (custom/hybrid only)."""
    return mode in ("custom", "hybrid")


def _int(s: str) -> int:
    return int(s, 16) if s.lower().startswith("0x") else int(s)


def _parse8(s: str, label: str) -> list[int]:
    lanes = [_int(x) for x in s.split(",")]
    if len(lanes) != 8:
        raise ValueError(f"{label} needs exactly 8 comma-separated values")
    return lanes


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="M002 control-word service engine")
    sub = p.add_subparsers(dest="cmd")

    sp_f = sub.add_parser("fingerprint", help="per-lane DNA fingerprints of a round state")
    for plane in ("state", "memory", "rule", "random"):
        sp_f.add_argument(f"--{plane}", default="1,2,3,4,5,6,7,8")
    sp_f.add_argument("--json", action="store_true")

    sp_q = sub.add_parser("quarantine", help="R00282 flag lanes drifting past a threshold")
    sp_q.add_argument("--prev", required=True, help="8 previous fingerprints")
    sp_q.add_argument("--cur", required=True, help="8 current fingerprints")
    sp_q.add_argument("--threshold", type=int, default=8)
    sp_q.add_argument("--json", action="store_true")

    sp_m = sub.add_parser("metrics", help="Prometheus text for the service gauges")
    sp_m.add_argument("--diversity", type=float, default=1.0)
    sp_m.add_argument("--steps-per-sec", type=float, default=0.0)
    sp_m.add_argument("--variable-shift-cost", type=float, default=1.0)

    args = p.parse_args(argv)
    cmd = args.cmd or "fingerprint"

    if cmd == "fingerprint":
        s = {plane: _parse8(getattr(args, plane), f"--{plane}")
             for plane in ("state", "memory", "rule", "random")}
        fps = round_fingerprints(s)
        div = diversity_index(fps)
        if getattr(args, "json", False):
            print(json.dumps({"fingerprints": fps, "diversity_index": div}, indent=2))
        else:
            for i, f in enumerate(fps):
                print(f"  lane {i}: 0x{f:016X}")
            print(f"  diversity index: {div}")
        return 0

    if cmd == "quarantine":
        try:
            prev, cur = _parse8(args.prev, "--prev"), _parse8(args.cur, "--cur")
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        rep = quarantine(prev, cur, args.threshold)
        if getattr(args, "json", False):
            print(json.dumps(rep, indent=2))
        else:
            print(f"flagged lanes (drift > {args.threshold} bits): {rep['flagged']}")
            print(f"drift bits: {rep['drift_bits']}")
        return 0

    if cmd == "metrics":
        m = metrics(args.diversity, args.steps_per_sec, args.variable_shift_cost)
        print(render_prometheus(m), end="")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
