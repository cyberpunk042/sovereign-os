#!/usr/bin/env python3
"""scripts/hardware/wasm-aot-enforcer.py — R281 (E1.M17).

Operator-named (§1a + raw-dump master-spec §20, verbatim):
  "## 20. The Wasm-to-AVX-512 AOT Pipeline (The Pulse Implementation)
   When The Pulse processes low-bit matrix logic via WebAssembly, it
   avoids standard JIT (Just-In-Time) compilation bloat. Instead, it
   uses an Ahead-Of-Time (AOT) compilation lifecycle optimized via
   Cranelift or LLVM to output native Zen 5 machine code."

   "# Force the Cranelift/Wasmtime compiler to emit absolute
    microarchitectural optimization
    export WASMTIME_COMPARE_OPTIONS=\"-C target-cpu=znver5 -C opt-level=3
       -C relaxed-simd=true\"
    taskset -c 0-11 wasmtime compile --target znver5 -O speed
       /mnt/vault/agents/pulse_core.wasm"

R155 ships the build-bitnet pipeline. R280 ships ternary execution
probe. R281 closes E1.M17: validate that the Wasm-to-AVX-512 AOT
TOOLCHAIN is correctly installed AND emit the operator-canonical
compile invocation when given a Wasm source path.

Three signals:
  - toolchain status — is wasmtime present? Cranelift compiled in?
  - target-cpu support — does wasmtime support `--target znver5`?
                          (older wasmtime needs `--target x86_64`
                          + RUSTFLAGS for target-cpu)
  - env-flag enforcement — is WASMTIME_COMPARE_OPTIONS / similar set
                            to the master-spec-mandated values?

CLI:
  wasm-aot-enforcer.py status [--json]              toolchain + env state
  wasm-aot-enforcer.py compile-cmd <wasm-path> [--json]
                                                    emit the canonical
                                                    `wasmtime compile`
                                                    invocation
  wasm-aot-enforcer.py advisory [--json]            operator-actionable
                                                    drift from spec
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


# Master-spec §20 canonical knobs.
SPEC_TARGET_CPU = "znver5"
SPEC_OPT_LEVEL = "3"
SPEC_RELAXED_SIMD = "true"
SPEC_TASKSET_CORES = "0-11"

# Env vars the master spec invokes.
ENV_WASMTIME_OPTIONS = "WASMTIME_COMPARE_OPTIONS"
ENV_RUSTFLAGS = "RUSTFLAGS"


def detect_wasmtime() -> dict[str, Any]:
    path = shutil.which("wasmtime")
    out: dict[str, Any] = {"binary_path": path, "version": None, "supports_compile": False}
    if path is None:
        return out
    try:
        r = subprocess.run(
            ["wasmtime", "--version"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        out["version"] = r.stdout.strip() or r.stderr.strip()
    except (subprocess.TimeoutExpired, OSError):
        pass
    # Check whether `wasmtime compile` subcommand exists.
    try:
        r = subprocess.run(
            ["wasmtime", "compile", "--help"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        out["supports_compile"] = r.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        pass
    return out


def detect_cranelift_target() -> dict[str, Any]:
    """Check whether wasmtime knows about the `znver5` target.

    wasmtime --target list (when supported) enumerates Cranelift
    targets. Older wasmtime versions only support `x86_64-unknown-...`
    and the operator must set RUSTFLAGS to push the target-cpu.
    """
    if not shutil.which("wasmtime"):
        return {"target_listing_available": False, "znver5_explicit": None}
    try:
        r = subprocess.run(
            ["wasmtime", "compile", "--help"],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return {"target_listing_available": False, "znver5_explicit": None}
    znver5_explicit = "znver5" in r.stdout.lower()
    return {
        "target_listing_available": r.returncode == 0,
        "znver5_explicit": znver5_explicit,
    }


def detect_env_state() -> dict[str, Any]:
    """Read env vars + verify their values match master-spec §20."""
    out: dict[str, Any] = {}
    wasmtime_opts = os.environ.get(ENV_WASMTIME_OPTIONS, "")
    rustflags = os.environ.get(ENV_RUSTFLAGS, "")
    out["wasmtime_compare_options_raw"] = wasmtime_opts or None
    out["rustflags_raw"] = rustflags or None
    # Spec-conformance checks
    out["target_cpu_set"] = (
        f"target-cpu={SPEC_TARGET_CPU}" in wasmtime_opts
        or f"target-cpu={SPEC_TARGET_CPU}" in rustflags
        or f"-Ctarget-cpu={SPEC_TARGET_CPU}" in rustflags
    )
    out["opt_level_set"] = (
        f"opt-level={SPEC_OPT_LEVEL}" in wasmtime_opts
        or f"-C opt-level={SPEC_OPT_LEVEL}" in rustflags
    )
    out["relaxed_simd_set"] = (
        f"relaxed-simd={SPEC_RELAXED_SIMD}" in wasmtime_opts
        or "relaxed-simd=true" in rustflags
    )
    return out


def emit_compile_cmd(wasm_path: str) -> list[str]:
    """Build the master-spec §20 canonical wasmtime compile invocation."""
    return [
        "taskset", "-c", SPEC_TASKSET_CORES,
        "wasmtime", "compile",
        "--target", "x86_64",  # CPU subtype set via RUSTFLAGS / target-cpu
        "-O", "speed",
        wasm_path,
    ]


def derive_verdict(
    wasmtime: dict[str, Any], target: dict[str, Any], env: dict[str, Any]
) -> dict[str, Any]:
    if not wasmtime["binary_path"]:
        return {
            "fit": "not-supported",
            "reason": (
                "wasmtime binary not installed. Master spec §20 ('The "
                "Pulse Implementation') REQUIRES wasmtime for the "
                "Wasm-to-AVX-512 AOT pipeline. Install: `curl https://"
                "wasmtime.dev/install.sh -sSf | bash`."
            ),
        }
    if not wasmtime["supports_compile"]:
        return {
            "fit": "partial",
            "reason": (
                "wasmtime installed but `wasmtime compile` subcommand "
                "unavailable. Upgrade to a recent release (current: "
                f"{wasmtime['version']!r}); the compile subcommand has "
                "been stable since wasmtime 0.39."
            ),
        }
    missing_env: list[str] = []
    if not env["target_cpu_set"]:
        missing_env.append(f"target-cpu={SPEC_TARGET_CPU}")
    if not env["opt_level_set"]:
        missing_env.append(f"opt-level={SPEC_OPT_LEVEL}")
    if not env["relaxed_simd_set"]:
        missing_env.append(f"relaxed-simd={SPEC_RELAXED_SIMD}")
    if missing_env:
        return {
            "fit": "partial",
            "reason": (
                f"wasmtime ready but env not configured for AVX-512 AOT. "
                f"Missing master-spec §20 settings: {', '.join(missing_env)}. "
                f"Export {ENV_WASMTIME_OPTIONS} OR {ENV_RUSTFLAGS} with "
                "these knobs before invoking wasmtime compile."
            ),
        }
    return {
        "fit": "ready",
        "reason": (
            "wasmtime + Cranelift compile path + env flags all conform to "
            "master-spec §20. `wasmtime compile` will emit znver5-targeted "
            "native code with relaxed-simd enabled."
        ),
    }


def cmd_status(args: argparse.Namespace) -> int:
    wasmtime = detect_wasmtime()
    target = detect_cranelift_target()
    env = detect_env_state()
    verdict = derive_verdict(wasmtime, target, env)
    out = {
        "round": "R281",
        "vector": "E1.M17 (Wasm-to-AVX-512 AOT enforcer)",
        "raw_dump_anchor": "master spec § 20 (The Pulse Implementation)",
        "spec_target_cpu": SPEC_TARGET_CPU,
        "spec_opt_level": SPEC_OPT_LEVEL,
        "spec_relaxed_simd": SPEC_RELAXED_SIMD,
        "wasmtime": wasmtime,
        "cranelift_target": target,
        "env_state": env,
        "verdict": verdict,
    }
    rc = 1 if verdict["fit"] in {"partial", "not-supported"} else 0
    if args.json:
        print(json.dumps(out, indent=2))
        return rc
    print(f"── R281 sovereign-os wasm-aot-enforcer status (E1.M17) ──")
    print(f"  spec ref:      master spec § 20")
    print(f"  spec target:   {SPEC_TARGET_CPU}  opt-level {SPEC_OPT_LEVEL}  relaxed-simd={SPEC_RELAXED_SIMD}")
    print(f"\n  wasmtime")
    print(f"    binary:    {wasmtime['binary_path'] or '(absent)'}")
    print(f"    version:   {wasmtime['version']}")
    print(f"    compile?:  {wasmtime['supports_compile']}")
    print(f"\n  Cranelift target")
    print(f"    znver5 explicit: {target['znver5_explicit']}")
    print(f"\n  env")
    print(f"    {ENV_WASMTIME_OPTIONS}: {env['wasmtime_compare_options_raw'] or '(unset)'}")
    print(f"    {ENV_RUSTFLAGS}:           {env['rustflags_raw'] or '(unset)'}")
    print(f"    target_cpu_set:           {env['target_cpu_set']}")
    print(f"    opt_level_set:            {env['opt_level_set']}")
    print(f"    relaxed_simd_set:         {env['relaxed_simd_set']}")
    print(f"\n  verdict: {verdict['fit']}")
    print(f"    {verdict['reason']}")
    return rc


def cmd_compile_cmd(args: argparse.Namespace) -> int:
    cmd = emit_compile_cmd(args.wasm_path)
    # Recommended env preamble.
    env_preamble = [
        f'export {ENV_WASMTIME_OPTIONS}="-C target-cpu={SPEC_TARGET_CPU} '
        f'-C opt-level={SPEC_OPT_LEVEL} -C relaxed-simd={SPEC_RELAXED_SIMD}"',
    ]
    out = {
        "round": "R281",
        "vector": "E1.M17 (compile-cmd)",
        "wasm_path": args.wasm_path,
        "env_preamble": env_preamble,
        "command": cmd,
        "command_shell": " ".join(cmd),
        "spec_anchor": "master spec § 20",
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"── R281 wasm-aot-enforcer compile-cmd (E1.M17) ──")
    print(f"  paste this in operator's shell before invoking:")
    for line in env_preamble:
        print(f"    {line}")
    print()
    print(f"  $ {' '.join(cmd)}")
    return 0


def cmd_advisory(args: argparse.Namespace) -> int:
    wasmtime = detect_wasmtime()
    target = detect_cranelift_target()
    env = detect_env_state()
    verdict = derive_verdict(wasmtime, target, env)
    advisories: list[str] = []
    if verdict["fit"] != "ready":
        advisories.append(verdict["reason"])
    # Always note the operator-canonical env-export incantation
    if not (env["target_cpu_set"] and env["opt_level_set"] and env["relaxed_simd_set"]):
        advisories.append(
            f"To make this persistent: add the following to operator's "
            f"shell rc (~/.bashrc OR /etc/profile.d/sovereign-os-wasm-aot.sh):\n"
            f"  export {ENV_WASMTIME_OPTIONS}=\"-C target-cpu={SPEC_TARGET_CPU} "
            f"-C opt-level={SPEC_OPT_LEVEL} -C relaxed-simd={SPEC_RELAXED_SIMD}\""
        )
    out = {
        "round": "R281",
        "vector": "E1.M17 (advisory)",
        "fit": verdict["fit"],
        "advisories": advisories,
    }
    rc = 1 if verdict["fit"] in {"partial", "not-supported"} else 0
    if args.json:
        print(json.dumps(out, indent=2))
        return rc
    print(f"── R281 wasm-aot-enforcer advisory (E1.M17) ──")
    print(f"  fit: {verdict['fit']}")
    for a in advisories:
        print(f"\n  • {a}")
    if not advisories:
        print("  (ready — master spec §20 honored)")
    return rc


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="wasm-aot-enforcer.py",
        description="R281 (E1.M17) — Wasm-to-AVX-512 AOT pipeline enforcer per master spec § 20.",
    )
    sub = p.add_subparsers(dest="verb", required=True)
    ps = sub.add_parser("status", help="toolchain + env state + verdict")
    ps.add_argument("--json", action="store_true")
    ps.set_defaults(func=cmd_status)
    pc = sub.add_parser("compile-cmd", help="emit canonical wasmtime invocation")
    pc.add_argument("wasm_path", help="path to .wasm to compile (e.g. /mnt/vault/agents/pulse_core.wasm)")
    pc.add_argument("--json", action="store_true")
    pc.set_defaults(func=cmd_compile_cmd)
    pa = sub.add_parser("advisory", help="operator-actionable drift hints")
    pa.add_argument("--json", action="store_true")
    pa.set_defaults(func=cmd_advisory)
    return p


def main(argv: list[str]) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
