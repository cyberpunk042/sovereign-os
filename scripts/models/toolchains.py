#!/usr/bin/env python3
"""scripts/models/toolchains.py — R242 (SDD-026 Z-2 expansion).

Operator-named (verbatim, 2026-05-17 expansion): "there are going to
be multiple mode of functioning too, like LM Studio and LM Link
maybe ? Unsloth ?"

Catalog of model inference + fine-tune toolchains the operator might
want on this host. Each entry declares:

  - kind            inference / fine-tune / both
  - detection       how to probe whether it's installed (bin / pip / dir)
  - install_hint    one-liner the operator runs to install
  - operator_role   what the operator uses it FOR (training / serving /
                    eval / quantization / etc.)

Per-toolchain live detection runs on each call. JSON output drives
the dashboard 'Toolchains' tab + the operator's "what AI infrastructure
do I have on this host?" answer.

CLI:
  toolchains.py list [--kind K] [--installed-only] [--json]
  toolchains.py info <name> [--json]

Exit codes:
  0  always (informational verb)
  2  usage error / unknown toolchain
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------- toolchain registry
#
# Each entry: {
#   name, kind, summary, operator_role, install_hint,
#   detect: { binary?, pip?, dir?, python_import? }
# }
TOOLCHAINS: list[dict[str, Any]] = [
    {
        "name": "llama.cpp",
        "kind": "inference",
        "summary": "C++/CUDA llama.cpp inference + quantization (GGUF format).",
        "operator_role": "serve GGUF-quantized models locally; quantize HF "
                         "models to GGUF Q4_K_M / Q5_K_M / Q8_0",
        "install_hint": "git clone github.com/ggerganov/llama.cpp && make -C llama.cpp",
        "detect": {"binary": "llama-server"},
        "license": "MIT",
        "hardware_fit": ["CPU", "CUDA", "Vulkan", "Metal"],
    },
    {
        "name": "bitnet.cpp",
        "kind": "inference",
        "summary": "Microsoft BitNet.cpp ternary (1.58-bit) inference engine.",
        "operator_role": "serve ternary-LM models on AVX-512-VNNI hosts; "
                         "primary engine for Pulse tier (master spec §17.1)",
        "install_hint": "git clone github.com/microsoft/BitNet && cd BitNet && pip install -e .",
        "detect": {"binary": "bitnet-cli"},
        "license": "MIT",
        "hardware_fit": ["CPU-AVX512-VNNI"],
    },
    {
        "name": "vllm",
        "kind": "inference",
        "summary": "High-throughput LLM serving with PagedAttention.",
        "operator_role": "production serving with continuous batching; "
                         "Oracle-tier RLM/LLM hot path",
        "install_hint": "pip install vllm",
        "detect": {"pip": "vllm", "python_import": "vllm"},
        "license": "Apache-2.0",
        "hardware_fit": ["CUDA"],
    },
    {
        "name": "ollama",
        "kind": "inference",
        "summary": "Local LLM runtime with model registry + REST API.",
        "operator_role": "operator-facing local inference; serves any GGUF",
        "install_hint": "curl -fsSL ollama.ai/install.sh | sh",
        "detect": {"binary": "ollama"},
        "license": "MIT",
        "hardware_fit": ["CPU", "CUDA", "Metal"],
    },
    {
        "name": "lm-studio",
        "kind": "inference",
        "summary": "LM Studio GUI + local API server (closed-source GUI).",
        "operator_role": "operator-facing GUI for browsing + running models; "
                         "sovereign-os ships HEADLESS by default — use only on "
                         "operator-attached screen sessions",
        "install_hint": "download from lmstudio.ai (closed-source binary)",
        "detect": {"binary": "lms"},
        "license": "proprietary (GUI); MIT (CLI)",
        "hardware_fit": ["CPU", "CUDA", "Metal"],
    },
    {
        "name": "unsloth",
        "kind": "fine-tune",
        "summary": "Unsloth — 2-5× faster LoRA / QLoRA fine-tuning on consumer GPUs.",
        "operator_role": "operator-driven LoRA fine-tunes on the SAIN-01 GPUs; "
                         "supports Llama / Mistral / Qwen / Gemma base models",
        "install_hint": "pip install unsloth",
        "detect": {"pip": "unsloth", "python_import": "unsloth"},
        "license": "Apache-2.0",
        "hardware_fit": ["CUDA"],
    },
    {
        "name": "lm-link",
        "kind": "inference",
        "summary": "LM Link — multi-model gateway + per-request routing across "
                   "local & remote LM Studio / Ollama / llama.cpp servers.",
        "operator_role": "operator-facing single endpoint when running BOTH "
                         "lm-studio AND ollama AND llama-server on the same "
                         "host — LM Link multiplexes them under one OpenAI-"
                         "compatible API URL",
        "install_hint": "pip install lm-link (or download release from lm-link.dev)",
        "detect": {"binary": "lm-link", "pip": "lm_link", "python_import": "lm_link"},
        "license": "Apache-2.0",
        "hardware_fit": ["any"],
    },
    {
        "name": "transformers",
        "kind": "both",
        "summary": "HuggingFace transformers — reference runtime + training loop.",
        "operator_role": "ground-truth runtime for novel architectures; "
                         "loaders for every HF-hosted model",
        "install_hint": "pip install transformers accelerate",
        "detect": {"pip": "transformers", "python_import": "transformers"},
        "license": "Apache-2.0",
        "hardware_fit": ["CPU", "CUDA"],
    },
    {
        "name": "trl",
        "kind": "fine-tune",
        "summary": "HuggingFace TRL — SFT / DPO / PPO training pipeline.",
        "operator_role": "RLHF + preference fine-tuning (DPO/PPO/KTO) on top of "
                         "transformers loaders",
        "install_hint": "pip install trl",
        "detect": {"pip": "trl", "python_import": "trl"},
        "license": "Apache-2.0",
        "hardware_fit": ["CUDA"],
    },
    {
        "name": "huggingface-cli",
        "kind": "both",
        "summary": "HuggingFace Hub CLI — download / upload models + datasets.",
        "operator_role": "operator-facing HF push/pull primitive; "
                         "sovereign-os scripts/models/pull.sh wraps it",
        "install_hint": "pip install huggingface_hub",
        "detect": {"binary": "huggingface-cli", "pip": "huggingface_hub"},
        "license": "Apache-2.0",
        "hardware_fit": ["any"],
    },
    {
        "name": "lm-eval-harness",
        "kind": "eval",
        "summary": "EleutherAI lm-evaluation-harness — MMLU / HumanEval / ARC etc.",
        "operator_role": "primary eval driver for R232 `models eval` benchmarks",
        "install_hint": "pip install lm-eval",
        "detect": {"binary": "lm-eval", "pip": "lm_eval"},
        "license": "MIT",
        "hardware_fit": ["CPU", "CUDA"],
    },
    {
        "name": "mteb",
        "kind": "eval",
        "summary": "Massive Text Embedding Benchmark — embedding model recall@k.",
        "operator_role": "eval driver for embedding models (R212 class=embed)",
        "install_hint": "pip install mteb",
        "detect": {"pip": "mteb", "python_import": "mteb"},
        "license": "Apache-2.0",
        "hardware_fit": ["CPU", "CUDA"],
    },
    {
        "name": "dflash",
        "kind": "inference",
        "summary": "DFlash speculative decoding (SDD-026 Round 157).",
        "operator_role": "block-diffusion speculation harness for 2-3× decode "
                         "speedups on Oracle-tier models",
        "install_hint": "git clone github.com/z-lab/dflash && pip install -e dflash",
        "detect": {"pip": "dflash", "python_import": "dflash"},
        "license": "Apache-2.0",
        "hardware_fit": ["CUDA"],
    },
]


def detect_installed(detect: dict[str, Any]) -> dict[str, Any]:
    """Run all configured probes; return per-probe outcome + a final OK bool."""
    probes: dict[str, Any] = {}
    any_ok = False

    binary = detect.get("binary")
    if binary:
        path = shutil.which(binary)
        probes["binary"] = {"name": binary, "path": path, "ok": path is not None}
        if path is not None:
            any_ok = True

    pip_pkg = detect.get("pip")
    if pip_pkg:
        # Use `pip show` (cheap) when pip exists.
        pip_ok = False
        if shutil.which("pip") or shutil.which("pip3"):
            try:
                r = subprocess.run(
                    ["pip", "show", pip_pkg],
                    capture_output=True, text=True, timeout=8, check=False,
                )
                pip_ok = r.returncode == 0
            except (subprocess.TimeoutExpired, OSError):
                pip_ok = False
        probes["pip"] = {"name": pip_pkg, "ok": pip_ok}
        if pip_ok:
            any_ok = True

    py_import = detect.get("python_import")
    if py_import:
        try:
            r = subprocess.run(
                [sys.executable, "-c", f"import {py_import}"],
                capture_output=True, text=True, timeout=5, check=False,
            )
            ok = r.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            ok = False
        probes["python_import"] = {"name": py_import, "ok": ok}
        if ok:
            any_ok = True

    dir_path = detect.get("dir")
    if dir_path:
        ok = Path(dir_path).is_dir()
        probes["dir"] = {"path": dir_path, "ok": ok}
        if ok:
            any_ok = True

    return {"probes": probes, "installed": any_ok}


def classify_all() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for t in TOOLCHAINS:
        det = detect_installed(t.get("detect") or {})
        rows.append(
            {
                "name": t["name"],
                "kind": t["kind"],
                "summary": t["summary"],
                "operator_role": t["operator_role"],
                "install_hint": t["install_hint"],
                "license": t.get("license", "unknown"),
                "hardware_fit": t.get("hardware_fit", []),
                "installed": det["installed"],
                "detect": det,
            }
        )
    return rows


def cmd_list(args: argparse.Namespace) -> int:
    rows = classify_all()
    if args.kind:
        rows = [r for r in rows if r["kind"] == args.kind or r["kind"] == "both"]
    if args.installed_only:
        rows = [r for r in rows if r["installed"]]
    counts = {
        "total": len(rows),
        "installed": sum(1 for r in rows if r["installed"]),
        "absent": sum(1 for r in rows if not r["installed"]),
        "by_kind": {},
    }
    for r in rows:
        counts["by_kind"][r["kind"]] = counts["by_kind"].get(r["kind"], 0) + 1
    report = {
        "round": "R242",
        "vector": "SDD-026 Z-2 (toolchains catalog)",
        "filter": {"kind": args.kind, "installed_only": args.installed_only},
        "counts": counts,
        "toolchains": rows,
    }
    if args.json:
        print(json.dumps(report, indent=2))
        return 0
    print(f"── R242 sovereign-os models toolchains (SDD-026 Z-2) ──")
    print(
        f"  totals:  installed={counts['installed']}  absent={counts['absent']}  "
        f"(by_kind: {counts['by_kind']})"
    )
    print()
    for r in rows:
        glyph = "✓" if r["installed"] else "·"
        print(f"  {glyph} {r['name']:<22} [{r['kind']:<10}]  {r['summary']}")
        if not r["installed"]:
            print(f"      install: {r['install_hint']}")
        else:
            # Show how it was detected.
            kinds_ok = [
                k for k, p in r["detect"]["probes"].items() if p.get("ok")
            ]
            print(f"      detected via: {','.join(kinds_ok)}")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    rows = classify_all()
    match = next((r for r in rows if r["name"] == args.name), None)
    if match is None:
        known = sorted(r["name"] for r in rows)
        print(
            f"ERROR unknown toolchain {args.name!r}; known: {known}",
            file=sys.stderr,
        )
        return 2
    report = {
        "round": "R242",
        "vector": "SDD-026 Z-2 (toolchain detail)",
        **match,
    }
    if args.json:
        print(json.dumps(report, indent=2))
        return 0
    print(f"── R242 sovereign-os models toolchain — {match['name']} ──")
    print(f"  kind:           {match['kind']}")
    print(f"  installed:      {match['installed']}")
    print(f"  license:        {match['license']}")
    print(f"  hardware_fit:   {', '.join(match['hardware_fit']) or '?'}")
    print(f"  summary:        {match['summary']}")
    print(f"  operator role:  {match['operator_role']}")
    if not match["installed"]:
        print(f"  install hint:   {match['install_hint']}")
    print(f"  detect probes:")
    for k, p in match["detect"]["probes"].items():
        mark = "✓" if p.get("ok") else "x"
        print(f"    {mark} {k}: {json.dumps(p)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="toolchains.py",
        description="R242 (SDD-026 Z-2) — inference + fine-tune toolchain catalog.",
    )
    sub = p.add_subparsers(dest="verb", required=True)
    pl = sub.add_parser("list", help="enumerate the toolchain catalog")
    pl.add_argument(
        "--kind",
        choices=["inference", "fine-tune", "eval", "both"],
        help="filter by toolchain kind",
    )
    pl.add_argument("--installed-only", action="store_true")
    pl.add_argument("--json", action="store_true")
    pl.set_defaults(func=cmd_list)

    pi = sub.add_parser("info", help="full detail for one toolchain")
    pi.add_argument("name")
    pi.add_argument("--json", action="store_true")
    pi.set_defaults(func=cmd_info)
    return p


def main(argv: list[str]) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
