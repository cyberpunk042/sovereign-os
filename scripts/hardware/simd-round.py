#!/usr/bin/env python3
"""scripts/hardware/simd-round.py — the M00019/M00020 round-update engine (M002).

The scalar mirror of crate `sovereign-simd::round` — the bit-machine actually
running. 8 lanes evolve in lock-step through the 5-step round (M00020) over the
strong ZMM layout (M00019): state / memory / rule / random. Pure u64 ops — the
AVX-512 kernel in the crate is proven bit-identical to THIS, and this file is
proven bit-identical to the crate scalar reference by the lint test. No AVX
needed to run it; the semantics are just shifts and XORs.

Steps, per lane (R00289-293):
  1 extract  features = (state ^ memory ^ random) & 0x3F        (M00016)
  2 decision (eff_rule >> features) & 1                          (M00014, R00290)
  3 apply    state  = (state << 1) | decision                   (R00291)
  4 memory   memory = (memory >> 1) | ((old_state & 1) << 63)   (R00292)
  5 advance  random = xorshift64(random)                        (R00293)

Knobs (opt-in): --masked-op branchless|branchy (M00014, identical output),
--per-lane-dna (M00018, eff_rule = rule ^ state → per-lane divergence).

Verbs: round / variable-shift / lane-fields. Sovereignty: stdlib-only.
"""
from __future__ import annotations

import argparse
import json
import sys

MASK64 = (1 << 64) - 1


def extract_features(state: int, memory: int, random: int) -> int:
    return (state ^ memory ^ random) & 0x3F


def decide(rule: int, features: int) -> int:
    # branchless and branchy are identical by construction (F00110).
    return (rule >> (features & 63)) & 1


def apply_state(state: int, decision: int) -> int:
    return ((state << 1) | (decision & 1)) & MASK64


def update_memory(memory: int, old_state: int) -> int:
    return ((memory >> 1) | ((old_state & 1) << 63)) & MASK64


def advance_rng(x: int) -> int:
    x &= MASK64
    x ^= (x << 13) & MASK64
    x ^= x >> 7
    x ^= (x << 17) & MASK64
    return x & MASK64


def round_update(s: dict[str, list[int]], per_lane_dna: bool = False) -> dict[str, list[int]]:
    """One round over all 8 lanes. `s` has state/memory/rule/random, 8 each."""
    out = {k: list(v) for k, v in s.items()}
    for i in range(8):
        eff_rule = (s["rule"][i] ^ s["state"][i]) if per_lane_dna else s["rule"][i]
        feats = extract_features(s["state"][i], s["memory"][i], s["random"][i])
        d = decide(eff_rule, feats)
        out["state"][i] = apply_state(s["state"][i], d)
        out["memory"][i] = update_memory(s["memory"][i], s["state"][i])
        out["random"][i] = advance_rng(s["random"][i])
    return out


def variable_shift_left(values: list[int], shifts: list[int]) -> list[int]:
    """M00021 — per-lane `values[i] << shifts[i]`; shift ≥ 64 → 0 (VPSLLVQ)."""
    return [((v << sh) & MASK64) if sh < 64 else 0 for v, sh in zip(values, shifts)]


# M00012 lane-fields — state_lo 0..16 / state_hi 16..32 / control 32..48 / scratch 48..64.
LANE_FIELDS = [("state_lo", 0), ("state_hi", 16), ("control", 32), ("scratch", 48)]


def lane_pack(f: dict[str, int]) -> int:
    w = 0
    for name, shift in LANE_FIELDS:
        v = int(f.get(name, 0))
        if v < 0 or v > 0xFFFF:
            raise ValueError(f"lane field {name!r} = {v} overflows its 16-bit range")
        w |= (v & 0xFFFF) << shift
    return w & MASK64


def lane_unpack(word: int) -> dict[str, int]:
    return {name: (int(word) >> shift) & 0xFFFF for name, shift in LANE_FIELDS}


# Round-config knobs (opt-in + hot-swap) — mirror crate RoundConfig::resolve.
# Only the two knobs this round kernel actually honors are exposed.
ROUND_CONFIG_DEFAULTS: dict[str, object] = {
    "masked_op": "branchless",
    "per_lane_dna": False,
}
_TRUE = ("1", "true", "yes", "on")
_FALSE = ("0", "false", "no", "off")


def resolve_round_config(get) -> dict[str, object]:
    c = dict(ROUND_CONFIG_DEFAULTS)
    v = get("SOVEREIGN_CTRL_MASKED_OP_MODE")
    if v in ("branchless", "branchy"):
        c["masked_op"] = v
    v = get("SOVEREIGN_CTRL_PER_LANE_DNA_ENABLED")
    if v in _TRUE:
        c["per_lane_dna"] = True
    elif v in _FALSE:
        c["per_lane_dna"] = False
    return c


def round_config_from_env() -> dict[str, object]:
    import os

    return resolve_round_config(lambda k: os.environ.get(k))


def _int(s: str) -> int:
    return int(s, 16) if s.lower().startswith("0x") else int(s)


def _parse8(s: str, label: str) -> list[int]:
    lanes = [_int(x) for x in s.split(",")]
    if len(lanes) != 8:
        raise ValueError(f"{label} needs exactly 8 comma-separated values")
    return lanes


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="M00019/M00020 round-update engine (M002)")
    sub = p.add_subparsers(dest="cmd")

    sp_r = sub.add_parser("round", help="run N rounds over the 8-lane strong layout")
    for plane in ("state", "memory", "rule", "random"):
        sp_r.add_argument(f"--{plane}", default="1,2,3,4,5,6,7,8",
                          help=f"8 comma-separated lane values for {plane}")
    sp_r.add_argument("--rounds", type=int, default=1)
    sp_r.add_argument("--masked-op", choices=["branchless", "branchy"], default="branchless")
    sp_r.add_argument("--per-lane-dna", action="store_true")
    sp_r.add_argument("--json", action="store_true")

    sp_v = sub.add_parser("variable-shift", help="M00021 per-lane VPSLLVQ")
    sp_v.add_argument("--values", required=True, help="8 comma-separated values")
    sp_v.add_argument("--shifts", required=True, help="8 comma-separated shift amounts")
    sp_v.add_argument("--json", action="store_true")

    sp_l = sub.add_parser("lane-fields", help="M00012 pack/unpack the 4 lane fields")
    sp_l.add_argument("--unpack", help="a u64 word to unpack")
    for name, _s in LANE_FIELDS:
        sp_l.add_argument(f"--{name}", type=int, default=0)
    sp_l.add_argument("--json", action="store_true")

    sp_c = sub.add_parser("config", help="resolve round knobs from SOVEREIGN_CTRL_* env")
    sp_c.add_argument("--json", action="store_true")

    args = p.parse_args(argv)
    cmd = args.cmd or "round"

    if cmd == "round":
        s = {plane: _parse8(getattr(args, plane), f"--{plane}")
             for plane in ("state", "memory", "rule", "random")}
        cur = s
        for _ in range(max(0, args.rounds)):
            cur = round_update(cur, per_lane_dna=args.per_lane_dna)
        if getattr(args, "json", False):
            print(json.dumps({"rounds": args.rounds, "per_lane_dna": args.per_lane_dna,
                              "masked_op": args.masked_op, "result": cur}, indent=2))
        else:
            print(f"after {args.rounds} round(s) (masked-op={args.masked_op}, "
                  f"per-lane-dna={args.per_lane_dna}):")
            for plane in ("state", "memory", "rule", "random"):
                print(f"  {plane:<7} " + " ".join(f"0x{v:016X}" for v in cur[plane]))
        return 0

    if cmd == "variable-shift":
        try:
            vals, shifts = _parse8(args.values, "--values"), _parse8(args.shifts, "--shifts")
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        out = variable_shift_left(vals, shifts)
        if getattr(args, "json", False):
            print(json.dumps({"values": vals, "shifts": shifts, "result": out}, indent=2))
        else:
            print("  " + " ".join(f"0x{v:016X}" for v in out))
        return 0

    if cmd == "lane-fields":
        if args.unpack is not None:
            f = lane_unpack(_int(args.unpack))
            if getattr(args, "json", False):
                print(json.dumps({"word": _int(args.unpack), "fields": f}, indent=2))
            else:
                for name, _s in LANE_FIELDS:
                    print(f"  {name:<9} {f[name]}")
            return 0
        vals = {name: getattr(args, name) for name, _s in LANE_FIELDS}
        try:
            w = lane_pack(vals)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        rt = lane_unpack(w)
        if getattr(args, "json", False):
            print(json.dumps({"fields": vals, "word": w, "hex": f"0x{w:016X}",
                              "roundtrip_ok": rt == vals}, indent=2))
        else:
            print(f"lane word = 0x{w:016X}  ({w})")
        return 0

    if cmd == "config":
        cfg = round_config_from_env()
        if getattr(args, "json", False):
            print(json.dumps(cfg, indent=2))
        else:
            print("round runtime config (defaults + SOVEREIGN_CTRL_* env):")
            envs = {"masked_op": "SOVEREIGN_CTRL_MASKED_OP_MODE",
                    "per_lane_dna": "SOVEREIGN_CTRL_PER_LANE_DNA_ENABLED"}
            for k, v in cfg.items():
                mark = "" if v == ROUND_CONFIG_DEFAULTS[k] else "  (overridden)"
                print(f"  {k:<14} {v}{mark}   [{envs[k]}]")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
