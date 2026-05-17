#!/usr/bin/env python3
"""scripts/models/catalog-query.py — R213 operator query surface over
the sovereign-os model catalog.

The R212 catalog carries the full taxonomy (class × quantization ×
size_class × purpose × vram_gib_min × context_window_tokens) for 17
curated models. R213 puts an operator-facing filter on top:

  catalog-query.py --class rlm --max-vram 48
  catalog-query.py --purpose code --status verified-real
  catalog-query.py --tier oracle --quantization fp8
  catalog-query.py --min-context 65536

Filters compose (every flag is an AND constraint). Output is either
a one-model-per-line table (default) or JSON for fleet tooling.

Exit codes:
  0  ≥1 model matched
  1  zero models matched (used by `||` chains in operator scripts)
  2  usage error
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPO_ROOT / "models" / "catalog.yaml"


def load_catalog() -> list[dict[str, Any]]:
    with CATALOG_PATH.open() as fh:
        doc = yaml.safe_load(fh)
    return doc["catalog"]["models"]


def match(model: dict[str, Any], args: argparse.Namespace) -> bool:
    if args.cls and model.get("class") != args.cls:
        return False
    if args.tier and model.get("tier") != args.tier:
        return False
    if args.engine and model.get("engine") != args.engine:
        return False
    if args.quantization and model.get("quantization") != args.quantization:
        return False
    if args.size_class and model.get("size_class") != args.size_class:
        return False
    if args.status and model.get("status") != args.status:
        return False
    if args.purpose:
        purposes = set(model.get("purpose") or [])
        if args.purpose not in purposes:
            return False
    if args.max_vram is not None:
        vram = model.get("vram_gib_min")
        # Models without declared vram are excluded when --max-vram set:
        # operator asked for a VRAM budget, undeclared models can't be
        # proven to fit.
        if vram is None or vram > args.max_vram:
            return False
    if args.min_context is not None:
        ctx = model.get("context_window_tokens")
        if ctx is None or ctx < args.min_context:
            return False
    if args.base_model and model.get("base_model") != args.base_model:
        return False
    return True


def render_table(matches: list[dict[str, Any]]) -> str:
    if not matches:
        return "(no models match)\n"
    lines: list[str] = []
    lines.append(
        f"{'id':<48}  {'tier':<6}  {'class':<14}  "
        f"{'size':<5}  {'quant':<18}  {'vram-min':<8}  status"
    )
    for m in matches:
        vram = m.get("vram_gib_min")
        vram_display = f"{vram:.1f} GiB" if isinstance(vram, (int, float)) else "?"
        lines.append(
            f"{m.get('id','?'):<48}  "
            f"{m.get('tier','?'):<6}  "
            f"{m.get('class','?'):<14}  "
            f"{m.get('size_class','?'):<5}  "
            f"{m.get('quantization','?'):<18}  "
            f"{vram_display:<8}  "
            f"{m.get('status','?')}"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "Filter the sovereign-os model catalog by R212 taxonomy "
            "fields. All flags compose with AND semantics."
        )
    )
    p.add_argument("--class", dest="cls", help="exact class match (llm, slm, rlm, …)")
    p.add_argument("--tier", help="exact tier match (pulse, logic, oracle, router)")
    p.add_argument("--engine", help="exact engine match (bitnet.cpp, vllm, …)")
    p.add_argument("--quantization", help="exact quantization match (bf16, fp8, …)")
    p.add_argument(
        "--size-class",
        dest="size_class",
        help="exact size_class match (xs, s, m, l, xl, xxl)",
    )
    p.add_argument(
        "--status",
        help="exact status match (verified-real, aspirational, operator-must-confirm)",
    )
    p.add_argument(
        "--purpose",
        help="must include this purpose tag (chat, reasoning, code, …)",
    )
    p.add_argument(
        "--max-vram",
        dest="max_vram",
        type=float,
        help="exclude models whose vram_gib_min > N (GiB)",
    )
    p.add_argument(
        "--min-context",
        dest="min_context",
        type=int,
        help="require context_window_tokens >= N",
    )
    p.add_argument(
        "--base-model",
        dest="base_model",
        help="filter LoRA adapters by base_model id",
    )
    p.add_argument("--json", action="store_true", help="emit JSON instead of table")

    args = p.parse_args()

    try:
        catalog = load_catalog()
    except FileNotFoundError:
        print(f"ERROR catalog not found at {CATALOG_PATH}", file=sys.stderr)
        return 2

    matches = [m for m in catalog if match(m, args)]

    if args.json:
        print(json.dumps({"count": len(matches), "models": matches}, indent=2))
    else:
        sys.stdout.write(render_table(matches))

    return 0 if matches else 1


if __name__ == "__main__":
    sys.exit(main())
