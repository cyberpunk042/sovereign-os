#!/usr/bin/env python3
"""scripts/models/select-by-intent.py — SDD-043 Phase 2: VRAM-aware model selection.

Resolves a runtime-profile allocation's `tier_intent` block (declare WHAT
kind of model a tier wants + how much VRAM it may spend) into a concrete
model from models/catalog.yaml. This is the connective tissue that lets a
profile say "oracle tier = an rlm within 48 GB" instead of hardcoding
`DeepSeek-R1-Distill-Llama-70B-Q4_K_M` — so 20+ OS×GPU1×GPU2 combos need
not hand-pin every model.

Ranking (deterministic): among catalog models whose class is in the
intent, whose vram_gib_min fits the budget, and (if given) whose tier /
purpose / min-context match —
  1. prefer=verified-real → verified-real models first (aspirational only
     if none real fit);
  2. then MAXIMISE vram_gib_min (spend the budget: the biggest model that
     fits is the most capable);
  3. then larger context window;
  4. then class preference order in the intent;
  5. then id (stable tie-break).

Usage:
  select-by-intent.py --class rlm[,llm] --vram 48 [--tier oracle]
                      [--purpose reasoning] [--min-context 32768]
                      [--prefer verified-real|any] [--json]
  select-by-intent.py --profile profiles/runtime/<id>.yaml   # resolve all

Exit: 0 chosen · 3 no catalog model satisfies the intent · 2 usage/error
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG = REPO_ROOT / "models" / "catalog.yaml"

CLASS_ENUM = {"llm", "slm", "rlm", "ternary-lm", "lora-adapter", "embed",
              "vision", "multimodal", "code", "mixture", "speculative", "reranker"}


def _load_yaml(path: Path) -> dict:
    import yaml
    with open(path) as f:
        return yaml.safe_load(f) or {}


def load_catalog(path: Path | None = None) -> list[dict]:
    doc = _load_yaml(path or CATALOG)
    return (doc.get("catalog") or {}).get("models") or []


def select(models: list[dict], intent: dict, tier: str | None = None) -> dict | None:
    """Return the best catalog model for a tier_intent, or None."""
    classes: list[str] = list(intent.get("class") or [])
    budget = float(intent.get("vram_budget_gib", 0) or 0)
    want_purpose = set(intent.get("purpose") or [])
    min_ctx = int(intent.get("min_context_tokens") or 0)
    prefer = intent.get("prefer", "verified-real")

    def eligible(m: dict) -> bool:
        if m.get("class") not in classes:
            return False
        vram = m.get("vram_gib_min")
        if vram is None or float(vram) > budget:
            return False
        if tier is not None and m.get("tier") != tier:
            return False
        if want_purpose and not (want_purpose & set(m.get("purpose") or [])):
            return False
        if min_ctx and int(m.get("context_window_tokens") or 0) < min_ctx:
            return False
        return True

    cands = [m for m in models if eligible(m)]
    if not cands:
        return None

    class_rank = {c: i for i, c in enumerate(classes)}

    def sort_key(m: dict):
        real = 0 if m.get("status") == "verified-real" else 1
        return (
            real,                                              # verified-real first
            -float(m.get("vram_gib_min") or 0),                # spend the budget
            -int(m.get("context_window_tokens") or 0),         # more context
            class_rank.get(m.get("class"), len(classes)),      # class preference
            str(m.get("id")),                                  # stable
        )

    ordered = sorted(cands, key=sort_key)
    if prefer == "verified-real":
        real = [m for m in ordered if m.get("status") == "verified-real"]
        if real:
            return real[0]
    return ordered[0]


def resolve_profile(profile: dict, models: list[dict]) -> list[dict]:
    """Resolve every tier_intent allocation in a runtime profile. Returns a
    list of {agent_id, tier, intent, chosen|None}."""
    rp = profile.get("runtime_profile") or {}
    out = []
    for alloc in rp.get("allocations") or []:
        intent = alloc.get("tier_intent")
        if not intent:
            continue
        chosen = select(models, intent, tier=alloc.get("tier"))
        out.append({
            "agent_id": alloc.get("agent_id"),
            "tier": alloc.get("tier"),
            "intent": intent,
            "chosen": chosen,
        })
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="VRAM-aware model selection (SDD-043 P2)")
    ap.add_argument("--profile", help="resolve every tier_intent in a runtime profile")
    ap.add_argument("--class", dest="klass", help="comma-separated class preference")
    ap.add_argument("--vram", type=float, help="VRAM budget (GiB)")
    ap.add_argument("--tier", choices=["pulse", "logic", "oracle", "router"])
    ap.add_argument("--purpose", help="comma-separated purpose tags (any-of)")
    ap.add_argument("--min-context", type=int, default=0)
    ap.add_argument("--prefer", choices=["verified-real", "any"], default="verified-real")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--catalog", type=Path, default=CATALOG)
    args = ap.parse_args(argv)

    models = load_catalog(args.catalog)

    if args.profile:
        prof = _load_yaml(Path(args.profile))
        resolved = resolve_profile(prof, models)
        if args.json:
            print(json.dumps(resolved, indent=2))
        else:
            for r in resolved:
                c = r["chosen"]
                pick = f"{c['id']} ({c['quantization']}, {c['vram_gib_min']} GiB, {c['status']})" if c else "NO FIT"
                print(f"  {r['agent_id']} [{r['tier']}] intent {r['intent'].get('class')} "
                      f"<= {r['intent'].get('vram_budget_gib')} GiB → {pick}")
        return 0 if all(r["chosen"] for r in resolved) else 3

    if not args.klass or args.vram is None:
        ap.error("provide --class and --vram (or --profile)")
    intent = {
        "class": args.klass.split(","),
        "vram_budget_gib": args.vram,
        "purpose": args.purpose.split(",") if args.purpose else [],
        "min_context_tokens": args.min_context,
        "prefer": args.prefer,
    }
    chosen = select(models, intent, tier=args.tier)
    if chosen is None:
        print("no catalog model satisfies the intent", file=sys.stderr)
        return 3
    if args.json:
        print(json.dumps(chosen, indent=2))
    else:
        print(f"{chosen['id']}  ({chosen['class']}, {chosen['quantization']}, "
              f"{chosen['vram_gib_min']} GiB, {chosen['status']}, tier={chosen['tier']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
