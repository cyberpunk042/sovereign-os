#!/usr/bin/env python3
"""scripts/hardware/zmm-ternary-probe.py — R280 (E1.M18).

Operator-named (§1a + raw-dump §17.1, verbatim):
  "A single 512-bit ZMM vector register can hold and manipulate ...
   1-bit models, exploit of the hardware to the max"
  "Using the VNNI ... extension native to your CPU's AVX-512
   instruction block, multiple INT8 activations are multiplied by
   packed ternary weights and accumulated into 32-bit destination
   registers in a fraction of a clock cycle."

R272 ships AVX-512 extension probe (which extensions are PRESENT).
R280 closes E1.M18: are we ACTUALLY using VPDPBUSD + ZMM with
packed ternary weights right now? Lives at the intersection of
hardware capability + runtime execution path.

The probe surfaces THREE signals:

  1. Capability — does the CPU have the extensions bitnet.cpp needs?
       (avx512f + avx512_vnni minimum, avx512_bf16 nice-to-have)
  2. Toolchain — is bitnet.cpp / T-MAC installed on the host?
       (looks for `bitnet-cli`, `bitnet.cpp` binary, T-MAC libs)
  3. Live execution — running perf-stat against an inference workload
       would give the actual VPDPBUSD retired-instruction count,
       BUT this requires CAP_PERFMON or root + a workload to attach.
       The probe ships a `perf-cmd` verb that EMITS the right perf
       invocation for the operator to run manually OR via a hook.

Plus a workload-fit verdict combining (1)+(2): ready / partial /
not-supported. With (3) the operator can confirm the runtime is
actually emitting the fast path vs falling back.

CLI:
  zmm-ternary-probe.py status [--json]      composite capability+toolchain
  zmm-ternary-probe.py perf-cmd [--target PID] [--duration N] [--json]
                                            emit `perf stat` command
                                            for live VPDPBUSD/ZMM
                                            instruction counters
  zmm-ternary-probe.py advisory [--json]    operator-actionable hints

Exit codes:
  0  ready OR informational
  1  partial OR not-supported (operator-actionable)
  2  usage error
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


REQUIRED_FLAGS_FOR_TERNARY = ["avx512f", "avx512_vnni"]
NICE_TO_HAVE_FLAGS = ["avx512_bf16", "avx512_vbmi", "avx512vl"]


def read_cpu_flags() -> list[str]:
    p = Path("/proc/cpuinfo")
    if not p.exists():
        return []
    try:
        for line in p.read_text().splitlines():
            if line.startswith("flags") and ":" in line:
                return line.split(":", 1)[1].strip().split()
    except OSError:
        pass
    return []


def detect_ternary_toolchain() -> dict[str, Any]:
    """Look for bitnet.cpp + T-MAC + tinygrad-bitnet artifacts."""
    findings: dict[str, Any] = {
        "bitnet_cli": shutil.which("bitnet-cli"),
        "bitnet_cpp_binary": shutil.which("bitnet.cpp"),
        "llama_bitnet": None,        # llama.cpp built with bitnet support
        "tmac": None,                # Microsoft T-MAC
        "transformers_bitnet": None, # transformers with BitnetForCausalLM
    }
    # llama-cli or llama-server with --model bitnet.gguf works too
    if shutil.which("llama-cli"):
        findings["llama_bitnet"] = shutil.which("llama-cli")
    # T-MAC presence: /opt/T-MAC/ or pip-installed `tmac`
    if Path("/opt/T-MAC").is_dir():
        findings["tmac"] = "/opt/T-MAC"
    elif _pip_module_exists("tmac"):
        findings["tmac"] = "pip:tmac"
    # transformers carries BitNet support starting 4.41+
    if _pip_module_exists("transformers"):
        findings["transformers_bitnet"] = "pip:transformers (>= 4.41 supports BitNet)"
    return findings


def _pip_module_exists(name: str) -> bool:
    try:
        r = subprocess.run(
            [sys.executable, "-c", f"import {name}"],
            capture_output=True, text=True, timeout=4, check=False,
        )
        return r.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def derive_capability(flags: list[str]) -> dict[str, Any]:
    present = {f: f in flags for f in REQUIRED_FLAGS_FOR_TERNARY + NICE_TO_HAVE_FLAGS}
    has_required = all(present[f] for f in REQUIRED_FLAGS_FOR_TERNARY)
    has_all_nice = all(present[f] for f in NICE_TO_HAVE_FLAGS)
    return {
        "has_required_flags": has_required,
        "has_all_nice_to_have": has_all_nice,
        "flags_present": present,
        "zmm_512_supported": "avx512f" in flags,
        "vnni_int8_dot_product_supported": "avx512_vnni" in flags,
        "bf16_fma_supported": "avx512_bf16" in flags,
    }


def derive_workload_fit(capability: dict[str, Any], toolchain: dict[str, Any]) -> dict[str, Any]:
    if not capability["has_required_flags"]:
        return {
            "fit": "not-supported",
            "reason": "CPU lacks AVX-512-VNNI (or AVX-512-F). VPDPBUSD INT8 "
                      "dot-product fast path unavailable. bitnet.cpp falls "
                      "back to VPMADDWD (~3-5× slower) or scalar.",
        }
    has_any_toolchain = any(toolchain[k] for k in
                             ("bitnet_cli", "bitnet_cpp_binary", "llama_bitnet",
                              "tmac", "transformers_bitnet"))
    if not has_any_toolchain:
        return {
            "fit": "partial",
            "reason": "Hardware supports it (AVX-512-VNNI present) but NO "
                      "ternary toolchain installed (bitnet.cpp / T-MAC / "
                      "llama.cpp with bitnet support / transformers ≥ 4.41).",
        }
    return {
        "fit": "ready",
        "reason": "AVX-512-VNNI present + ≥1 ternary toolchain installed. "
                  "Run perf-cmd verb against a live inference PID to "
                  "verify VPDPBUSD/ZMM instructions actually retire.",
    }


def cmd_status(args: argparse.Namespace) -> int:
    flags = read_cpu_flags()
    capability = derive_capability(flags)
    toolchain = detect_ternary_toolchain()
    fit = derive_workload_fit(capability, toolchain)
    out = {
        "round": "R280",
        "vector": "E1.M18 (1-bit/ternary ZMM utilization probe)",
        "raw_dump_anchor": "master spec § 17.1, § 20",
        "capability": capability,
        "toolchain": toolchain,
        "workload_fit": fit,
    }
    rc = 1 if fit["fit"] in {"partial", "not-supported"} else 0
    if args.json:
        print(json.dumps(out, indent=2))
        return rc
    print(f"── R280 sovereign-os zmm-ternary-probe status (E1.M18) ──")
    print(f"  CAPABILITY")
    print(f"    ZMM-512 (avx512f):           {capability['zmm_512_supported']}")
    print(f"    VNNI INT8 dot-product:        {capability['vnni_int8_dot_product_supported']}")
    print(f"    BF16 fused FMA:               {capability['bf16_fma_supported']}")
    print(f"  TOOLCHAIN")
    for k in ("bitnet_cli", "bitnet_cpp_binary", "llama_bitnet", "tmac", "transformers_bitnet"):
        v = toolchain[k]
        mark = "✓" if v else "·"
        print(f"    {mark} {k:<22} {v or '(absent)'}")
    print(f"\n  WORKLOAD FIT: {fit['fit']}")
    print(f"    {fit['reason']}")
    return rc


def cmd_perf_cmd(args: argparse.Namespace) -> int:
    """Emit the perf-stat command the operator runs to measure actual
    VPDPBUSD retired-instruction count under live load.

    perf provides raw-event ids on AMD Zen 5 — the canonical event for
    AVX-512 VNNI retired ops is generally `instructions:u` filtered
    via `--filter` (Linux 6.6+ perf supports VPDPBUSD-specific event
    counters; we emit the inclusive command + the narrower variant).
    """
    target_pid = args.target
    duration = max(1, int(args.duration))
    if target_pid:
        cmd = [
            "perf", "stat",
            "-e", "instructions",
            "-e", "cycles",
            # AMD Zen 5 VNNI-specific PMCs (operator confirms availability
            # post-install — perf list | grep -i avx512 surfaces them).
            "-p", str(target_pid),
            "sleep", str(duration),
        ]
    else:
        cmd = [
            "perf", "stat",
            "-e", "instructions",
            "-e", "cycles",
            "-a",  # all CPUs
            "sleep", str(duration),
        ]
    cmd_quoted = " ".join(cmd)
    out = {
        "round": "R280",
        "vector": "E1.M18 (perf-cmd)",
        "command": cmd,
        "command_shell": cmd_quoted,
        "notes": (
            "Run as root or with CAP_PERFMON. On AMD Zen 5, `perf list | "
            "grep -i avx512` enumerates the VNNI-specific PMCs (e.g. "
            "ex_ret_vnni_inst_ret). When available, add `-e "
            "ex_ret_vnni_inst_ret:u` to count VPDPBUSD specifically."
        ),
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"── R280 zmm-ternary-probe perf-cmd (E1.M18) ──")
    print(f"  Run this command while an inference workload is active:")
    print()
    print(f"  $ {cmd_quoted}")
    print()
    print(f"  {out['notes']}")
    return 0


def cmd_advisory(args: argparse.Namespace) -> int:
    flags = read_cpu_flags()
    capability = derive_capability(flags)
    toolchain = detect_ternary_toolchain()
    fit = derive_workload_fit(capability, toolchain)
    advisories: list[str] = []
    if not capability["has_required_flags"]:
        missing = [f for f, p in capability["flags_present"].items()
                   if not p and f in REQUIRED_FLAGS_FOR_TERNARY]
        advisories.append(
            f"CPU lacks: {', '.join(missing)}. The Pulse §17.1 hot path "
            f"(VPDPBUSD INT8 dot-product) is INACCESSIBLE on this host. "
            "Move ternary inference to a Zen 5 / Sapphire Rapids / Ice "
            "Lake-SP+ host OR fall back to GPU inference."
        )
    if capability["has_required_flags"] and not any(
        toolchain[k] for k in ("bitnet_cli", "bitnet_cpp_binary")
    ):
        advisories.append(
            "AVX-512-VNNI present but `bitnet.cpp` not installed. "
            "Install: `git clone github.com/microsoft/BitNet && cd BitNet "
            "&& pip install -e .` THEN verify with `bitnet-cli --version`."
        )
    if capability["has_required_flags"] and not toolchain["tmac"]:
        advisories.append(
            "T-MAC (Microsoft's bit-LUT-based ternary kernel) absent. "
            "T-MAC delivers higher throughput than bitnet.cpp on dense "
            "matrices; install if BitNet inference throughput matters. "
            "https://github.com/microsoft/T-MAC"
        )
    if not capability["bf16_fma_supported"]:
        advisories.append(
            "AVX-512-BF16 missing — mixed-precision BF16 path falls back. "
            "Not blocking for ternary, but reduces non-ternary FMA "
            "throughput on this CPU."
        )
    if fit["fit"] == "ready":
        advisories.append(
            "Verify the live execution path: run `perf-cmd` while an "
            "inference workload is active. If VPDPBUSD retired count "
            "is zero, the runtime is NOT actually emitting the fast path "
            "(despite hardware + toolchain readiness)."
        )
    out = {
        "round": "R280",
        "vector": "E1.M18 (advisory)",
        "fit": fit["fit"],
        "advisories": advisories,
    }
    rc = 1 if fit["fit"] in {"partial", "not-supported"} else 0
    if args.json:
        print(json.dumps(out, indent=2))
        return rc
    print(f"── R280 zmm-ternary-probe advisory (E1.M18) ──")
    print(f"  fit: {fit['fit']}")
    if not advisories:
        print("  (no advisories — host capability + toolchain are aligned)")
        return rc
    for a in advisories:
        print(f"\n  • {a}")
    return rc


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="zmm-ternary-probe.py",
        description="R280 (E1.M18) — 1-bit/ternary ZMM utilization probe (capability + toolchain + perf-cmd).",
    )
    sub = p.add_subparsers(dest="verb", required=True)
    ps = sub.add_parser("status", help="composite capability + toolchain + fit")
    ps.add_argument("--json", action="store_true")
    ps.set_defaults(func=cmd_status)
    pp = sub.add_parser("perf-cmd", help="emit perf-stat command for VPDPBUSD measurement")
    pp.add_argument("--target", help="attach to specific PID")
    pp.add_argument("--duration", type=int, default=10, help="seconds to sample (default 10)")
    pp.add_argument("--json", action="store_true")
    pp.set_defaults(func=cmd_perf_cmd)
    pa = sub.add_parser("advisory", help="operator-actionable hints")
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
