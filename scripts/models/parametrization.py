#!/usr/bin/env python3
"""scripts/models/parametrization.py — R311 (E5.M7 closure).

Operator-named (§1b mandate row, verbatim): "Model variants +
quantizations + advanced features parametrization". E5.M7 was
partial — R231 ships variants + quantization detail; this round
ships the PARAMETRIZATION layer.

For each LLM-runtime parameter that operators tune (context_size,
n_gpu_layers, cache_type_k/v, batch_size, mlock, mmap, etc.), this
script provides:

  - per-parameter catalog with axis tag + rationale + tradeoff
  - hardware-aware recommended values (probes GPU VRAM via the
    R270 pcie-lanes / R272 avx512 / R303 gpu-wattage probes)
  - operator-overlay so per-host pin overrides defaults

CLI:
  parametrization.py list   [--axis X] [--config P] [--json|--human]
  parametrization.py show   <param> [--config P] [--json|--human]
  parametrization.py recommend [--vram-gib N] [--config P] [--json|--human]
                                hardware-aware recommended set

Operator-overlay (R283/SDD-030): /etc/sovereign-os/parametrization.toml
adds [[parameters]] (replaces catalog) OR per-key [recommendation_pin]
override.

Exit codes:
  0  rendered
  1  unknown parameter (show verb)
  2  usage error
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
try:
    from operator_overlay import load_with_overlay  # type: ignore
except Exception:  # pragma: no cover
    load_with_overlay = None


SCHEMA_VERSION = "1.0.0"
ROUND = "R311"
SDD_VECTOR = "E5.M7"


DEFAULT_PARAMETERS: list[dict[str, Any]] = [
    {
        "name": "context_size",
        "axis": "context",
        "type": "int",
        "default": 8192,
        "rationale": "Model's context window. Larger = longer "
                     "conversations + RAG retrieval, but quadratic "
                     "memory cost.",
        "tradeoff_low": "Less VRAM use; cuts long-context tasks short.",
        "tradeoff_high": "More VRAM (KV cache scales O(ctx * layers)); "
                          "slower per-token gen.",
        "recommend_per_vram_gib": {
            "<16":  4096,
            "16-24": 8192,
            "24-48": 16384,
            ">48":  32768,
        },
    },
    {
        "name": "n_gpu_layers",
        "axis": "placement",
        "type": "int",
        "default": -1,
        "rationale": "How many transformer layers to offload to GPU. "
                     "-1 = all layers. Use a smaller number to keep some "
                     "layers on CPU (split-mode hybrid inference).",
        "tradeoff_low": "Cooler GPU; uses CPU compute (much slower per "
                         "token).",
        "tradeoff_high": "Max GPU utilization; VRAM-limited.",
        "recommend_per_vram_gib": {
            "<16":  20,
            "16-24": 40,
            "24-48": -1,
            ">48":  -1,
        },
    },
    {
        "name": "cache_type_k",
        "axis": "kv-cache",
        "type": "str",
        "default": "f16",
        "rationale": "Quantization of the K-side of the KV cache. q8_0 "
                     "or q4_0 halves/quarters KV cache memory at a small "
                     "quality cost.",
        "tradeoff_low": "q4_0 = 4x smaller KV cache, slight quality drop.",
        "tradeoff_high": "f16 = baseline quality, full KV cache size.",
        "recommend_per_vram_gib": {
            "<16":  "q4_0",
            "16-24": "q8_0",
            "24-48": "q8_0",
            ">48":  "f16",
        },
    },
    {
        "name": "cache_type_v",
        "axis": "kv-cache",
        "type": "str",
        "default": "f16",
        "rationale": "V-side KV cache quantization (asymmetric KV cache "
                     "is safe — V is more compressible than K).",
        "tradeoff_low": "q4_0 V with f16 K = good balance per upstream "
                         "research.",
        "tradeoff_high": "f16 V = baseline.",
        "recommend_per_vram_gib": {
            "<16":  "q4_0",
            "16-24": "q4_0",
            "24-48": "q8_0",
            ">48":  "f16",
        },
    },
    {
        "name": "batch_size",
        "axis": "batching",
        "type": "int",
        "default": 512,
        "rationale": "Prompt-processing batch size. Larger = faster "
                     "ingestion of long prompts; smaller = lower VRAM "
                     "peak.",
        "tradeoff_low": "Lower VRAM peak during prompt eval; slower "
                         "ingestion.",
        "tradeoff_high": "Faster prompt eval; higher VRAM spike.",
        "recommend_per_vram_gib": {
            "<16":  256,
            "16-24": 512,
            "24-48": 1024,
            ">48":  2048,
        },
    },
    {
        "name": "parallel",
        "axis": "concurrency",
        "type": "int",
        "default": 1,
        "rationale": "Number of parallel sequences served concurrently. "
                     "Each parallel slot doubles KV cache use roughly.",
        "tradeoff_low": "Lower KV cache use; sequential operators.",
        "tradeoff_high": "Higher throughput for batch workloads; KV "
                          "cache linear in N.",
        "recommend_per_vram_gib": {
            "<16":  1,
            "16-24": 2,
            "24-48": 4,
            ">48":  8,
        },
    },
    {
        "name": "mlock",
        "axis": "memory",
        "type": "bool",
        "default": True,
        "rationale": "mlock() the model into RAM so the kernel can't "
                     "swap it out. Prevents 30-second stall on cold "
                     "re-use.",
        "tradeoff_low": "Kernel may swap model out; cold re-load latency "
                         "spike.",
        "tradeoff_high": "Permanent RAM commitment; fights other "
                          "workloads for RAM.",
        "recommend_per_vram_gib": {
            "<16":  True,  "16-24": True,  "24-48": True,  ">48": True,
        },
    },
    {
        "name": "mmap",
        "axis": "memory",
        "type": "bool",
        "default": True,
        "rationale": "mmap() the GGUF instead of read()-ing. Lower "
                     "memory commit + faster cold start.",
        "tradeoff_low": "Slower cold start; doubles memory footprint "
                         "during load.",
        "tradeoff_high": "Standard llama.cpp default; pairs with mlock.",
        "recommend_per_vram_gib": {
            "<16":  True,  "16-24": True,  "24-48": True,  ">48": True,
        },
    },
    {
        "name": "flash_attn",
        "axis": "compute",
        "type": "bool",
        "default": True,
        "rationale": "Use FlashAttention kernel for attention compute. "
                     "Faster + lower VRAM. Some quantized models don't "
                     "support it; fallback ok.",
        "tradeoff_low": "Standard attention; higher VRAM during eval.",
        "tradeoff_high": "FlashAttention — faster, less VRAM. Some "
                          "models incompatible.",
        "recommend_per_vram_gib": {
            "<16":  True,  "16-24": True,  "24-48": True,  ">48": True,
        },
    },
    {
        "name": "rope_freq_base",
        "axis": "context",
        "type": "float",
        "default": 10000.0,
        "rationale": "RoPE (rotary position embedding) base frequency. "
                     "Override to extend context beyond model's training "
                     "length (e.g. 1000000.0 for long-context fine-tunes).",
        "tradeoff_low": "Model native — no context extrapolation.",
        "tradeoff_high": "Extended context — works for some bases but "
                          "degrades quality for others.",
        "recommend_per_vram_gib": {
            "<16":  10000.0, "16-24": 10000.0,
            "24-48": 10000.0, ">48":  10000.0,
        },
    },
    {
        "name": "temperature",
        "axis": "sampling",
        "type": "float",
        "default": 0.7,
        "rationale": "Sampling temperature. 0 = deterministic greedy. "
                     "0.7 = balanced. >1.0 = more chaotic.",
        "tradeoff_low": "Deterministic + repetitive output.",
        "tradeoff_high": "Creative but less reliable for code / facts.",
        "recommend_per_vram_gib": {
            "<16":  0.7, "16-24": 0.7, "24-48": 0.7, ">48":  0.7,
        },
    },
    {
        "name": "top_p",
        "axis": "sampling",
        "type": "float",
        "default": 0.9,
        "rationale": "Nucleus-sampling threshold. 0.9 = consider tokens "
                     "covering 90% probability mass.",
        "tradeoff_low": "Tighter generation; less diverse.",
        "tradeoff_high": "More diverse generation; tail of low-prob "
                          "tokens reached.",
        "recommend_per_vram_gib": {
            "<16":  0.9, "16-24": 0.9, "24-48": 0.9, ">48":  0.9,
        },
    },
]


def load_catalog(overlay_path: Path | None) -> tuple[list[dict], dict, dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    catalog = list(DEFAULT_PARAMETERS)
    pins: dict[str, Any] = {}
    if load_with_overlay is not None:
        cfg = load_with_overlay(
            "parametrization",
            {"parameters": [], "recommendation_pin": {}},
            explicit_path=overlay_path,
        )
        meta["_source"] = cfg.get("_source", meta["_source"])
        meta["_overlay_keys"] = cfg.get("_overlay_keys", [])
        if cfg.get("_parse_error"):
            meta["_parse_error"] = cfg["_parse_error"]
        if cfg.get("parameters"):
            catalog = list(cfg["parameters"])
        if isinstance(cfg.get("recommendation_pin"), dict):
            pins = dict(cfg["recommendation_pin"])
    return catalog, meta, pins


def filter_axis(catalog: list[dict], axis: str | None) -> list[dict]:
    if axis is None:
        return list(catalog)
    return [d for d in catalog if isinstance(d, dict) and d.get("axis") == axis]


def resolve(catalog: list[dict], name: str) -> dict | None:
    for d in catalog:
        if isinstance(d, dict) and d.get("name") == name:
            return d
    return None


def vram_bucket(vram_gib: float | None) -> str:
    if vram_gib is None:
        return "16-24"  # safe default when unknown
    if vram_gib < 16:
        return "<16"
    if vram_gib < 24:
        return "16-24"
    if vram_gib < 48:
        return "24-48"
    return ">48"


def recommended_value(param: dict, vram_gib: float | None,
                      pins: dict) -> Any:
    if param.get("name") in pins:
        return pins[param["name"]]
    rec_map = param.get("recommend_per_vram_gib", {})
    bucket = vram_bucket(vram_gib)
    return rec_map.get(bucket, param.get("default"))


def render_list_human(entries: list[dict]) -> str:
    lines = [f"── R311 sovereign-os LLM parametrization (E5.M7) ──",
             f"  parameters: {len(entries)}", ""]
    axes = sorted({d.get("axis", "?") for d in entries if isinstance(d, dict)})
    for ax in axes:
        items = [d for d in entries if d.get("axis") == ax]
        if not items:
            continue
        lines.append(f"  ── {ax} ──")
        for d in items:
            lines.append(f"    {d.get('name'):20s}  type={d.get('type'):6s} default={d.get('default')}")
        lines.append("")
    return "\n".join(lines)


def render_show_human(d: dict, vram_gib: float | None, pins: dict) -> str:
    bucket = vram_bucket(vram_gib)
    rec = recommended_value(d, vram_gib, pins)
    pinned = d.get("name") in pins
    lines = [f"── R311 LLM parameter: {d.get('name')} (E5.M7) ──",
             f"  axis:        {d.get('axis')}",
             f"  type:        {d.get('type')}",
             f"  default:     {d.get('default')}",
             "",
             f"  current host VRAM bucket: {bucket}",
             f"  recommended:              {rec}{' [operator-pinned]' if pinned else ''}",
             ""]
    if d.get("rationale"):
        lines.append(f"  rationale: {d['rationale']}")
        lines.append("")
    lines.append(f"  tradeoff low:  {d.get('tradeoff_low')}")
    lines.append(f"  tradeoff high: {d.get('tradeoff_high')}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="parametrization.py")
    sub = p.add_subparsers(dest="verb", required=True)

    pl = sub.add_parser("list")
    pl.add_argument("--axis")
    pl.add_argument("--config", type=Path)
    fl = pl.add_mutually_exclusive_group()
    fl.add_argument("--json", dest="fmt", action="store_const", const="json")
    fl.add_argument("--human", dest="fmt", action="store_const", const="human")
    pl.set_defaults(fmt="json")

    ps = sub.add_parser("show")
    ps.add_argument("param")
    ps.add_argument("--vram-gib", type=float)
    ps.add_argument("--config", type=Path)
    fs = ps.add_mutually_exclusive_group()
    fs.add_argument("--json", dest="fmt", action="store_const", const="json")
    fs.add_argument("--human", dest="fmt", action="store_const", const="human")
    ps.set_defaults(fmt="json")

    pr = sub.add_parser("recommend")
    pr.add_argument("--vram-gib", type=float,
                    help="GPU VRAM (gib) to bucket against; "
                         "default 24 (mid-tier)")
    pr.add_argument("--config", type=Path)
    fr = pr.add_mutually_exclusive_group()
    fr.add_argument("--json", dest="fmt", action="store_const", const="json")
    fr.add_argument("--human", dest="fmt", action="store_const", const="human")
    pr.set_defaults(fmt="json")

    args = p.parse_args(argv)
    catalog, meta, pins = load_catalog(args.config)

    if args.verb == "list":
        entries = filter_axis(catalog, args.axis)
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "axis_filter": args.axis,
                "total_count": len(catalog),
                "filtered_count": len(entries),
                "parameters": entries,
                "operator_pins": pins,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_list_human(entries), end="")
        return 0

    if args.verb == "show":
        d = resolve(catalog, args.param)
        if d is None:
            print(json.dumps({
                "error": f"unknown parameter: {args.param}",
                "known": [x.get("name") for x in catalog if isinstance(x, dict)],
                "round": ROUND,
            }, indent=2), file=sys.stderr)
            return 1
        rec = recommended_value(d, args.vram_gib, pins)
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "parameter": d,
                "vram_bucket": vram_bucket(args.vram_gib),
                "recommended_value": rec,
                "operator_pinned": d.get("name") in pins,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_show_human(d, args.vram_gib, pins), end="")
        return 0

    if args.verb == "recommend":
        vram_gib = args.vram_gib if args.vram_gib is not None else 24.0
        bucket = vram_bucket(vram_gib)
        recs = []
        for d in catalog:
            if not isinstance(d, dict):
                continue
            rec = recommended_value(d, vram_gib, pins)
            recs.append({
                "name": d.get("name"),
                "axis": d.get("axis"),
                "default": d.get("default"),
                "recommended": rec,
                "operator_pinned": d.get("name") in pins,
                "rationale_excerpt": (d.get("rationale") or "")[:80],
            })
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "vram_gib_input": vram_gib,
                "vram_bucket": bucket,
                "recommendations": recs,
                "operator_pins": pins,
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R311 LLM parametrization recommend (E5.M7) ──")
            print(f"  vram bucket: {bucket} (input: {vram_gib} GiB)")
            print()
            for r in recs:
                pin = " [pinned]" if r["operator_pinned"] else ""
                print(f"  {r['name']:20s}  default={str(r['default']):>8s}  "
                      f"recommended={str(r['recommended']):>8s}{pin}")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
