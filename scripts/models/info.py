#!/usr/bin/env python3
"""scripts/models/info.py — R231 (SDD-026 Z-2).

Operator-named (verbatim, 2026-05-17 expansion): "you can browse too
with all the models and all their variant and quantization options
and advanced features options and parametrization and all".

LM-Studio-equivalent detail surface for one catalog entry. R213
ships `models query` (catalog filter); R231 ships `models info <slug>`
which surfaces EVERYTHING the catalog declares about one model:

  Identity        id, hf_repo_id, license, status
  Classification  class, quantization, size_class, tier, purpose
  Footprint       parameters_millions, vram_gib_min, context_window_tokens
  Runtime         engine, runtime_profile_bindings, master_spec_section
  Operator        operator_note (verbatim guidance)
  Variants        other catalog entries sharing purpose tags
  LoRA adapters   catalog entries whose base_model == this slug
  Actions         the pull/verify/suggest commands the operator runs next

Drives the dashboard's "model detail" panel (R227 catalog browse
links one click into this view).

CLI:
  info.py <slug>             human-readable banner
  info.py <slug> --json      machine-readable JSON for the dashboard

Slug matching is case-insensitive + accepts hf_repo_id substring as
a fallback (operators paste a HF URL fragment and the script resolves).

Exit codes:
  0  slug resolved + detail rendered
  2  unknown slug / usage error
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    print("ERROR PyYAML missing — install with `pip install PyYAML`", file=sys.stderr)
    sys.exit(2)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG = REPO_ROOT / "models" / "catalog.yaml"


def load_catalog(path: Path) -> list[dict[str, Any]]:
    with path.open() as fh:
        doc = yaml.safe_load(fh)
    cat = doc.get("catalog") or {}
    return cat.get("models") or []


def resolve_slug(models: list[dict[str, Any]], slug: str) -> dict[str, Any] | None:
    """Case-insensitive id match; falls back to hf_repo_id substring."""
    s = slug.lower()
    for m in models:
        if m.get("id", "").lower() == s:
            return m
    for m in models:
        if s in (m.get("hf_repo_id") or "").lower():
            return m
    return None


def find_variants(
    models: list[dict[str, Any]], target: dict[str, Any]
) -> list[dict[str, Any]]:
    """Other models that share at least one purpose tag with target."""
    tgt_id = target.get("id")
    tgt_purposes = set(target.get("purpose") or [])
    if not tgt_purposes:
        return []
    out = []
    for m in models:
        if m.get("id") == tgt_id:
            continue
        if set(m.get("purpose") or []) & tgt_purposes:
            out.append(m)
    return out


def find_lora_adapters(
    models: list[dict[str, Any]], target: dict[str, Any]
) -> list[dict[str, Any]]:
    """Catalog entries declaring base_model == target id (LoRA targets)."""
    tgt_id = target.get("id")
    if not tgt_id:
        return []
    return [
        m
        for m in models
        if m.get("class") == "lora-adapter" and m.get("base_model") == tgt_id
    ]


def build_detail(models: list[dict[str, Any]], target: dict[str, Any]) -> dict[str, Any]:
    variants = find_variants(models, target)
    adapters = find_lora_adapters(models, target)
    return {
        "round": "R231",
        "vector": "SDD-026 Z-2 (model detail)",
        "model": {
            "id": target.get("id"),
            "hf_repo_id": target.get("hf_repo_id"),
            "license": target.get("license"),
            "status": target.get("status"),
            "class": target.get("class"),
            "quantization": target.get("quantization"),
            "size_class": target.get("size_class"),
            "tier": target.get("tier"),
            "purpose": target.get("purpose") or [],
            "engine": target.get("engine"),
            "parameters_millions": target.get("parameters_millions"),
            "vram_gib_min": target.get("vram_gib_min"),
            "context_window_tokens": target.get("context_window_tokens"),
            "runtime_profile_bindings": target.get("runtime_profile_bindings") or [],
            "master_spec_section": target.get("master_spec_section"),
            "operator_note": target.get("operator_note"),
            "base_model": target.get("base_model"),
            "closest_real_alternative": target.get("closest_real_alternative"),
        },
        "variants": [
            {
                "id": v.get("id"),
                "class": v.get("class"),
                "quantization": v.get("quantization"),
                "size_class": v.get("size_class"),
                "vram_gib_min": v.get("vram_gib_min"),
                "shared_purpose": sorted(
                    set(v.get("purpose") or []) & set(target.get("purpose") or [])
                ),
            }
            for v in variants
        ],
        "lora_adapters": [
            {
                "id": a.get("id"),
                "hf_repo_id": a.get("hf_repo_id"),
                "purpose": a.get("purpose") or [],
            }
            for a in adapters
        ],
        "actions": {
            "pull": f"scripts/models/pull.sh {target.get('id')}",
            "verify": f"scripts/models/verify.sh {target.get('id')}",
            "suggest_for_active_profile":
                "sovereign-osctl models suggest --runtime-profile "
                "high-concurrency-burst",
        },
    }


def render_human(detail: dict[str, Any]) -> str:
    out: list[str] = []
    m = detail["model"]
    out.append(f"── R231 sovereign-os models info — {m['id']} (SDD-026 Z-2) ──")
    out.append("")
    out.append("  IDENTITY")
    out.append(f"    id:            {m['id']}")
    out.append(f"    hf_repo_id:    {m['hf_repo_id'] or '(none)'}")
    out.append(f"    license:       {m['license'] or '(unspecified)'}")
    out.append(f"    status:        {m['status']}")
    out.append("")
    out.append("  CLASSIFICATION")
    out.append(f"    class:         {m['class']}")
    out.append(f"    quantization:  {m['quantization']}")
    out.append(f"    size_class:    {m['size_class']}")
    out.append(f"    tier:          {m['tier']}")
    out.append(f"    purpose:       {', '.join(m['purpose']) or '(none)'}")
    if m.get("base_model"):
        out.append(f"    base_model:    {m['base_model']}  (LoRA adapter target)")
    if m.get("closest_real_alternative"):
        out.append(
            f"    alternative:   {m['closest_real_alternative']}  "
            "(aspirational entry — see operator_note)"
        )
    out.append("")
    out.append("  FOOTPRINT")
    pm = m["parameters_millions"]
    if pm is not None:
        param_str = f"{pm:.1f}M" if pm < 1000 else f"{pm/1000:.2f}B"
    else:
        param_str = "(unknown)"
    out.append(f"    parameters:    {param_str}")
    out.append(f"    vram_gib_min:  {m['vram_gib_min']}")
    out.append(f"    context_tokens:{m['context_window_tokens']}")
    out.append("")
    out.append("  RUNTIME")
    out.append(f"    engine:        {m['engine'] or '(unspecified)'}")
    bindings = m["runtime_profile_bindings"]
    out.append(
        f"    profile_bind:  {', '.join(bindings) if bindings else '(none)'}"
    )
    if m.get("master_spec_section"):
        out.append(f"    master_spec:   {m['master_spec_section']}")
    out.append("")
    if m.get("operator_note"):
        out.append("  OPERATOR NOTE")
        for line in (m["operator_note"] or "").splitlines():
            out.append(f"    {line}")
        out.append("")
    if detail["variants"]:
        out.append(f"  VARIANTS ({len(detail['variants'])} — same purpose tag)")
        for v in detail["variants"][:8]:
            out.append(
                f"    · {v['id']}  [{v['class']} / {v['quantization']} / "
                f"{v['size_class']}]  vram≥{v['vram_gib_min']}"
            )
        if len(detail["variants"]) > 8:
            out.append(f"    … +{len(detail['variants']) - 8} more")
        out.append("")
    if detail["lora_adapters"]:
        out.append(f"  LORA ADAPTERS ({len(detail['lora_adapters'])})")
        for a in detail["lora_adapters"]:
            out.append(f"    · {a['id']}  ({a['hf_repo_id']})")
        out.append("")
    out.append("  ACTIONS")
    for k, v in detail["actions"].items():
        out.append(f"    {k:>30}: {v}")
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        prog="info.py",
        description="R231 (SDD-026 Z-2) — rich detail surface for one catalog model.",
    )
    p.add_argument("slug", help="model id (case-insensitive) or hf_repo_id fragment")
    p.add_argument(
        "--catalog",
        type=Path,
        default=DEFAULT_CATALOG,
        help="override catalog path",
    )
    p.add_argument("--json", action="store_true")
    try:
        args = p.parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2

    if not args.catalog.exists():
        print(f"ERROR catalog not found: {args.catalog}", file=sys.stderr)
        return 2
    models = load_catalog(args.catalog)
    target = resolve_slug(models, args.slug)
    if target is None:
        known = sorted(m.get("id", "") for m in models)[:10]
        print(
            f"ERROR unknown model slug {args.slug!r}; "
            f"first 10 known ids: {known}",
            file=sys.stderr,
        )
        return 2
    detail = build_detail(models, target)
    if args.json:
        print(json.dumps(detail, indent=2))
    else:
        print(render_human(detail), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
