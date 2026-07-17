#!/usr/bin/env python3
"""scripts/hardware/control-word.py — the M00013 control-word engine (M002).

THIS IS THE REAL, TESTABLE BIT-MACHINE — no AVX-512 required. The parallelism
(evaluating 8 words per masked ZMM op) is future hardware work; the bit
SEMANTICS are just u64 shift-and-AND and run correctly scalar, today.

Canonical layout (M00013 / R00180 — non-negotiable):

    bits  0..3   mode          (4)   0..15
    bits  4..7   event         (4)   0..15
    bits  8..15  intensity     (8)   0..255
    bits 16..23  cooldown      (8)   0..255
    bits 24..31  neighborhood  (8)   0..255
    bits 32..47  paramA        (16)  0..65535
    bits 48..63  paramB        (16)  0..65535

Verbs:
  layout                  → the field schema (F00096)
  encode --mode N …       → pack fields → the u64 control word (M00025/M00027);
                            rejects any field over its range (R00189 overflow)
  decode <u64>            → unpack the u64 → the 8 typed fields (M00026/M00028)
  lut --rule-word W --condition C
                          → the M00017 64-entry boolean LUT: (W >> (C & 63)) & 1
                            — one branchless decision bit

Sovereignty: stdlib-only. Round-trip exact: decode(encode(x)) == x.
"""
from __future__ import annotations

import argparse
import json
import sys

# (name, shift, width) — canonical M00013 layout, R00180. Sums to exactly 64.
FIELDS: list[tuple[str, int, int]] = [
    ("mode", 0, 4),
    ("event", 4, 4),
    ("intensity", 8, 8),
    ("cooldown", 16, 8),
    ("neighborhood", 24, 8),
    ("paramA", 32, 16),
    ("paramB", 48, 16),
]
SCHEMA_VERSION = "1.0.0"


def layout() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "word_bits": 64,
        "fields": [
            {"name": n, "bits": f"{s}..{s + w}", "width": w, "max": (1 << w) - 1}
            for n, s, w in FIELDS
        ],
    }


def encode(values: dict[str, int]) -> int:
    """Pack fields → u64. Raises on overflow (a field value past its width)."""
    word = 0
    for name, shift, width in FIELDS:
        v = int(values.get(name, 0))
        hi = (1 << width) - 1
        if v < 0 or v > hi:
            raise ValueError(f"field {name!r} = {v} overflows its {width}-bit range (0..{hi})")
        word |= (v & hi) << shift
    return word


def decode(word: int) -> dict[str, int]:
    """Unpack u64 → the typed fields."""
    word &= (1 << 64) - 1
    return {name: (word >> shift) & ((1 << width) - 1) for name, shift, width in FIELDS}


def lut(rule_word: int, condition: int) -> int:
    """M00017: a 64-entry boolean rule table inside one u64. The decision for a
    6-bit condition is a single bit: (rule_word >> (condition & 63)) & 1."""
    return (int(rule_word) >> (int(condition) & 63)) & 1


def pack_u64(lanes: list[int]) -> int:
    """M00027/R00263 generic packer — 8 lanes, low byte each, lane i at bits i*8."""
    w = 0
    for i, v in enumerate(lanes[:8]):
        w |= (int(v) & 0xFF) << (i * 8)
    return w


def unpack_u64(word: int) -> list[int]:
    """M00028/R00264 — the inverse of pack_u64."""
    return [(int(word) >> (i * 8)) & 0xFF for i in range(8)]


def rule_decide(width: int, lo: int, hi: int, condition: int) -> int:
    """M00022-24 — the decision bit for a 32/64/128-bit rule word."""
    if width == 32:
        return (int(lo) >> (int(condition) & 31)) & 1
    if width == 64:
        return (int(lo) >> (int(condition) & 63)) & 1
    c = int(condition) & 127  # 128-bit: bit 6 selects limb, bits 0..5 the entry
    limb = lo if c < 64 else hi
    return (int(limb) >> (c & 63)) & 1


def encode_mode(values: dict[str, int], mode: str) -> int:
    """R00318-320 overflow policy: abort (default) / wrap / saturate."""
    word = 0
    for name, shift, width in FIELDS:
        v = int(values.get(name, 0))
        hi = (1 << width) - 1
        if mode == "abort":
            if v < 0 or v > hi:
                raise ValueError(f"field {name!r} = {v} overflows its {width}-bit range (0..{hi})")
        elif mode == "saturate":
            v = max(0, min(v, hi))
        else:  # wrap
            v &= hi
        word |= (v & hi) << shift
    return word


LAYOUT_VERSION_SEMVER = "1.0.0"

# The built-knob defaults — mirror crate m00013::ControlWordConfig::default().
CONFIG_DEFAULTS: dict[str, object] = {
    "layout_version": LAYOUT_VERSION_SEMVER,
    "overflow_mode": "abort",
    "rule_word_width": 64,
    "lut_condition_width": 6,
    "masked_op_mode": "branchless",
}


def resolve_config(get) -> dict[str, object]:
    """R00183/196/206/254 — resolve the control-word runtime config over the
    defaults using a getter (pure; parity with crate ControlWordConfig::resolve).
    Invalid values are ignored so the loader never fails."""
    c = dict(CONFIG_DEFAULTS)
    v = get("SOVEREIGN_CTRL_WORD_LAYOUT_VERSION")
    if v is not None:
        parts = v.split(".")
        if len(parts) == 3 and all(p.isdigit() for p in parts):
            c["layout_version"] = v
    v = get("SOVEREIGN_CTRL_OVERFLOW_MODE")
    if v in ("abort", "wrap", "saturate"):
        c["overflow_mode"] = v
    v = get("SOVEREIGN_CTRL_RULE_WORD_WIDTH")
    if v is not None and v.isdigit() and int(v) in (32, 64, 128):
        c["rule_word_width"] = int(v)
    v = get("SOVEREIGN_CTRL_LUT_CONDITION_WIDTH")
    if v is not None and v.isdigit() and int(v) in (5, 6, 7):
        c["lut_condition_width"] = int(v)
    v = get("SOVEREIGN_CTRL_MASKED_OP_MODE")
    if v in ("branchless", "branchy"):
        c["masked_op_mode"] = v
    return c


def config_from_env() -> dict[str, object]:
    import os

    return resolve_config(lambda k: os.environ.get(k))


def _fmt_word(word: int) -> str:
    return f"0x{word:016X}"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="M00013 control-word engine (M002)")
    sub = p.add_subparsers(dest="cmd")

    sp_layout = sub.add_parser("layout", help="print the field schema")
    sp_layout.add_argument("--json", action="store_true")

    sp_enc = sub.add_parser("encode", help="pack fields → the u64 control word")
    for name, _s, _w in FIELDS:
        sp_enc.add_argument(f"--{name}", type=int, default=0)
    sp_enc.add_argument("--overflow", choices=["abort", "wrap", "saturate"], default="abort",
                        help="R00318-320 overflow policy (default abort)")
    sp_enc.add_argument("--json", action="store_true")

    sp_dec = sub.add_parser("decode", help="unpack a u64 control word → fields")
    sp_dec.add_argument("word", help="the control word (0x… hex or decimal)")
    sp_dec.add_argument("--json", action="store_true")

    sp_lut = sub.add_parser("lut", help="M00017 64-entry LUT decision bit")
    sp_lut.add_argument("--rule-word", required=True, help="the 64-bit rule word (0x… or decimal)")
    sp_lut.add_argument("--condition", type=int, required=True, help="the 6-bit condition (0..63)")
    sp_lut.add_argument("--json", action="store_true")

    sp_pack = sub.add_parser("pack", help="M00027 generic pack — 8 lanes (low byte each) → u64")
    sp_pack.add_argument("--lanes", required=True, help="8 comma-separated values")
    sp_pack.add_argument("--json", action="store_true")

    sp_unpack = sub.add_parser("unpack", help="M00028 generic unpack — u64 → 8 lanes")
    sp_unpack.add_argument("word", help="the packed word (0x… or decimal)")
    sp_unpack.add_argument("--json", action="store_true")

    sp_rule = sub.add_parser("rule", help="M00022-24 rule-word decision (32/64/128-bit)")
    sp_rule.add_argument("--width", type=int, choices=[32, 64, 128], default=64)
    sp_rule.add_argument("--lo", required=True, help="rule word (32/64) or low limb (128)")
    sp_rule.add_argument("--hi", default="0", help="high limb (128-bit only)")
    sp_rule.add_argument("--condition", type=int, required=True)
    sp_rule.add_argument("--json", action="store_true")

    sp_cfg = sub.add_parser(
        "config", help="resolve the runtime config (SOVEREIGN_CTRL_* env → built knobs)")
    sp_cfg.add_argument("--json", action="store_true")

    args = p.parse_args(argv)
    cmd = args.cmd or "layout"

    def _int(s: str) -> int:
        return int(s, 16) if s.lower().startswith("0x") else int(s)

    if cmd == "layout":
        lay = layout()
        if getattr(args, "json", False):
            print(json.dumps(lay, indent=2))
        else:
            print(f"control word — {lay['word_bits']} bits (M00013, schema {lay['schema_version']})")
            for f in lay["fields"]:
                print(f"  bits {f['bits']:>7}  {f['name']:<13} width {f['width']:>2}  max {f['max']}")
        return 0

    if cmd == "encode":
        vals = {name: getattr(args, name) for name, _s, _w in FIELDS}
        try:
            word = encode_mode(vals, getattr(args, "overflow", "abort"))
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        rt = decode(word)  # prove the round-trip inline
        if getattr(args, "json", False):
            print(json.dumps({"word": word, "hex": _fmt_word(word), "fields": vals,
                              "roundtrip_ok": rt == vals}, indent=2))
        else:
            print(f"control word = {_fmt_word(word)}  ({word})")
            print("  " + "  ".join(f"{k}={v}" for k, v in vals.items()))
            print(f"  round-trip: decode → {'exact ✓' if rt == vals else 'MISMATCH ✗'}")
        return 0

    if cmd == "decode":
        word = _int(args.word)
        fields = decode(word)
        if getattr(args, "json", False):
            print(json.dumps({"word": word, "hex": _fmt_word(word), "fields": fields}, indent=2))
        else:
            print(f"{_fmt_word(word)}:")
            for name, _s, _w in FIELDS:
                print(f"  {name:<13} {fields[name]}")
        return 0

    if cmd == "lut":
        rw = _int(args.rule_word)
        bit = lut(rw, args.condition)
        if getattr(args, "json", False):
            print(json.dumps({"rule_word": rw, "hex": _fmt_word(rw),
                              "condition": args.condition, "decision": bit}, indent=2))
        else:
            print(f"lut({_fmt_word(rw)}, cond={args.condition}) = {bit}  "
                  f"(bit {args.condition & 63} of the rule word)")
        return 0

    if cmd == "pack":
        lanes = [int(x, 0) for x in args.lanes.split(",")]
        if len(lanes) != 8:
            print("error: --lanes needs exactly 8 comma-separated values", file=sys.stderr)
            return 2
        w = pack_u64(lanes)
        if getattr(args, "json", False):
            print(json.dumps({"lanes": lanes, "word": w, "hex": _fmt_word(w),
                              "roundtrip_ok": unpack_u64(w) == [x & 0xFF for x in lanes]}, indent=2))
        else:
            print(f"pack {lanes} = {_fmt_word(w)}  ({w})")
        return 0

    if cmd == "unpack":
        w = _int(args.word)
        lanes = unpack_u64(w)
        if getattr(args, "json", False):
            print(json.dumps({"word": w, "hex": _fmt_word(w), "lanes": lanes}, indent=2))
        else:
            print(f"{_fmt_word(w)} → lanes {lanes}")
        return 0

    if cmd == "rule":
        lo, hi = _int(args.lo), _int(args.hi)
        bit = rule_decide(args.width, lo, hi, args.condition)
        if getattr(args, "json", False):
            print(json.dumps({"width": args.width, "lo": lo, "hi": hi,
                              "condition": args.condition, "decision": bit}, indent=2))
        else:
            print(f"rule[{args.width}-bit].decide(cond={args.condition}) = {bit}")
        return 0

    if cmd == "config":
        cfg = config_from_env()
        if getattr(args, "json", False):
            print(json.dumps(cfg, indent=2))
        else:
            print("control-word runtime config (defaults + SOVEREIGN_CTRL_* env):")
            for k, v in cfg.items():
                env = "SOVEREIGN_CTRL_" + (
                    "WORD_LAYOUT_VERSION" if k == "layout_version" else k.upper())
                overridden = "" if v == CONFIG_DEFAULTS[k] else "  (overridden)"
                print(f"  {k:<20} {v}{overridden}   [{env}]")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
