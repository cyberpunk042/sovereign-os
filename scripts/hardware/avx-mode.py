#!/usr/bin/env python3
"""scripts/hardware/avx-mode.py — the AVX execution-mode hotswap (SDD-600 Part 3).

Operator directive 2026-07-16 (verbatim): *"is thre a mode … where we use the AVX
bits … Custom-AVX vs BuiltIn-Features-AVX vs Hybrid-AVX ? … If there is more mode
you put them all in a select."*

Two very different ways the box uses AVX-512, and this switch picks which is in
play:

  * **custom**  — the sovereign bit-machine (M002 control-word + M007 branch
    scheduler + M008 bit-level-cheats): "policy becomes bits". A packed control
    word per branch carries route/precision/permissions/grammar/priority, and one
    AVX-512 masked op routes many branches at once — token-by-token routing at
    hardware speed. This is the "using the bits for various purposes" superpower.
  * **builtin** — stock AVX-512 math acceleration (sovereign-simd / vnni / bitops
    + cpu-dispatch tiers + the M085/M086 precision tiers). Straight SIMD dot
    products, VNNI INT8, BF16 — no policy-in-bits, just faster math.
  * **hybrid**  — both: the bit-machine routes, the math tiers compute.
  * **off**     — scalar baseline; no AVX (portable path, any x86-64).

HONESTY (do-not-minimize, refreshed 2026-07-20 — the crates landed since the
original scaffold note): the bit-machine kernels are REAL today —
`sovereign-control-word` carries the M00013 layout + M00104 branch
permissions, `sovereign-simd::round` is the AVX-512 round kernel
(bit-identical to scalar), `sovereign-bit-cheats` / `sovereign-branch-tree` /
`sovereign-branch-scheduler` / `sovereign-control-word-service` all exist and
are consumed (gatewayd, cortex, coat). What remains downstream is the
PER-TOKEN INFERENCE integration — selecting `custom`/`hybrid` records the
mode and gates the `/v1/control-word/round` route; it does not yet steer
token-by-token routing inside the LM serving path. The compat layer gates
this switch too: C008/C011 relate avx-mode to inference-tier pulse and the
ultra-sovereign-efficiency profile, and `sovereign-osctl avx-mode set` runs
the compat precheck before executing (see docs/src/avx-mode-bit-machine.md
§ Compatibility).

Sovereignty: stdlib-only. SOVEREIGN_OS_AVX_MODE_DRYRUN=1 prints the plan.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# The master modes — surfaced in the panel's <select> (operator: "put them all
# in a select"). `built` state today: real = shipped kernels, scaffold = spec.
MASTER_MODES: dict[str, dict[str, object]] = {
    "custom": {
        "label": "Custom-AVX (bit-machine)",
        "summary": "M002 control-word + M007 branch scheduler + M008 bit-cheats — policy becomes bits. "
                   "Kernels real + live-verified; per-token inference integration is downstream.",
        "built": "real",
        "anchors": ["M002", "M007", "M008", "M061"],
    },
    "builtin": {
        "label": "BuiltIn-Features-AVX",
        "summary": "Stock AVX-512 math — sovereign-simd/vnni/bitops, cpu-dispatch tiers, M085/M086.",
        "built": "real",
        "anchors": ["M085", "M086", "sovereign-simd", "sovereign-vnni"],
    },
    "hybrid": {
        "label": "Hybrid-AVX",
        "summary": "Both — the bit-machine routes, the math tiers compute. "
                   "Kernels real + live-verified; per-token inference integration is downstream.",
        "built": "real",
        "anchors": ["M002", "M007", "M008", "M085"],
    },
    "off": {
        "label": "Off (scalar baseline)",
        "summary": "No AVX — the portable scalar path (cpu-dispatch ScalarBaseline), any x86-64.",
        "built": "real",
        "anchors": ["sovereign-cpu-dispatch"],
    },
}

# The full mode inventory the panel lists under the master select (the "various
# purposes" the bits are used for). Custom sub-modes = the M008 13 bit-cheats;
# builtin = the cpu-dispatch paths + the precision tiers.
CUSTOM_SUBMODES = [
    ("bitfields-microcode", "64-bit control word as executable policy (M00113)"),
    ("vpternlog-fused-policy", "VPTERNLOG fuses model-wants + policy-allows + oracle-verified into one mask (M00114)"),
    ("kmask-routing", "k-mask registers k1..k7 as decision/routing planes (M00115)"),
    ("vpcompress-pack", "VPCOMPRESS packs alive branches into dense GPU batches (M00116)"),
    ("token-law-bitset", "grammar/tool/safety/schema/route packed as a token bitset (M00117)"),
    ("inline-lut", "decision = (rule_word >> condition) & 1 — a LUT inside 64 bits (M00118)"),
    ("two-level-rule-table", "rule_id -> cached table[rule_id][event_class] (M00119)"),
    ("speculative-commit", "accept = oracle & grammar & tool & budget & memory (M00120)"),
    ("branch-prediction", "predictor / retirement / reorder-commit analogy (M00121)"),
    ("bloom-sketch", "popcount(query & memory) overlap sketches (M00122)"),
    ("simd-fsm", "8 branches through a finite-state machine at once (M00123)"),
    ("token-class-mini-lut", "token-class mini lookup table (M00124)"),
    ("filter-cascade", "cheapest-first filter cascade ordering (M00125)"),
]
BUILTIN_DISPATCH = [
    ("scalar-baseline", "portable x86-64 (cpu-dispatch ScalarBaseline)"),
    ("avx2", "AVX2 path"),
    ("avx512-generic", "generic AVX-512"),
    ("zen5-avx512", "Zen5-tuned AVX-512 (-march=znver5)"),
]
BUILTIN_TIERS = [
    ("t1-quant-dot", "T1 quantization & dot product (VPDPBUSD INT8 / VDPBF16PS BF16)"),
    ("t2-bitwise-attn", "T2 bitwise logic & attention masking (VPTERNLOG / VP2INTERSECT)"),
    ("t3-structure-kv", "T3 structure / prune / KV (VPCOMPRESS / VPEXPAND / VPERMB)"),
]

DRYRUN = os.environ.get("SOVEREIGN_OS_AVX_MODE_DRYRUN") == "1"
STATE_FILE = Path(os.environ.get(
    "SOVEREIGN_OS_AVX_MODE_STATE", "/etc/sovereign-os/avx-mode.active"))
DEFAULT_MODE = "builtin"  # default: straight math needs no opt-in; the bit-machine
                          # (custom/hybrid) is real but opt-in — runs_bit_machine()
                          # stays false until the operator chooses it


def _active() -> str:
    try:
        if STATE_FILE.is_file():
            v = STATE_FILE.read_text(encoding="utf-8").strip()
            if v in MASTER_MODES:
                return v
    except OSError:
        pass
    return DEFAULT_MODE


def _write(mode: str) -> list[str]:
    notes: list[str] = []
    if DRYRUN:
        notes.append(f"[dry-run] would write {STATE_FILE}")
        return notes
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(mode + "\n", encoding="utf-8")
    except OSError as e:
        notes.append(f"warning: could not persist mode ({e})")
    return notes


def inventory() -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "active": _active(),
        "master_modes": [{"id": k, **v} for k, v in MASTER_MODES.items()],
        "custom_submodes": [{"id": i, "desc": d} for i, d in CUSTOM_SUBMODES],
        "builtin_dispatch": [{"id": i, "desc": d} for i, d in BUILTIN_DISPATCH],
        "builtin_tiers": [{"id": i, "desc": d} for i, d in BUILTIN_TIERS],
    }


def set_mode(mode: str) -> dict[str, object]:
    if mode not in MASTER_MODES:
        return {"ok": False, "error": f"unknown mode {mode!r} (valid: {', '.join(MASTER_MODES)})"}
    notes = _write(mode)
    if MASTER_MODES[mode]["built"] == "scaffold":
        # No mode is scaffold today (all four are real + live-verified); the
        # branch stays so a future scaffold-tier mode degrades honestly.
        notes.append(
            "this mode's kernels are SCAFFOLD today — the mode is recorded; "
            "what it gates lands downstream.")
    return {"ok": True, "mode": mode, "dryrun": DRYRUN, "notes": notes}


def status() -> dict[str, object]:
    a = _active()
    return {"active": a, "built": MASTER_MODES[a]["built"],
            "label": MASTER_MODES[a]["label"], "state_file": str(STATE_FILE)}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="AVX execution-mode hotswap (SDD-600 Part 3)")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("list", help="list the master modes")
    sp_show = sub.add_parser("show", help="print the active mode")
    sp_show.add_argument("--json", action="store_true")
    sp_inv = sub.add_parser("inventory", help="print the full mode inventory")
    sp_inv.add_argument("--json", action="store_true")
    sp_set = sub.add_parser("set", help="set the AVX mode")
    sp_set.add_argument("mode", choices=list(MASTER_MODES))
    args = p.parse_args(argv)
    cmd = args.cmd or "show"

    if cmd == "list":
        for k, v in MASTER_MODES.items():
            flag = "" if v["built"] == "real" else "  (scaffold)"
            print(f"{k:8s} {v['label']}{flag}")
            print(f"         {v['summary']}")
        return 0
    if cmd == "inventory":
        inv = inventory()
        if getattr(args, "json", False):
            print(json.dumps(inv, indent=2))
        else:
            print(f"active: {inv['active']}")
            print(f"master modes: {', '.join(m['id'] for m in inv['master_modes'])}")
            print(f"custom sub-modes: {len(inv['custom_submodes'])} · "
                  f"builtin dispatch: {len(inv['builtin_dispatch'])} · tiers: {len(inv['builtin_tiers'])}")
        return 0
    if cmd == "set":
        r = set_mode(args.mode)
        if r.get("ok"):
            print(f"avx-mode → {r['mode']}" + (" (dry-run)" if DRYRUN else ""))
            for n in r.get("notes", []):
                print(f"  · {n}")
            return 0
        print(f"error: {r.get('error')}", file=sys.stderr)
        return 2
    # show
    s = status()
    if getattr(args, "json", False):
        print(json.dumps(s, indent=2))
    else:
        print(f"avx-mode: {s['active']} ({s['label']})")
        print(f"  built: {s['built']}")
        print(f"  set: sovereign-osctl avx-mode set {{custom|builtin|hybrid|off}}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
