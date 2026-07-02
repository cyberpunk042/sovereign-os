#!/usr/bin/env python3
"""scripts/models/adapt.py — R350 (E5.M17).

Operator-named (§1b verbatim hook drop):
  "AI and the tools but also download, fine-tune, parameters, build,
   run, use and train and adapt and use and eval and etc."

R231 ships INFO (model metadata). R232 ships EVAL planner. R244
ships FINE-TUNE planner. R350 ships ADAPT — the operator's word for
"given a target TASK, recommend (base model, adaptation method,
target GPU) that fits MY hardware right now."

ADAPT is upstream of EVAL+FINE-TUNE: operator picks a task → R350
recommends a recipe → operator hands off to R244 fine-tune plan →
operator hands off to R232 eval plan → operator decides to promote.

Recommendations are hardware-aware: VRAM ceiling per card pulled
from R317 inventory-catalog via R348 inventory_consult helper.
RTX 4090 (24 GiB) and RTX PRO 6000 (98 GiB) get DIFFERENT
recommendations for the same task.

CLI:
  adapt.py tasks                 [--json|--human]
  adapt.py recipes               [--json|--human]
  adapt.py recommend <task>      [--target-gpu N] [--config P] [--json|--human]
  adapt.py show <recipe>         [--config P] [--json|--human]

Operator-overlay (R283/SDD-030): /etc/sovereign-os/model-adapt.toml
— operator can extend recipes / tasks / per-card overrides.

Exit codes:
  0  rendered
  1  unknown task / unknown recipe / no recipe fits target GPU
  2  usage
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
try:
    # R350 — third consumer of SDD-032 §4 helper (after R315, R252).
    from inventory_consult import find_advisor_caveats  # type: ignore
except Exception:  # pragma: no cover
    find_advisor_caveats = None


SCHEMA_VERSION = "1.0.0"
ROUND = "R350"
SDD_VECTOR = "E5.M17"


# ── Recipe catalog ────────────────────────────────────────────────
#
# Each recipe binds:
#   - recipe_id           short slug operator references
#   - base_class          base model family + size class
#   - min_vram_gib        VRAM the recipe needs to RUN inference
#   - finetune_vram_gib   additional VRAM for the fine-tune method
#   - method              adaptation method (lora / qlora / sft / dpo)
#   - target_tasks        which tasks this recipe fits
#   - cost_estimate       operator-readable (~hours of fine-tune on the
#                         declared GPU under typical 1k-row dataset)
#   - rationale           WHY operator should pick this for the task
RECIPES: list[dict[str, Any]] = [
    {
        "recipe_id": "qlora-7b-codegen",
        "base_class": "code-llama-7b OR qwen2.5-coder-7b",
        "min_vram_gib": 6,
        "finetune_vram_gib": 16,
        "method": "qlora-trl",
        "target_tasks": ["code", "agent", "tool-use"],
        "cost_estimate": "~2-4h on RTX 4090 (24 GiB) at 1k rows",
        "rationale": ("7B code model + qlora 4-bit fits the 4090; ideal "
                       "for operator-specific tool-use fine-tunes without "
                       "displacing oracle-core."),
    },
    {
        "recipe_id": "lora-13b-chat",
        "base_class": "llama-3-13b OR mistral-13b",
        "min_vram_gib": 12,
        "finetune_vram_gib": 22,
        "method": "lora-unsloth",
        "target_tasks": ["chat", "instruction-following"],
        "cost_estimate": "~3-5h on RTX 4090 (24 GiB) at 2k rows",
        "rationale": ("13B chat model + lora unsloth FA2 path is the "
                       "sweet spot for the 4090; oracle-core stays free."),
    },
    {
        "recipe_id": "qlora-32b-reasoning",
        "base_class": "qwen2.5-32b OR mistral-small-2503",
        "min_vram_gib": 22,
        "finetune_vram_gib": 48,
        "method": "qlora-trl",
        "target_tasks": ["reasoning", "math", "long-context"],
        "cost_estimate": "~6-10h on RTX PRO 6000 (98 GiB) at 1k rows",
        "rationale": ("32B reasoning model: PRO 6000 has the VRAM for "
                       "qlora + long-context windows. Won't fit on 4090 "
                       "during fine-tune."),
    },
    {
        "recipe_id": "lora-70b-instruct",
        "base_class": "llama-3.3-70b-instruct",
        "min_vram_gib": 40,
        "finetune_vram_gib": 90,
        "method": "lora-unsloth",
        "target_tasks": ["instruction-following", "chat", "agent"],
        "cost_estimate": "~12-20h on RTX PRO 6000 (98 GiB) at 1k rows",
        "rationale": ("70B instruct + lora unsloth saturates PRO 6000 "
                       "VRAM; operator should pause logic-engine "
                       "(4090 VFIO) workloads during the run."),
    },
    {
        "recipe_id": "sft-3b-edge",
        "base_class": "qwen2.5-3b OR phi-3.5-mini",
        "min_vram_gib": 3,
        "finetune_vram_gib": 8,
        "method": "sft-trl",
        "target_tasks": ["chat", "edge", "fast-iteration"],
        "cost_estimate": "~1-2h on either GPU at 1k rows",
        "rationale": ("3B SFT runs anywhere; ideal for fast iteration "
                       "loops or pulse co-routine."),
    },
    {
        "recipe_id": "dpo-preference",
        "base_class": "any already-fine-tuned model from above",
        "min_vram_gib": 6,
        "finetune_vram_gib": 24,
        "method": "dpo-trl",
        "target_tasks": ["alignment", "preference-tune", "rlhf-lite"],
        "cost_estimate": "~3-6h depending on base + dataset",
        "rationale": ("DPO refines an already-fine-tuned base — second "
                       "pass after one of the above lora/qlora runs. "
                       "Operator-specified preference pairs in JSONL."),
    },
]


# Default GPU VRAM map. Operator overlay can replace; live nvidia-smi
# is the source of truth but this default mirrors the SAIN-01 catalog.
DEFAULT_GPUS: list[dict[str, Any]] = [
    {
        "index": 0,
        "model": "RTX 4090",
        "vram_gib": 24,
        "role_hint": "VFIO sandbox (logic-engine when active)",
    },
    {
        "index": 1,
        "model": "RTX PRO 6000 Blackwell",
        "vram_gib": 98,
        "role_hint": "host (oracle-core); operator's heavy-lift card",
    },
]


# Tasks operator picks from. Keep tight — these are operator-meaningful
# categories, not arbitrary text. Operator overlay can add more.
TASK_CATALOG = (
    "chat", "instruction-following", "code", "agent", "tool-use",
    "reasoning", "math", "long-context", "edge", "fast-iteration",
    "alignment", "preference-tune", "rlhf-lite",
)


# ── Loading + filtering ───────────────────────────────────────────
def load_state(
    overlay_path: Path | None,
) -> tuple[list[dict], list[dict], dict]:
    """Returns (recipes, gpus, meta)."""
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    recipes = list(RECIPES)
    gpus = list(DEFAULT_GPUS)
    if load_with_overlay is not None:
        loaded = load_with_overlay(
            "model-adapt",
            {"recipes": [], "gpus": []},
            explicit_path=overlay_path,
        )
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]
        if loaded.get("recipes"):
            recipes = list(loaded["recipes"])
        if loaded.get("gpus"):
            gpus = list(loaded["gpus"])
    return recipes, gpus, meta


def resolve_recipe(recipes: list[dict], rid: str) -> dict | None:
    for r in recipes:
        if isinstance(r, dict) and r.get("recipe_id") == rid:
            return r
    return None


def _gpu_caveats() -> list[dict[str, Any]]:
    """Catalog caveats for the GPU/PCIe slots — R350 is the 3rd
    consumer of SDD-032 §4 helper (after R315, R252)."""
    if find_advisor_caveats is None:
        return []
    # R317 catalog gpu-pcie entries tag related_advisor with the
    # advisors that READ them (R315, R311) — not R350. So we
    # pull ALL gpu-pcie caveats via a known adjacent advisor's tag.
    try:
        return [c for c in find_advisor_caveats("R315")
                if c.get("category") in ("gpu-pcie", "pcie")]
    except Exception:
        return []


def recommend_for_task(
    task: str, recipes: list[dict], gpus: list[dict],
    target_gpu_index: int | None = None,
) -> dict[str, Any]:
    """Pick the best recipe(s) for the task, ranked by VRAM fit on
    the operator's available GPUs."""
    task_l = task.lower()
    candidates = [r for r in recipes
                  if isinstance(r, dict)
                  and task_l in [t.lower()
                                  for t in (r.get("target_tasks") or [])]]
    if not candidates:
        return {
            "task": task,
            "matches": 0,
            "recommendation": None,
            "alternatives": [],
            "reason": (f"no recipe in catalog targets task='{task}'; "
                        f"known tasks: {list(TASK_CATALOG)}"),
        }
    if target_gpu_index is not None:
        target_gpus = [g for g in gpus if g.get("index") == target_gpu_index]
        if not target_gpus:
            return {
                "task": task,
                "matches": len(candidates),
                "recommendation": None,
                "alternatives": [r.get("recipe_id") for r in candidates],
                "reason": (f"target GPU index={target_gpu_index} not "
                            f"found in declared GPUs; known indices: "
                            f"{[g.get('index') for g in gpus]}"),
            }
    else:
        target_gpus = gpus
    # For each candidate, find the highest-VRAM GPU it fits into during
    # fine-tune (most operator-meaningful threshold).
    scored: list[dict] = []
    for r in candidates:
        ft = r.get("finetune_vram_gib", 0)
        fit_gpus = [g for g in target_gpus
                    if g.get("vram_gib", 0) >= ft]
        if not fit_gpus:
            continue
        # Aggressiveness score = higher VRAM consumed = larger model.
        target = max(fit_gpus, key=lambda g: g.get("vram_gib", 0))
        scored.append({
            "recipe_id": r.get("recipe_id"),
            "base_class": r.get("base_class"),
            "method": r.get("method"),
            "min_vram_gib": r.get("min_vram_gib"),
            "finetune_vram_gib": r.get("finetune_vram_gib"),
            "fits_on_gpu_index": target.get("index"),
            "fits_on_gpu_model": target.get("model"),
            "fits_headroom_gib": target.get("vram_gib", 0) - ft,
            "cost_estimate": r.get("cost_estimate"),
            "rationale": r.get("rationale"),
        })
    if not scored:
        return {
            "task": task,
            "matches": len(candidates),
            "recommendation": None,
            "alternatives": [r.get("recipe_id") for r in candidates],
            "reason": (f"no candidate fits finetune_vram_gib on declared "
                        f"GPUs (max VRAM: "
                        f"{max((g.get('vram_gib', 0) for g in target_gpus), default=0)} GiB)"),
        }
    # Recommend the largest-fitting recipe (operator-most-aggressive).
    scored.sort(key=lambda s: s["finetune_vram_gib"], reverse=True)
    rec = scored[0]
    return {
        "task": task,
        "matches": len(candidates),
        "recommendation": rec,
        "alternatives": [s["recipe_id"] for s in scored[1:]],
        "downstream_verbs": [
            f"sovereign-osctl fine-tune plan <base-of-{rec['base_class']}> "
            f"--method {rec['method']} --dataset <your-dataset>",
            f"sovereign-osctl eval plan <slug-after-finetune> "
            f"--benchmark <benchmark-name>",
        ],
    }


# ── Renderers ─────────────────────────────────────────────────────
def render_recommend_human(rec_doc: dict) -> str:
    lines = [f"── R350 model-adapt recommend: task={rec_doc.get('task')} (E5.M17) ──"]
    rec = rec_doc.get("recommendation")
    if rec is None:
        lines.append(f"  recommendation: NONE")
        lines.append(f"  reason: {rec_doc.get('reason')}")
        if rec_doc.get("alternatives"):
            lines.append(f"  alternatives (no-fit): "
                          f"{rec_doc['alternatives']}")
        return "\n".join(lines) + "\n"
    lines.append(f"  ⮕ recipe:    {rec['recipe_id']}")
    lines.append(f"    base:      {rec['base_class']}")
    lines.append(f"    method:    {rec['method']}")
    lines.append(f"    VRAM:      {rec['min_vram_gib']} GiB to run / "
                  f"{rec['finetune_vram_gib']} GiB to fine-tune")
    lines.append(f"    fits on:   GPU{rec['fits_on_gpu_index']} "
                  f"({rec['fits_on_gpu_model']}; "
                  f"+{rec['fits_headroom_gib']} GiB headroom)")
    lines.append(f"    cost:      {rec['cost_estimate']}")
    lines.append(f"    why:       {rec['rationale']}")
    if rec_doc.get("alternatives"):
        lines.append(f"  alternatives: {rec_doc['alternatives']}")
    lines.append(f"  next steps:")
    for v in rec_doc.get("downstream_verbs") or []:
        lines.append(f"    $ {v}")
    return "\n".join(lines) + "\n"


# ── Main ──────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="adapt.py")
    sub = p.add_subparsers(dest="cmd", required=True)

    pt = sub.add_parser("tasks")
    ptg = pt.add_mutually_exclusive_group()
    ptg.add_argument("--json", dest="fmt", action="store_const", const="json")
    ptg.add_argument("--human", dest="fmt", action="store_const", const="human")
    pt.set_defaults(fmt="json")

    pr = sub.add_parser("recipes")
    pr.add_argument("--config", type=Path)
    prg = pr.add_mutually_exclusive_group()
    prg.add_argument("--json", dest="fmt", action="store_const", const="json")
    prg.add_argument("--human", dest="fmt", action="store_const", const="human")
    pr.set_defaults(fmt="json")

    prec = sub.add_parser("recommend")
    prec.add_argument("task")
    prec.add_argument("--target-gpu", type=int, default=None,
                       dest="target_gpu")
    prec.add_argument("--config", type=Path)
    precg = prec.add_mutually_exclusive_group()
    precg.add_argument("--json", dest="fmt", action="store_const", const="json")
    precg.add_argument("--human", dest="fmt", action="store_const", const="human")
    prec.set_defaults(fmt="json")

    ps = sub.add_parser("show")
    ps.add_argument("recipe")
    ps.add_argument("--config", type=Path)
    psg = ps.add_mutually_exclusive_group()
    psg.add_argument("--json", dest="fmt", action="store_const", const="json")
    psg.add_argument("--human", dest="fmt", action="store_const", const="human")
    ps.set_defaults(fmt="json")

    args = p.parse_args(argv)
    recipes, gpus, meta = load_state(getattr(args, "config", None))
    gpu_caveats = _gpu_caveats()

    if args.cmd == "tasks":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "tasks": list(TASK_CATALOG),
                "task_count": len(TASK_CATALOG),
            }, indent=2))
        else:
            print("── R350 model-adapt tasks (E5.M17) ──")
            for t in TASK_CATALOG:
                print(f"  - {t}")
        return 0

    if args.cmd == "recipes":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "recipe_count": len(recipes),
                "recipes": recipes,
                "declared_gpus": gpus,
                "gpu_caveats": gpu_caveats,
                "overlay": meta,
            }, indent=2))
        else:
            print("── R350 model-adapt recipes (E5.M17) ──")
            for r in recipes:
                if not isinstance(r, dict):
                    continue
                print(f"  {r.get('recipe_id', '?'):28s} "
                      f"({r.get('finetune_vram_gib', '?'):>3} GiB FT) "
                      f"→ tasks: {','.join(r.get('target_tasks') or [])}")
        return 0

    if args.cmd == "recommend":
        rec_doc = recommend_for_task(
            args.task, recipes, gpus,
            target_gpu_index=args.target_gpu,
        )
        out = {
            "schema_version": SCHEMA_VERSION,
            "round": ROUND,
            "sdd_vector": SDD_VECTOR,
            **rec_doc,
            "declared_gpus": gpus,
            "gpu_caveats": gpu_caveats,
            "overlay": meta,
        }
        if args.fmt == "json":
            print(json.dumps(out, indent=2))
        else:
            print(render_recommend_human(rec_doc), end="")
        return 0 if rec_doc.get("recommendation") else 1

    if args.cmd == "show":
        r = resolve_recipe(recipes, args.recipe)
        if r is None:
            print(json.dumps({
                "error": f"unknown recipe: {args.recipe}",
                "known": [x.get("recipe_id") for x in recipes
                          if isinstance(x, dict)],
                "round": ROUND,
            }, indent=2), file=sys.stderr)
            return 1
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "recipe": r,
                "declared_gpus": gpus,
                "gpu_caveats": gpu_caveats,
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R350 recipe: {r['recipe_id']} (E5.M17) ──")
            for k, v in r.items():
                if k == "recipe_id":
                    continue
                print(f"  {k}: {v}")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
