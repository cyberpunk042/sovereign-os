#!/usr/bin/env python3
"""scripts/hardware/avx512-advisor.py — R272 (E1.M14).

Operator-named (verbatim, 2026-05-17 mandate): "and the CPU and
AVX512".

R155+R164 ship Pulse algorithmic foundation (ternary + AVX-512
VPDPBUSD hot path). R272 closes E1.M14: per-feature probe of the
operator's AVX-512 EXTENSION set + workload-fit advisor that maps
detected extensions to the workloads they enable.

Probes (read-only):
  /proc/cpuinfo flags    AVX-512 feature flags (F, VL, BW, DQ, VNNI,
                         BF16, FP16, IFMA, VBMI, VBMI2, BITALG, ...)
  /sys/devices/system/cpu cpu count + per-core topology
  perf stat              best-effort actual VPDPBUSD instruction count
                         (operator-pull; needs CAP_PERFMON OR root)

Workload fit table — each workload requires a specific extension set:
  bitnet.cpp ternary    AVX-512-VNNI (VPDPBUSD INT8 fast path)
  bf16 inference        AVX-512-BF16 (VCVTNE2PS2BF16 + fused ops)
  fp16 mixed precision  AVX-512-FP16 (VFMADDxxx FP16 native)
  cipher / hash         AVX-512-VAES + AVX-512-VPCLMULQDQ
  conflict detection    AVX-512-CD (used by some sparse algorithms)
  vector permutations   AVX-512-VBMI / VBMI2 (string + bit-shuffle)
  PSI / sparse-matrix   AVX-512-IFMA (integer fused multiply-add)
  rotation / GF(2^n)    AVX-512-GFNI

CLI:
  avx512-advisor.py probe [--json]      raw feature flags + extension map
  avx512-advisor.py tiers [--json]      M085 three-tier note → flag/Zen5/host/engine
  avx512-advisor.py workloads [--json]  fit verdict per AI workload
  avx512-advisor.py advisory [--json]   actionable hints for missing extensions
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


# AVX-512 extension flags grouped by capability family.
AVX512_FLAGS = {
    "F":        "Foundation (mandatory floor)",
    "VL":       "Vector Length 128/256/512-bit",
    "BW":       "Byte + Word integer ops",
    "DQ":       "Doubleword + Quadword integer ops",
    "CD":       "Conflict Detection (sparse loops)",
    "VNNI":     "Vector Neural Network Instructions (INT8 dot-product)",
    "BF16":     "BFloat16 conversions + fused ops",
    "FP16":     "Half-precision native FMA",
    "IFMA":     "Integer Fused Multiply-Add (52-bit)",
    "VBMI":     "Vector Byte Manipulation",
    "VBMI2":   "Vector Byte Manipulation 2",
    "VP2INTERSECT": "Two-register token intersection (membership masks)",
    "BITALG":  "Bit Algorithms",
    "VPOPCNTDQ": "Population Count Doubleword/Quadword",
    "VAES":     "Vector AES (4× parallel AES rounds)",
    "VPCLMULQDQ": "Vector PCLMULQDQ (carry-less multiply)",
    "GFNI":     "Galois Field New Instructions (GF(2^8))",
}

# Map flag-name → /proc/cpuinfo flag string.
FLAG_LOWERCASE = {k: f"avx512{k.lower()}" if k != "F" else "avx512f" for k in AVX512_FLAGS}
# Special-case canonical mappings.
FLAG_LOWERCASE.update({
    "F": "avx512f",
    "VL": "avx512vl",
    "BW": "avx512bw",
    "DQ": "avx512dq",
    "CD": "avx512cd",
    "VNNI": "avx512_vnni",
    "BF16": "avx512_bf16",
    "FP16": "avx512_fp16",
    "IFMA": "avx512_ifma",
    "VBMI": "avx512_vbmi",
    "VBMI2": "avx512_vbmi2",
    "VP2INTERSECT": "avx512_vp2intersect",
    "BITALG": "avx512_bitalg",
    "VPOPCNTDQ": "avx512_vpopcntdq",
    # VAES / VPCLMULQDQ / GFNI are AVX-512-capable but are SEPARATE CPUID bits:
    # the kernel exposes them in /proc/cpuinfo WITHOUT the `avx512` prefix. The
    # computed default above ("avx512vaes" etc.) never matches, so without these
    # explicit entries the advisor reported them missing on a CPU (e.g. Zen5)
    # that actually has them.
    "VAES": "vaes",
    "VPCLMULQDQ": "vpclmulqdq",
    "GFNI": "gfni",
})


# The operator's AVX-512 three-tier note (2026-07-02, M085): each tier names a
# concrete instruction; this maps it → the sub-extension flag that provides it →
# whether Zen 5 (the SAIN-01 baseline) has that flag → its status in the Rust
# engine. VP2INTERSECT is the single exception: Intel shipped it once (Tiger
# Lake) then removed it and AMD never implemented it, so on Zen 5 the T2
# token-correlation op has NO hardware and can only ever run as a scalar
# fallback. `engine` values: "wired" = runs in the model path; "scalar-ref" =
# semantically-exact portable reference, not yet a SIMD/consumer path.
TIER_INSTRUCTIONS: list[dict[str, Any]] = [
    {"tier": "T1", "role": "Quantisation & Dot Product",
     "instruction": "VPDPBUSD", "operator_mnemonic": "VPDPBUSD", "flag": "VNNI",
     "engine": "wired", "note": "Precision::Int8 hot path (sovereign-vnni MatI8)"},
    {"tier": "T1", "role": "Quantisation & Dot Product",
     "instruction": "VDPBF16PS", "operator_mnemonic": "VPDOTBF16PLUS", "flag": "BF16",
     "engine": "wired", "note": "Precision::Bf16 (sovereign-vnni MatBf16)"},
    {"tier": "T2", "role": "Bitwise Logic & Attention",
     "instruction": "VPTERNLOGD/Q", "operator_mnemonic": "VPTERNLOGD/Q", "flag": "F",
     "engine": "scalar-ref", "note": "3-input LUT (sovereign-bitops::vpternlog)"},
    {"tier": "T2", "role": "Bitwise Logic & Attention",
     "instruction": "VP2INTERSECTD/Q", "operator_mnemonic": "VP2INTERSECTD/Q",
     "flag": "VP2INTERSECT", "engine": "scalar-ref",
     "note": "no Zen 5 hardware — scalar only (sovereign-bitops::intersect)"},
    {"tier": "T3", "role": "Structure, Prune & KV-Cache",
     "instruction": "VPERMB", "operator_mnemonic": "VPERMB", "flag": "VBMI",
     "engine": "scalar-ref", "note": "64-byte permute (sovereign-bitops::vpermb)"},
    {"tier": "T3", "role": "Structure, Prune & KV-Cache",
     "instruction": "VPSHLDVQ", "operator_mnemonic": "VPSHLDV", "flag": "VBMI2",
     "engine": "scalar-ref", "note": "funnel shift (sovereign-bitops::vpshldv)"},
    {"tier": "T3", "role": "Structure, Prune & KV-Cache",
     "instruction": "VPCOMPRESSB/VPEXPANDB", "operator_mnemonic": "VPCOMPRESSB/VPEXPANDB",
     "flag": "VBMI2", "engine": "scalar-ref",
     "note": "compact/expand live slots (sovereign-bitops::compress/expand)"},
    {"tier": "margin", "role": "Pop count (ternary/mask)",
     "instruction": "VPOPCNTD/Q", "operator_mnemonic": "VPOPCNT", "flag": "VPOPCNTDQ",
     "engine": "scalar-ref", "note": "dword/qword popcount (sovereign-bitops::popcount)"},
    {"tier": "margin", "role": "Pop count (ternary/mask)",
     "instruction": "VPOPCNTB/W", "operator_mnemonic": "VPOPCNT", "flag": "BITALG",
     "engine": "scalar-ref", "note": "byte/word popcount — ternary masks"},
]

# Zen 5 (znver5, SAIN-01 baseline) presence per note-relevant flag. Every flag
# the note uses is native on Zen 5 EXCEPT VP2INTERSECT (see above).
ZEN5_ABSENT_FLAGS = {"VP2INTERSECT"}


# Workload fit table: workload → required flags.
WORKLOAD_FIT: dict[str, dict[str, Any]] = {
    "bitnet-ternary-inference": {
        "required": ["F", "VL", "BW", "VNNI"],
        "summary": "BitNet 1.58-bit ternary inference (VPDPBUSD INT8 dot-product hot path).",
        "operator_note": "Primary engine for SAIN-01 Pulse tier (master spec §17.1).",
    },
    "bf16-inference": {
        "required": ["F", "VL", "BW", "BF16"],
        "summary": "BFloat16 inference at native AVX-512 throughput.",
        "operator_note": "vLLM + transformers prefer BF16 when BF16 extension present.",
    },
    "fp16-mixed-precision": {
        "required": ["F", "VL", "BW", "FP16"],
        "summary": "FP16 native AVX-512 FMA (no upcast to FP32 mid-FMA).",
        "operator_note": "Half-precision training without the FP16-to-FP32 conversion tax.",
    },
    "sparse-attention": {
        "required": ["F", "VL", "BW", "CD"],
        "summary": "Sparse-matrix kernels with VPCONFLICT-based dedup.",
        "operator_note": "Long-context attention sparsification (FlashAttention 3+).",
    },
    "string-tokenization": {
        "required": ["F", "VL", "BW", "VBMI", "VBMI2"],
        "summary": "Byte-permute tokenization (BPE merge tables, SIMD JSON).",
        "operator_note": "Reduces tokenizer wall-time during dataset loading.",
    },
    "ifma-sparse-matmul": {
        "required": ["F", "VL", "IFMA"],
        "summary": "Integer fused multiply-add for 52-bit precision matmul.",
        "operator_note": "Used by some embedding pipelines + cryptographic libraries.",
    },
    "aes-disk-encryption": {
        "required": ["F", "VL", "VAES"],
        "summary": "4-parallel AES rounds for full-disk + at-rest encryption.",
        "operator_note": "Speeds LUKS/ZFS-native-encryption ~3× on AVX-512 hosts.",
    },
    "ghash-tls13-throughput": {
        "required": ["F", "VL", "VPCLMULQDQ"],
        "summary": "AES-GCM GHASH at 4× width — TLS 1.3 high-throughput servers.",
        "operator_note": "Cloudflared / Traefik TLS termination benefits.",
    },
    "gfni-rotation": {
        "required": ["F", "VL", "GFNI"],
        "summary": "Galois-field rotations for hash + erasure-coding kernels.",
        "operator_note": "Some Reed-Solomon RAID parity implementations use this.",
    },
    "token-intersect-attention": {
        "required": ["F", "VL", "VP2INTERSECT"],
        "summary": "One-op token-set intersection for attention (T2, M085).",
        "operator_note": "NO Zen 5 hardware — VP2INTERSECT is Intel-Tiger-Lake-only "
                         "and removed; sovereign-os runs the scalar fallback.",
    },
    "kv-cache-compaction": {
        "required": ["F", "VL", "BW", "VBMI2"],
        "summary": "Compact/expand live KV-cache + token slots (T3, M085).",
        "operator_note": "VPCOMPRESSB/VPEXPANDB + VPSHLDV structure ops; Zen 5 native.",
    },
}


def read_proc_cpuinfo_flags() -> list[str]:
    p = Path("/proc/cpuinfo")
    if not p.exists():
        return []
    try:
        text = p.read_text()
    except OSError:
        return []
    for line in text.splitlines():
        if line.startswith("flags") and ":" in line:
            return line.split(":", 1)[1].strip().split()
    return []


def read_cpu_model() -> str | None:
    p = Path("/proc/cpuinfo")
    if not p.exists():
        return None
    try:
        for line in p.read_text().splitlines():
            if line.startswith("model name") and ":" in line:
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return None


def detect_avx512_extensions() -> dict[str, bool]:
    """Returns {flag_key: present} for every flag in AVX512_FLAGS."""
    cpu_flags = set(read_proc_cpuinfo_flags())
    return {key: (FLAG_LOWERCASE[key] in cpu_flags) for key in AVX512_FLAGS}


def cmd_probe(args: argparse.Namespace) -> int:
    ext = detect_avx512_extensions()
    model = read_cpu_model()
    avx512_supported = ext.get("F", False)
    present_count = sum(1 for v in ext.values() if v)
    total_count = len(ext)
    extensions = [
        {
            "flag": key,
            "cpuinfo_flag": FLAG_LOWERCASE[key],
            "present": ext[key],
            "summary": AVX512_FLAGS[key],
        }
        for key in AVX512_FLAGS
    ]
    out = {
        "round": "R272",
        "vector": "E1.M14 (avx512-probe)",
        "cpu_model": model,
        "avx512_supported": avx512_supported,
        "extensions": extensions,
        "extension_counts": {
            "present": present_count,
            "total": total_count,
        },
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"── R272 sovereign-os avx512-advisor probe (E1.M14) ──")
    print(f"  cpu_model:        {model or '(unknown)'}")
    print(f"  avx512 supported: {avx512_supported}  ({present_count}/{total_count} extensions present)")
    print()
    for e in extensions:
        mark = "✓" if e["present"] else "·"
        print(f"  {mark} {e['flag']:<10}  ({e['cpuinfo_flag']:<22})  {e['summary']}")
    return 0


def cmd_workloads(args: argparse.Namespace) -> int:
    ext = detect_avx512_extensions()
    rows: list[dict[str, Any]] = []
    fit_count = 0
    for name, spec in WORKLOAD_FIT.items():
        missing = [f for f in spec["required"] if not ext.get(f, False)]
        fits = not missing
        if fits:
            fit_count += 1
        rows.append({
            "workload": name,
            "required_flags": spec["required"],
            "missing_flags": missing,
            "fits": fits,
            "summary": spec["summary"],
            "operator_note": spec["operator_note"],
        })
    out = {
        "round": "R272",
        "vector": "E1.M14 (avx512-workloads)",
        "workload_count": len(rows),
        "fitting_workload_count": fit_count,
        "workloads": rows,
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"── R272 sovereign-os avx512-advisor workloads (E1.M14) ──")
    print(f"  {fit_count}/{len(rows)} workloads have ALL required extensions present.")
    print()
    for r in rows:
        glyph = "✓" if r["fits"] else "·"
        print(f"  {glyph} {r['workload']:<26} {r['summary']}")
        if r["missing_flags"]:
            print(f"      missing: {', '.join(r['missing_flags'])}")
    return 0


def cmd_tiers(args: argparse.Namespace) -> int:
    """The M085 three-tier AVX-512 note → per-instruction flag, Zen-5 verdict,
    detected-on-this-host verdict, and engine status."""
    ext = detect_avx512_extensions()
    rows: list[dict[str, Any]] = []
    for i in TIER_INSTRUCTIONS:
        flag = i["flag"]
        rows.append({
            **i,
            "cpuinfo_flag": FLAG_LOWERCASE[flag],
            "zen5": flag not in ZEN5_ABSENT_FLAGS,
            "present_on_host": ext.get(flag, False),
        })
    out = {
        "round": "M085",
        "vector": "avx512-tiers (three-tier instruction exploitation)",
        "tiers": rows,
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print("── sovereign-os avx512-advisor tiers (M085 three-tier note) ──")
    print(f"  {'tier':<6} {'instruction':<22} {'flag':<20} zen5 host engine")
    for r in rows:
        z = "✓" if r["zen5"] else "✗"
        h = "✓" if r["present_on_host"] else "·"
        print(f"  {r['tier']:<6} {r['instruction']:<22} {r['cpuinfo_flag']:<20}  {z}    {h}   {r['engine']}")
    print("\n  ✗ zen5 = no hardware for that op on the SAIN-01 baseline "
          "(VP2INTERSECT: Intel-only + removed) → scalar fallback only.")
    return 0


def cmd_advisory(args: argparse.Namespace) -> int:
    ext = detect_avx512_extensions()
    advisories: list[str] = []
    severity = "ok"
    if not ext.get("F", False):
        severity = "attention"
        advisories.append(
            "Host CPU LACKS AVX-512 entirely. Pulse tier (bitnet.cpp / "
            "VPDPBUSD INT8 fast path) WILL NOT WORK. Master spec §17.1 "
            "requires AVX-512-VNNI minimum — operator must use a CPU "
            "with avx512f + avx512_vnni (Zen 5 / Sapphire Rapids / Ice "
            "Lake-SP+) for the Pulse tier to function."
        )
    else:
        # Identify operator-relevant missing extensions.
        if not ext.get("VNNI", False):
            severity = "attention"
            advisories.append(
                "AVX-512 present but VNNI missing — bitnet.cpp ternary "
                "inference falls back to slower VPMADDWD path (≈3-5× "
                "slower than VPDPBUSD)."
            )
        if not ext.get("BF16", False):
            advisories.append(
                "AVX-512-BF16 missing — BF16 inference upcast to FP32 "
                "mid-FMA (≈40% slower). Use FP16 path if FP16 extension "
                "present, else INT8."
            )
        if not ext.get("FP16", False):
            advisories.append(
                "AVX-512-FP16 missing — FP16 mixed-precision training "
                "incurs FP16↔FP32 conversion tax. Either accept it or "
                "use BF16 (if BF16 extension is present)."
            )
        # SAIN-01-specific: Zen 5 has ALL of these. Surface a positive ack.
        zen5_set = ["F", "VL", "BW", "DQ", "VNNI", "BF16", "FP16"]
        if all(ext.get(f, False) for f in zen5_set):
            advisories.append(
                "Operator's SAIN-01 Zen 5 baseline detected: every "
                "AI-relevant AVX-512 extension is present. Pulse / Logic / "
                "Oracle tiers all fit at native AVX-512 throughput."
            )
            if severity == "ok":
                severity = "informational"
    out = {
        "round": "R272",
        "vector": "E1.M14 (avx512-advisory)",
        "severity": severity,
        "advisories": advisories,
        "avx512_supported": ext.get("F", False),
    }
    rc = 1 if severity == "attention" else 0
    if args.json:
        print(json.dumps(out, indent=2))
        return rc
    print(f"── R272 sovereign-os avx512-advisor advisory (E1.M14) ──")
    print(f"  severity: {severity}")
    if not advisories:
        print("  (no advisories — host AVX-512 posture is uncontroversial)")
        return rc
    for a in advisories:
        print(f"\n  • {a}")
    return rc


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="avx512-advisor.py",
        description="R272 (E1.M14) — AVX-512 extension probe + workload-fit advisor.",
    )
    sub = p.add_subparsers(dest="verb", required=True)
    for name, fn, helptxt in [
        ("probe", cmd_probe, "raw extension flag map"),
        ("tiers", cmd_tiers, "M085 three-tier note → flag/Zen5/host/engine"),
        ("workloads", cmd_workloads, "per-workload fit verdict"),
        ("advisory", cmd_advisory, "operator-actionable hints"),
    ]:
        sp = sub.add_parser(name, help=helptxt)
        sp.add_argument("--json", action="store_true")
        sp.set_defaults(func=fn)
    return p


def main(argv: list[str]) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
