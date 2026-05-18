#!/usr/bin/env python3
"""scripts/models/build.py — R353 (E5.M18).

Operator-named (§1b verbatim, 9-verb AI tools pipeline):
  "download, fine-tune, parameters, build, run, use and train and
   adapt and use and eval"

  download    → R231 model info / scripts/models/pull.sh
  fine-tune   → R244 fine_tune.py
  parameters  → R311 model-params
  BUILD       → R353 (THIS ROUND — was the unfilled verb)
  run         → systemd inference units + R230 inference-processes
  use         → R263 router-status + live API
  train       → R290 lifecycle / R291 workflow
  adapt       → R350 model-adapt
  eval        → R232 model/eval.py

BUILD turns a SET of constituent pieces — base model + LoRA adapter
+ quantization spec + export-format — into a DEPLOYABLE artifact
(merged weights, quantized blob, server-loadable file).

Composes with the rest of the pipeline:
  R350 adapt → picks recipe (recommends method + base)
  R244 fine-tune → produces LoRA adapter
  R353 build → MERGE + QUANTIZE + EXPORT (this script's planner)
  R232 eval → benchmarks the built artifact
  R263 use → loads the artifact behind a router

R353 ships PLANNER scope (SEED, mirrors R232/R244):
  - 4 build-recipe types: merge / quantize-gguf / quantize-awq /
    export-safetensors
  - per-recipe operator-runnable command template (peft / llama.cpp
    convert / autoawq / transformers save_pretrained)
  - cost estimate + VRAM ceiling so operator can pick a target GPU

CLI:
  build.py recipes                                [--json|--human]
  build.py plan <base> --recipe R [--adapter A]   [--config P] [--json|--human]
                                  [--target-gpu N]
  build.py show <recipe>                          [--config P] [--json|--human]
  build.py history                                [--config P] [--json|--human]

Operator-overlay (R283/SDD-030): /etc/sovereign-os/model-build.toml
adds custom recipes or per-host build paths.

Exit codes:
  0  rendered
  1  unknown recipe / unknown base / no GPU fits
  2  usage
"""
from __future__ import annotations

import argparse
import json
import os
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
ROUND = "R353"
SDD_VECTOR = "E5.M18"


# ── Build recipe catalog ──────────────────────────────────────────
#
# Each recipe binds:
#   - recipe_id           short slug
#   - name                human-readable
#   - artifact_kind       what the operator gets at the end
#   - needs_adapter       True if --adapter required
#   - command_template    operator-runnable shell command (placeholders:  # anti-min-waiver: R480 placeholders-here-are-FEATURE-template-substitution-tokens-not-minimization-debt
#                         {base}, {adapter}, {out}, {bits})
#   - min_vram_gib        VRAM needed to RUN the build step
#   - cost_estimate       operator-readable wall-clock for a 7B base
#   - output_extension    expected file suffix
BUILD_RECIPES: list[dict[str, Any]] = [
    {
        "recipe_id": "merge-lora-into-base",
        "name": "Merge LoRA into base (peft)",
        "artifact_kind": "merged-weights",
        "needs_adapter": True,
        "command_template": (
            "python -m peft merge_and_unload --base {base} "
            "--adapter {adapter} --output {out}"
        ),
        "min_vram_gib": 16,
        "cost_estimate": "~5-10 min on RTX 3090 for 7B; ~30 min for 13B",
        "output_extension": ".safetensors (dir)",
        "rationale": ("Folds LoRA delta back into base weights so the "
                       "artifact can be loaded by any standard runtime "
                       "(no peft dependency at inference time)."),
    },
    {
        "recipe_id": "quantize-gguf-q4-k-m",
        "name": "Quantize → GGUF Q4_K_M (llama.cpp)",
        "artifact_kind": "gguf-quantized",
        "needs_adapter": False,
        "command_template": (
            "llama.cpp/convert_hf_to_gguf.py {base} --outfile {out}.f16.gguf"
            " && llama.cpp/llama-quantize {out}.f16.gguf {out}.Q4_K_M.gguf Q4_K_M"
        ),
        "min_vram_gib": 0,  # CPU-only convert
        "cost_estimate": "~15-30 min CPU for 7B; ~60-90 min for 32B",
        "output_extension": ".gguf",
        "rationale": ("Q4_K_M is the operator's default sweet spot: ~4.7 "
                       "bits per weight, ~6 GiB for 7B → fits even pulse "
                       "(bitnet.cpp's CPU lane) or single 24 GiB GPU."),
    },
    {
        "recipe_id": "quantize-awq-int4",
        "name": "Quantize → AWQ INT4 (autoawq)",
        "artifact_kind": "awq-quantized",
        "needs_adapter": False,
        "command_template": (
            "python -m autoawq quantize --model {base} --w-bit 4 "
            "--group-size 128 --output {out}"
        ),
        "min_vram_gib": 24,
        "cost_estimate": "~1-2 hours on RTX 3090 for 7B; ~3-5h for 32B",
        "output_extension": ".safetensors (AWQ dir)",
        "rationale": ("AWQ keeps salient weights in higher precision; "
                       "loaded by vLLM (oracle-core/logic-engine) with "
                       "minimal accuracy loss. Calibration step needed."),
    },
    {
        "recipe_id": "export-safetensors",
        "name": "Export → safetensors (no quantize)",
        "artifact_kind": "fp16-safetensors",
        "needs_adapter": False,
        "command_template": (
            "python -c \"from transformers import AutoModelForCausalLM, "
            "AutoTokenizer; m=AutoModelForCausalLM.from_pretrained('{base}',"
            " torch_dtype='float16'); m.save_pretrained('{out}'); "
            "AutoTokenizer.from_pretrained('{base}').save_pretrained('{out}')\""
        ),
        "min_vram_gib": 0,
        "cost_estimate": "~2-5 min for 7B; ~10-20 min for 32B",
        "output_extension": ".safetensors (dir)",
        "rationale": ("Plain FP16 export — loadable by transformers, vLLM, "
                       "llama.cpp (after convert). No precision loss; "
                       "operator's reference baseline for eval comparisons."),
    },
]


DEFAULT_BUILD_DIR = "/var/lib/sovereign-os/model-builds"
DEFAULT_HISTORY_PATH = "/var/lib/sovereign-os/model-build.jsonl"


# Default GPUs — mirrors R350 but R353 only needs the highest VRAM
# card for can-this-build-run-here decisions.
DEFAULT_GPUS = [
    {"index": 0, "model": "RTX 3090", "vram_gib": 24},
    {"index": 1, "model": "RTX PRO 6000 Blackwell", "vram_gib": 98},
]


# ── Loading + filtering ───────────────────────────────────────────
def load_state(
    overlay_path: Path | None,
) -> tuple[list[dict], list[dict], str, str, dict]:
    """Returns (recipes, gpus, build_dir, history_path, meta)."""
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    recipes = list(BUILD_RECIPES)
    gpus = list(DEFAULT_GPUS)
    build_dir = DEFAULT_BUILD_DIR
    history = DEFAULT_HISTORY_PATH
    if load_with_overlay is not None:
        loaded = load_with_overlay(
            "model-build",
            {"recipes": [], "gpus": [],
             "build_dir": build_dir, "history_path": history},
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
        if loaded.get("build_dir"):
            build_dir = loaded["build_dir"]
        if loaded.get("history_path"):
            history = loaded["history_path"]
    return recipes, gpus, build_dir, history, meta


def resolve_recipe(recipes: list[dict], rid: str) -> dict | None:
    for r in recipes:
        if isinstance(r, dict) and r.get("recipe_id") == rid:
            return r
    return None


def find_fitting_gpu(
    recipe: dict, gpus: list[dict], target_idx: int | None,
) -> dict | None:
    """Pick a GPU that satisfies recipe.min_vram_gib. None when nothing
    fits. min_vram_gib == 0 → any GPU (CPU-only build) is fine."""
    need = int(recipe.get("min_vram_gib", 0))
    if target_idx is not None:
        for g in gpus:
            if g.get("index") == target_idx:
                if g.get("vram_gib", 0) >= need:
                    return g
                return None
        return None
    if need == 0:
        # CPU-only build — return a "cpu" sentinel with arbitrary GPU
        # entry (UX shows operator which card is around).
        return (gpus[0] if gpus else
                {"index": -1, "model": "(cpu-only)", "vram_gib": 0})
    fitting = [g for g in gpus if g.get("vram_gib", 0) >= need]
    if not fitting:
        return None
    # Prefer the highest-VRAM card (least disruption to inference).
    return max(fitting, key=lambda g: g.get("vram_gib", 0))


def render_command(
    recipe: dict, base: str, adapter: str | None, out_path: str,
) -> str:
    cmd = recipe.get("command_template", "")
    return (cmd
            .replace("{base}", base)
            .replace("{adapter}", adapter or "<--adapter required>")
            .replace("{out}", out_path)
            .replace("{bits}", "4"))


def assemble_plan(
    recipe: dict, base: str, adapter: str | None,
    build_dir: str, gpus: list[dict], target_gpu_idx: int | None,
) -> dict[str, Any]:
    if recipe.get("needs_adapter") and not adapter:
        return {
            "ok": False,
            "error": (f"recipe '{recipe['recipe_id']}' needs --adapter; "
                       f"none provided"),
        }
    gpu = find_fitting_gpu(recipe, gpus, target_gpu_idx)
    if gpu is None:
        return {
            "ok": False,
            "error": (f"no GPU fits recipe min_vram_gib="
                       f"{recipe.get('min_vram_gib')} "
                       f"(declared: {[g.get('model') for g in gpus]})"),
        }
    out_slug = (f"{base.replace('/', '_')}-"
                f"{recipe['recipe_id']}").lower()
    out_path = str(Path(build_dir) / out_slug)
    return {
        "ok": True,
        "recipe_id": recipe["recipe_id"],
        "name": recipe.get("name"),
        "artifact_kind": recipe.get("artifact_kind"),
        "base": base,
        "adapter": adapter,
        "fits_on_gpu_index": gpu.get("index"),
        "fits_on_gpu_model": gpu.get("model"),
        "min_vram_gib": recipe.get("min_vram_gib"),
        "output_path": out_path,
        "output_extension": recipe.get("output_extension"),
        "cost_estimate": recipe.get("cost_estimate"),
        "rationale": recipe.get("rationale"),
        "command": render_command(recipe, base, adapter, out_path),
        "downstream_verbs": [
            f"sovereign-osctl model-eval plan {out_slug} "
            f"--benchmark <benchmark-name>",
            f"# (after eval passes) wire into router via "
            f"/etc/sovereign-os/inference-*.env model_path={out_path}",
        ],
    }


def _read_history(path: str) -> list[dict]:
    p = Path(path)
    if not p.is_file():
        return []
    out = []
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    except OSError:
        return []
    return out


# ── Main ──────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="build.py")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("recipes")
    pr.add_argument("--config", type=Path)
    prg = pr.add_mutually_exclusive_group()
    prg.add_argument("--json", dest="fmt", action="store_const", const="json")
    prg.add_argument("--human", dest="fmt", action="store_const", const="human")
    pr.set_defaults(fmt="json")

    pp = sub.add_parser("plan")
    pp.add_argument("base")
    pp.add_argument("--recipe", required=True)
    pp.add_argument("--adapter", default=None)
    pp.add_argument("--target-gpu", dest="target_gpu", type=int, default=None)
    pp.add_argument("--config", type=Path)
    ppg = pp.add_mutually_exclusive_group()
    ppg.add_argument("--json", dest="fmt", action="store_const", const="json")
    ppg.add_argument("--human", dest="fmt", action="store_const", const="human")
    pp.set_defaults(fmt="json")

    ps = sub.add_parser("show")
    ps.add_argument("recipe")
    ps.add_argument("--config", type=Path)
    psg = ps.add_mutually_exclusive_group()
    psg.add_argument("--json", dest="fmt", action="store_const", const="json")
    psg.add_argument("--human", dest="fmt", action="store_const", const="human")
    ps.set_defaults(fmt="json")

    ph = sub.add_parser("history")
    ph.add_argument("--config", type=Path)
    phg = ph.add_mutually_exclusive_group()
    phg.add_argument("--json", dest="fmt", action="store_const", const="json")
    phg.add_argument("--human", dest="fmt", action="store_const", const="human")
    ph.set_defaults(fmt="json")

    args = p.parse_args(argv)
    recipes, gpus, build_dir, history, meta = load_state(
        getattr(args, "config", None))

    if args.cmd == "recipes":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "recipe_count": len(recipes),
                "recipes": recipes,
                "build_dir": build_dir,
                "declared_gpus": gpus,
                "overlay": meta,
            }, indent=2))
        else:
            print("── R353 model-build recipes (E5.M18) ──")
            for r in recipes:
                if not isinstance(r, dict):
                    continue
                print(f"  {r.get('recipe_id', '?'):28s} → "
                      f"{r.get('artifact_kind', '?')} "
                      f"(need {r.get('min_vram_gib', 0):>2} GiB VRAM)")
        return 0

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
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R353 build recipe: {r['recipe_id']} (E5.M18) ──")
            for k, v in r.items():
                if k == "recipe_id":
                    continue
                print(f"  {k}: {v}")
        return 0

    if args.cmd == "plan":
        r = resolve_recipe(recipes, args.recipe)
        if r is None:
            print(json.dumps({
                "error": f"unknown recipe: {args.recipe}",
                "known": [x.get("recipe_id") for x in recipes
                          if isinstance(x, dict)],
                "round": ROUND,
            }, indent=2), file=sys.stderr)
            return 1
        plan = assemble_plan(
            r, args.base, args.adapter, build_dir, gpus, args.target_gpu)
        out = {
            "schema_version": SCHEMA_VERSION,
            "round": ROUND,
            "sdd_vector": SDD_VECTOR,
            **plan,
            "overlay": meta,
        }
        if args.fmt == "json":
            print(json.dumps(out, indent=2))
        else:
            if not plan["ok"]:
                print(f"── R353 build plan: FAILED ──")
                print(f"  error: {plan['error']}")
            else:
                print(f"── R353 build plan: {plan['recipe_id']} (E5.M18) ──")
                print(f"  base:        {plan['base']}")
                if plan.get('adapter'):
                    print(f"  adapter:     {plan['adapter']}")
                print(f"  artifact:    {plan['artifact_kind']}")
                print(f"  fits on:     GPU{plan['fits_on_gpu_index']} "
                      f"({plan['fits_on_gpu_model']})")
                print(f"  output:      {plan['output_path']}{plan['output_extension']}")
                print(f"  cost:        {plan['cost_estimate']}")
                print(f"  why:         {plan['rationale']}")
                print(f"  command:")
                print(f"    $ {plan['command']}")
                print(f"  next steps:")
                for v in plan.get("downstream_verbs") or []:
                    print(f"    $ {v}")
        return 0 if plan.get("ok") else 1

    if args.cmd == "history":
        entries = _read_history(history)
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "history_path": history,
                "entry_count": len(entries),
                "entries": entries,
            }, indent=2))
        else:
            print(f"── R353 model-build history ({len(entries)} entries) ──")
            if not entries:
                print(f"  (empty — {history} does not exist or is blank)")
            for e in entries[-10:]:
                print(f"  {e.get('time', '?')} "
                      f"recipe={e.get('recipe_id', '?')} "
                      f"base={e.get('base', '?')} → "
                      f"{e.get('output_path', '?')}")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
