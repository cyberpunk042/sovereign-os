#!/usr/bin/env python3
"""scripts/build/cpu-features.py — SDD-043 Phase 1: profile CPU features → build flags.

The connective tissue that makes `hardware.cpu.features` in a profile
ACTUALLY drive the userspace Rust build. Emits the RUSTFLAGS
(`-C target-cpu=... -C target-feature=+...`) that compile the inference
crates (sovereign-vnni, sovereign-bitops, sovereign-bitlinear-core,
sovereign-attention, sovereign-quant-*) for exactly the ISA the declared
hardware has — VNNI (VPDPBUSD), BF16 (VDPBF16PS), popcount, and the rest.

WHY USERSPACE ONLY (resolves SDD-043 Q-1): the KERNEL build deliberately
DISABLES vector ISA (`-mno-avx512f …` in the profile's KCFLAGS) because
kernel code cannot touch vector registers at early boot (XCR0 unset →
#UD; the 2026-06-10 SIGILL). Feature exploitation is a USERSPACE concern
— so this emits a RUSTFLAGS overlay for the crate build, NOT a kernel
recompile. Kernel opts out; userspace opts in. That is the whole point.

Usage:
  cpu-features.py [--profile <path>] [--format rustflags|env|list|cargo]
    --profile   profile YAML (default: active profile → sain-01)
    --format    rustflags (default) → `-C target-cpu=.. -C target-feature=..`
                env       → `RUSTFLAGS="..."` (source-able)
                list      → one rustc target-feature per line
                cargo     → a [build] rustflags array for .cargo/config.toml

Exit codes: 0 ok · 2 unknown feature / march (drift — fix the map or profile)
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILES_DIR = REPO_ROOT / "profiles"

# Profile feature name (as declared in hardware.cpu.features) → the
# rustc/LLVM target-feature token. This is the single source of truth for
# the binding; the L1 lint asserts every declared feature is a key here.
FEATURE_MAP: dict[str, str] = {
    # SSE / AVX baseline
    "sse4_2": "sse4.2",
    "avx": "avx",
    "avx2": "avx2",
    "fma": "fma",
    "bmi2": "bmi2",
    "aes": "aes",
    # AVX-512 family (Zen 5 Pulse tier)
    "avx512f": "avx512f",
    "avx512dq": "avx512dq",
    "avx512bw": "avx512bw",
    "avx512vl": "avx512vl",
    "avx512_vnni": "avx512vnni",   # VPDPBUSD — INT8 fused MAC (sovereign-vnni)
    "avx512_bf16": "avx512bf16",   # VDPBF16PS — BF16 dot (bf16 inference)
    # scalar / misc exploited by the ternary + tokenization paths
    "popcnt": "popcnt",            # population count — ternary/BitNet (sovereign-bitops)
    "sha_ni": "sha",               # SHA extensions
    "avx_vnni": "avxvnni",         # VEX-encoded VNNI (256-bit)
    "movdiri": "movdiri",
    "movdir64b": "movdir64b",
    "prefetchi": "prefetchi",
}

# march (profile hardware.cpu.march) → rustc -C target-cpu. Allowlist so a
# typo'd march is caught, not silently passed to the compiler.
MARCH_MAP: dict[str, str] = {
    "x86-64-v2": "x86-64-v2",
    "x86-64-v3": "x86-64-v3",
    "x86-64-v4": "x86-64-v4",
    "znver4": "znver4",
    "znver5": "znver5",
    "native": "native",
}


def _load_yaml(path: Path) -> dict:
    try:
        import yaml
    except ImportError:
        print("error: python3-yaml required", file=sys.stderr)
        raise SystemExit(2)
    with open(path) as f:
        return yaml.safe_load(f) or {}


def resolve_profile_path(name_or_path: str | None) -> Path:
    if name_or_path and Path(name_or_path).is_file():
        return Path(name_or_path)
    if not name_or_path:
        active = REPO_ROOT / ".sovereign-os" / "active-profile"
        name_or_path = active.read_text().strip() if active.is_file() else "sain-01"
    p = PROFILES_DIR / f"{name_or_path}.yaml"
    if not p.is_file():
        print(f"error: profile not found: {name_or_path}", file=sys.stderr)
        raise SystemExit(2)
    return p


def cpu_features(profile: dict) -> tuple[str | None, list[str]]:
    """Return (march, ordered rustc target-features) for a loaded profile.
    Order is deterministic: required (as declared) then preferred."""
    cpu = (profile.get("hardware") or {}).get("cpu") or {}
    march = cpu.get("march")
    feats = cpu.get("features") or {}
    declared: list[str] = list(feats.get("required") or []) + list(feats.get("preferred") or [])
    out: list[str] = []
    for f in declared:
        if f not in FEATURE_MAP:
            print(f"error: CPU feature '{f}' has no rustc target-feature mapping "
                  f"(add it to FEATURE_MAP in scripts/build/cpu-features.py)",
                  file=sys.stderr)
            raise SystemExit(2)
        tf = FEATURE_MAP[f]
        if tf not in out:
            out.append(tf)
    if march is not None and march not in MARCH_MAP:
        print(f"error: march '{march}' not in MARCH_MAP (add it or fix the profile)",
              file=sys.stderr)
        raise SystemExit(2)
    return march, out


def rustflags(march: str | None, features: list[str]) -> str:
    parts: list[str] = []
    if march:
        parts.append(f"-C target-cpu={MARCH_MAP[march]}")
    if features:
        parts.append("-C target-feature=" + ",".join("+" + f for f in features))
    return " ".join(parts)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="profile CPU features → build flags (SDD-043 P1)")
    ap.add_argument("--profile", default=os.environ.get("SOVEREIGN_OS_PROFILE"))
    ap.add_argument("--format", choices=["rustflags", "env", "list", "cargo"],
                    default="rustflags")
    args = ap.parse_args(argv)

    path = resolve_profile_path(args.profile)
    march, features = cpu_features(_load_yaml(path))
    flags = rustflags(march, features)

    if args.format == "rustflags":
        print(flags)
    elif args.format == "env":
        print(f'RUSTFLAGS="{flags}"')
    elif args.format == "list":
        for f in features:
            print(f)
    elif args.format == "cargo":
        print("[build]")
        arr = ", ".join(f'"{tok}"' for tok in flags.split())
        print(f"rustflags = [{arr}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
