#!/usr/bin/env python3
"""scripts/operator/generate-runtime-profile.py — SDD-043 Phase 3.

PRODUCES a runtime profile from an OS profile's hardware + a named
strategy, instead of hand-authoring one. This is where the "20+ OS×GPU1×
GPU2 combos" actually come from: the generator reads the declared GPUs
(VRAM) + CPU cores, lays out tiers per the strategy, and emits tier_intent
allocations (Phase 2) sized to the real hardware — then validates the
result against the schema and proves every tier resolves to a real
catalog model.

Strategies (hardware-parameterized; mirror master spec § 18):
  efficiency        CPU-only Pulse (ternary), GPUs throttled — sovereign,
                    low-power.
  high-concurrency  asymmetric: Pulse on CPU + Logic on the smaller GPU +
                    Oracle on the largest GPU — parallel specialist agents.
  deep-context      one big model tensor-parallel across ALL GPUs.

Usage:
  generate-runtime-profile.py --hardware sain-01 --strategy high-concurrency
      [--out profiles/runtime/<id>.yaml]   (default: stdout)
      [--no-validate]                      (skip schema+resolve check)

Exit: 0 ok · 2 usage · 3 a tier does not resolve to any catalog model
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILES_DIR = REPO_ROOT / "profiles"
SCHEMA_FILE = REPO_ROOT / "schemas" / "runtime-profile.schema.yaml"
SELECTOR = REPO_ROOT / "scripts" / "models" / "select-by-intent.py"

VRAM_HEADROOM = 0.90   # leave 10% for framework + KV cache


def _load_yaml(path: Path) -> dict:
    import yaml
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _selector():
    spec = importlib.util.spec_from_file_location("select_by_intent", SELECTOR)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _hardware(os_profile_id: str) -> tuple[list[dict], int]:
    """Return (gpus-in-declaration-order-with-cuda-index, physical-cores)."""
    p = PROFILES_DIR / f"{os_profile_id}.yaml"
    if not p.is_file():
        print(f"error: OS profile not found: {os_profile_id}", file=sys.stderr)
        raise SystemExit(2)
    hw = _load_yaml(p).get("hardware") or {}
    gpus = []
    # SDD-993: `role: future` GPUs (not-yet-installed upgrade paths) get no cuda
    # index and are excluded from allocations. Installed GPUs — primary/secondary
    # (internal) and egpu (OcuLink) — are enumerated. `internal` flags whether a
    # GPU can participate in cross-link tensor-parallel: an OcuLink eGPU (role
    # `egpu`, PCIe 4.0 x4) is fine for single-GPU tiers but is bandwidth-bound for
    # tensor-parallel, so it is excluded from the deep-context TP set.
    present = [g for g in (hw.get("gpu") or []) if g.get("role") != "future"]
    for i, g in enumerate(present):
        gpus.append({"cuda": i, "vram_gb": int(g.get("vram_gb") or 0),
                     "model": g.get("model"), "role": g.get("role"),
                     "internal": g.get("role") != "egpu"})
    cores = ((hw.get("cpu") or {}).get("cores") or {}).get("physical") or 0
    return gpus, int(cores)


def _budget(vram_gb: int) -> float:
    return round(vram_gb * VRAM_HEADROOM, 1)


def _strategy_allocations(strategy: str, gpus: list[dict], cores: int) -> list[dict]:
    core_mask = f"0-{cores - 1}" if cores else "0-0"
    # GPUs largest-VRAM first for tier assignment (oracle → biggest).
    by_vram = sorted(gpus, key=lambda g: -g["vram_gb"])

    if strategy == "efficiency":
        return [{
            "agent_id": "conductor_01", "tier": "pulse",
            "target_hardware": "cpu", "core_mask": core_mask,
            "engine": "bitnet.cpp",
            "tier_intent": {"class": ["ternary-lm", "slm"], "vram_budget_gib": 12},
        }]

    if strategy == "high-concurrency":
        allocs = [{
            "agent_id": "conductor_01", "tier": "pulse",
            "target_hardware": "cpu", "core_mask": core_mask,
            "engine": "bitnet.cpp",
            "tier_intent": {"class": ["ternary-lm", "slm"], "vram_budget_gib": 12},
        }]
        if len(by_vram) >= 2:
            small = by_vram[-1]   # smaller GPU → Logic (translator/coder)
            big = by_vram[0]      # largest GPU → Oracle (deep reasoner)
            allocs.append({
                "agent_id": "translator_01", "tier": "logic",
                "target_hardware": f"cuda:{small['cuda']}", "engine": "vllm",
                "tier_intent": {"class": ["code", "slm", "llm"],
                                "vram_budget_gib": _budget(small["vram_gb"])},
            })
            allocs.append({
                "agent_id": "deep_reasoner_01", "tier": "oracle",
                "target_hardware": f"cuda:{big['cuda']}", "engine": "vllm",
                # `multimodal` included so a 32 GB-class primary (RTX 5090, SDD-993)
                # can still land the master-spec Oracle pick — Nemotron-3-Nano-Omni
                # reasoner — at NVFP4 (24 GiB); on a large card the rlm/llm/mixture
                # reasoners rank ahead of it (spend-the-budget within class order).
                "tier_intent": {"class": ["rlm", "llm", "mixture", "multimodal"],
                                "vram_budget_gib": _budget(big["vram_gb"])},
            })
        elif by_vram:
            big = by_vram[0]
            allocs.append({
                "agent_id": "deep_reasoner_01", "tier": "oracle",
                "target_hardware": f"cuda:{big['cuda']}", "engine": "vllm",
                "tier_intent": {"class": ["rlm", "llm", "multimodal"],
                                "vram_budget_gib": _budget(big["vram_gb"])},
            })
        return allocs

    if strategy == "deep-context":
        # Cross-link tensor-parallel spans the INTERNAL cards only — an OcuLink
        # eGPU (PCIe 4.0 x4) is bandwidth-bound for TP (SDD-993), so exclude it.
        tp_gpus = [g for g in gpus if g.get("internal", True)] or gpus
        if not tp_gpus:
            print("error: deep-context needs at least one GPU", file=sys.stderr)
            raise SystemExit(2)
        total = sum(g["vram_gb"] for g in tp_gpus)
        target = ",".join(f"cuda:{g['cuda']}" for g in sorted(tp_gpus, key=lambda g: g["cuda"]))
        alloc = {
            "agent_id": "deep_reasoner_01", "tier": "oracle",
            "target_hardware": target, "engine": "vllm",
            "tier_intent": {"class": ["llm", "mixture", "rlm"],
                            "vram_budget_gib": _budget(total)},
        }
        if len(tp_gpus) > 1:
            alloc["tensor_parallel_size"] = len(tp_gpus)
        return [alloc]

    print(f"error: unknown strategy '{strategy}' "
          f"(efficiency | high-concurrency | deep-context)", file=sys.stderr)
    raise SystemExit(2)


STRATEGY_DESC = {
    "efficiency": "CPU-only Pulse (ternary) — sovereign low-power; GPUs throttled.",
    "high-concurrency": "Asymmetric: Pulse on CPU + Logic on the smaller GPU + "
                        "Oracle on the largest GPU — parallel specialist agents.",
    "deep-context": "One large model tensor-parallel across all GPUs.",
}


def generate(os_profile_id: str, strategy: str) -> dict:
    gpus, cores = _hardware(os_profile_id)
    allocs = _strategy_allocations(strategy, gpus, cores)
    gpu_note = " · ".join(f"cuda:{g['cuda']}={g['model']}({g['vram_gb']}GB)" for g in gpus) or "no GPU"
    return {
        "schema_version": "1.0.0",
        "runtime_profile": {
            "id": f"{os_profile_id}-{strategy}",
            "name": f"{os_profile_id} · {strategy}",
            "description": (
                f"Generated by scripts/operator/generate-runtime-profile.py "
                f"(SDD-043 P3) from {os_profile_id} hardware [{gpu_note}] with "
                f"the '{strategy}' strategy: {STRATEGY_DESC[strategy]} Models bound "
                f"by tier_intent — resolve with scripts/models/select-by-intent.py."
            ),
            "hardware_profile_compat": [os_profile_id],
            "allocations": allocs,
        },
    }


def validate(profile: dict) -> list[str]:
    """Return a list of problems (empty = valid): schema conformance +
    every tier_intent resolves to a real catalog model."""
    problems: list[str] = []
    try:
        import jsonschema
        schema = _load_yaml(SCHEMA_FILE)
        jsonschema.Draft202012Validator(schema).validate(profile)
    except ImportError:
        pass
    except Exception as e:  # jsonschema.ValidationError
        problems.append(f"schema: {getattr(e, 'message', e)}")
    sel = _selector()
    models = sel.load_catalog()
    for r in sel.resolve_profile(profile, models):
        if r["chosen"] is None:
            problems.append(f"tier {r['agent_id']} ({r['intent']}) resolves to no catalog model")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="generate a runtime profile (SDD-043 P3)")
    ap.add_argument("--hardware", required=True, help="OS profile id (e.g. sain-01)")
    ap.add_argument("--strategy", required=True,
                    choices=["efficiency", "high-concurrency", "deep-context"])
    ap.add_argument("--out", type=Path, help="write here (default: stdout)")
    ap.add_argument("--no-validate", action="store_true")
    args = ap.parse_args(argv)

    import yaml
    profile = generate(args.hardware, args.strategy)

    if not args.no_validate:
        problems = validate(profile)
        if problems:
            for p in problems:
                print(f"  ✗ {p}", file=sys.stderr)
            print("generated profile did NOT validate", file=sys.stderr)
            return 3
        # show the resolved picks so the operator sees what they'll get
        sel = _selector()
        for r in sel.resolve_profile(profile, sel.load_catalog()):
            c = r["chosen"]
            print(f"  # {r['agent_id']} [{r['tier']}] → {c['id']} "
                  f"({c['quantization']}, {c['vram_gib_min']} GiB, {c['status']})",
                  file=sys.stderr)

    text = ("# yaml-language-server: $schema=../../schemas/runtime-profile.schema.yaml\n"
            "# GENERATED — SDD-043 Phase 3. Edit the strategy/generator, not this file,\n"
            "# to regenerate. Models bind by tier_intent (select-by-intent.py resolves).\n"
            + yaml.safe_dump(profile, sort_keys=False, width=100, allow_unicode=True))
    if args.out:
        args.out.write_text(text)
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
