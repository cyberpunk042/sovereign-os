#!/usr/bin/env python3
"""scripts/hardware/gpu-possibility-catalog.py — R295 (E1.M23).

Operator-named (§1b mandate row, verbatim): "RTX 3090 details and
possibilities established and non-established, same for the RTX Pro
6000 and the CPU and AVX512". Closes E1.M23 — operator-pull catalog
of per-card capabilities, partitioned by ESTABLISHED (the operator
has confirmed this works on the SAIN-01 stack) vs NON-ESTABLISHED
(theoretical headroom, requires operator validation).

The catalog is operator-readable + extensible via overlay. Each entry
binds:
  - card (RTX 3090 / RTX PRO 6000)
  - capability (e.g. "FP16 inference at 80 TFLOPS", "INT8 tensor cores",
                "NVLink between cards")
  - status: established | non-established
  - evidence: operator-readable note (which test / SDD / round
              confirmed it, or what's needed to validate)
  - related_sdd / related_round / related_mandate_module (cross-refs)

CLI:
  catalog.py list        [--card C] [--status S] [--config P] [--json|--human]
  catalog.py show        <card> [--config P] [--json|--human]
  catalog.py gaps        [--config P] [--json|--human]
                            list non-established capabilities (what
                            the operator needs to validate next)

Operator-overlay (R283/SDD-030): /etc/sovereign-os/gpu-possibility-
catalog.toml (or env, or --config). Lists REPLACE.

Exit codes:
  0  rendered
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
ROUND = "R295"
SDD_VECTOR = "E1.M23"


# ── Default GPU possibility catalog (operator-overlay replaces) ────
#
# Seeded with the operator's §1b dual-rig (RTX 3090 + RTX PRO 6000)
# capabilities + status. Operator extends / corrects via overlay.
DEFAULT_CATALOG: list[dict[str, Any]] = [
    # ── RTX 3090 (Ampere, 24 GB GDDR6X) ─────────────────────────
    {
        "card": "RTX 3090",
        "capability": "FP16 / BF16 inference via Tensor Cores",
        "status": "established",
        "evidence": "shipped via R244 fine_tune + R232 eval; "
                    "operator has run BF16 on this card.",
        "related_round": "R244",
        "related_mandate_module": "E5.M5",
        "related_sdd": "scripts/models/fine_tune.py",
    },
    {
        "card": "RTX 3090",
        "capability": "INT8 inference via Tensor Cores",
        "status": "established",
        "evidence": "vllm + TensorRT path uses INT8 tensor cores; "
                    "see scripts/inference/router.py routing rules.",
        "related_round": "R157",
        "related_mandate_module": "E5.M8",
        "related_sdd": "scripts/inference/dflash-wrap.sh",
    },
    {
        "card": "RTX 3090",
        "capability": "FP8 tensor cores (Hopper feature)",
        "status": "non-established",
        "evidence": "Ampere lacks FP8 tensor cores — this is "
                    "structurally absent. Listed for explicit "
                    "operator-pull surface ('what RTX 3090 CAN'T do').",
        "related_round": None,
        "related_mandate_module": None,
        "related_sdd": None,
    },
    {
        "card": "RTX 3090",
        "capability": "NVLink to second card (with RTX 3090)",
        "status": "non-established",
        "evidence": "operator has only one RTX 3090 — NVLink would "
                    "require a second matching card. The RTX PRO 6000 "
                    "isn't NVLink-compatible with the 3090.",
        "related_round": None,
        "related_mandate_module": "E1.M13",
        "related_sdd": "docs/sdd/029-hardware-stack-consolidation.md",
    },
    {
        "card": "RTX 3090",
        "capability": "tensor-parallel inference SPLIT with RTX PRO 6000",
        "status": "non-established",
        "evidence": "asymmetric VRAM (24 GB + 98 GB) + non-NVLink "
                    "means PCIe-mediated split — vllm support is "
                    "tentative. Listed as the next major validation.",
        "related_round": None,
        "related_mandate_module": "E1.M13",
        "related_sdd": "scripts/hardware/gpu-card-advisor.py",
    },
    {
        "card": "RTX 3090",
        "capability": "ECC memory",
        "status": "non-established",
        "evidence": "RTX 3090 (GeForce SKU) lacks ECC. Operator "
                    "workloads requiring ECC need to land on the "
                    "RTX PRO 6000 (Blackwell pro SKU has ECC).",
        "related_round": None,
        "related_mandate_module": None,
        "related_sdd": None,
    },

    # ── RTX PRO 6000 (Blackwell, 96-98 GB GDDR7 ECC) ────────────
    {
        "card": "RTX PRO 6000",
        "capability": "FP16 / BF16 / FP8 inference via Tensor Cores",
        "status": "established",
        "evidence": "Blackwell tensor cores ship FP8 (E5M2 + E4M3) "
                    "+ FP16 + BF16. Operator-confirmed via R272 "
                    "AVX-512 + tensor pipeline integration.",
            "related_round": "R272",
            "related_mandate_module": "E1.M14",
            "related_sdd": "docs/sdd/029-hardware-stack-consolidation.md",
    },
    {
        "card": "RTX PRO 6000",
        "capability": "INT8 inference via Tensor Cores",
        "status": "established",
        "evidence": "carries forward from Ampere; INT8 path used by "
                    "ternary-aot fast path (R280) for the bitnet.cpp "
                    "VPDPBUSD-equivalent flow.",
        "related_round": "R280",
        "related_mandate_module": "E1.M18",
        "related_sdd": "scripts/hardware/zmm-ternary-probe.py",
    },
    {
        "card": "RTX PRO 6000",
        "capability": "98 GB VRAM for large-context inference",
        "status": "established",
        "evidence": "card spec sheet ships 96-98 GB GDDR7. Operator's "
                    "ram-advisor (R279) projects model+KV-cache fit "
                    "for 70B-class FP16 + 8k context within budget.",
        "related_round": "R279",
        "related_mandate_module": "E1.M16",
        "related_sdd": "scripts/hardware/ram-advisor.py",
    },
    {
        "card": "RTX PRO 6000",
        "capability": "ECC memory (Blackwell PRO SKU)",
        "status": "established",
        "evidence": "RTX PRO 6000 is a workstation SKU with ECC "
                    "GDDR7. Production workloads requiring memory "
                    "integrity land here.",
        "related_round": None,
        "related_mandate_module": "E1.M13",
        "related_sdd": None,
    },
    {
        "card": "RTX PRO 6000",
        "capability": "Transformer Engine v3 (Blackwell)",
        "status": "non-established",
        "evidence": "feature ships on Blackwell silicon BUT operator "
                    "hasn't validated end-to-end TE-v3 path against "
                    "the operator-fine-tuned models. Listed for "
                    "future validation round.",
        "related_round": None,
        "related_mandate_module": "E5.M6",
        "related_sdd": "docs/sdd/027-pulse-algorithmic-foundation.md",
    },
    {
        "card": "RTX PRO 6000",
        "capability": "NVLink 5.0 (900 GB/s)",
        "status": "non-established",
        "evidence": "Blackwell PRO supports NVLink 5.0 BUT operator "
                    "has only one PRO 6000. Listed for the future "
                    "second-card upgrade scenario.",
        "related_round": None,
        "related_mandate_module": "E1.M13",
        "related_sdd": None,
    },
    {
        "card": "RTX PRO 6000",
        "capability": "MIG (Multi-Instance GPU) partitioning",
        "status": "non-established",
        "evidence": "MIG was Ampere/Hopper datacenter-SKU feature; "
                    "RTX PRO 6000 (workstation) doesn't ship MIG. "
                    "Listed explicitly so operator doesn't plan "
                    "for it.",
        "related_round": None,
        "related_mandate_module": None,
        "related_sdd": None,
    },
]


# ── Lookups ─────────────────────────────────────────────────────────
def load_catalog(overlay_path: Path | None) -> tuple[list[dict], dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    catalog = list(DEFAULT_CATALOG)
    if load_with_overlay is not None:
        cfg = load_with_overlay(
            "gpu-possibility-catalog",
            {"entries": []},
            explicit_path=overlay_path,
        )
        meta["_source"] = cfg.get("_source", meta["_source"])
        meta["_overlay_keys"] = cfg.get("_overlay_keys", [])
        if cfg.get("_parse_error"):
            meta["_parse_error"] = cfg["_parse_error"]
        if cfg.get("entries"):
            catalog = list(cfg["entries"])
    return catalog, meta


def filter_entries(catalog: list[dict], card: str | None,
                   status: str | None) -> list[dict]:
    out = []
    for e in catalog:
        if not isinstance(e, dict):
            continue
        if card is not None and e.get("card") != card:
            continue
        if status is not None and e.get("status") != status:
            continue
        out.append(e)
    return out


def cards(catalog: list[dict]) -> list[str]:
    seen = set()
    out = []
    for e in catalog:
        if isinstance(e, dict):
            c = e.get("card")
            if c and c not in seen:
                seen.add(c)
                out.append(c)
    return out


# ── Renderers ───────────────────────────────────────────────────────
def render_list_human(entries: list[dict], catalog: list[dict],
                      meta: dict) -> str:
    lines = ["── R295 sovereign-os GPU possibility catalog (E1.M23) ──"]
    lines.append(f"  source:   {meta.get('_source')}")
    lines.append(f"  total:    {len(catalog)}")
    lines.append(f"  filtered: {len(entries)}")
    lines.append(f"  cards:    {', '.join(cards(catalog))}")
    lines.append("")
    for c in cards(catalog):
        card_entries = [e for e in entries if e.get("card") == c]
        if not card_entries:
            continue
        lines.append(f"  ── {c} ──")
        for e in card_entries:
            mark = {"established": "OK ", "non-established": "?? "}.get(
                e.get("status"), "?? "
            )
            lines.append(f"    [{mark}] {e.get('capability', '?')}")
        lines.append("")
    return "\n".join(lines)


def render_show_human(card: str, entries: list[dict]) -> str:
    lines = [f"── R295 {card} possibility detail (E1.M23) ──"]
    est = [e for e in entries if e.get("status") == "established"]
    non = [e for e in entries if e.get("status") == "non-established"]
    lines.append(f"  established: {len(est)}")
    lines.append(f"  non-established: {len(non)}")
    lines.append("")
    lines.append("ESTABLISHED:")
    for e in est:
        lines.append(f"  • {e.get('capability')}")
        if e.get("evidence"):
            lines.append(f"      evidence: {e['evidence']}")
        for k in ("related_round", "related_mandate_module", "related_sdd"):
            v = e.get(k)
            if v:
                lines.append(f"      {k}: {v}")
        lines.append("")
    lines.append("NON-ESTABLISHED:")
    for e in non:
        lines.append(f"  • {e.get('capability')}")
        if e.get("evidence"):
            lines.append(f"      evidence: {e['evidence']}")
        lines.append("")
    return "\n".join(lines)


# ── Main ────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="gpu-possibility-catalog.py")
    sub = p.add_subparsers(dest="verb", required=True)

    pl = sub.add_parser("list")
    pl.add_argument("--card")
    pl.add_argument("--status", choices=("established", "non-established"))
    pl.add_argument("--config", type=Path)
    fl = pl.add_mutually_exclusive_group()
    fl.add_argument("--json", dest="fmt", action="store_const", const="json")
    fl.add_argument("--human", dest="fmt", action="store_const", const="human")
    pl.set_defaults(fmt="json")

    ps = sub.add_parser("show")
    ps.add_argument("card")
    ps.add_argument("--config", type=Path)
    fs = ps.add_mutually_exclusive_group()
    fs.add_argument("--json", dest="fmt", action="store_const", const="json")
    fs.add_argument("--human", dest="fmt", action="store_const", const="human")
    ps.set_defaults(fmt="json")

    pg = sub.add_parser("gaps")
    pg.add_argument("--config", type=Path)
    fg = pg.add_mutually_exclusive_group()
    fg.add_argument("--json", dest="fmt", action="store_const", const="json")
    fg.add_argument("--human", dest="fmt", action="store_const", const="human")
    pg.set_defaults(fmt="json")

    args = p.parse_args(argv)
    catalog, meta = load_catalog(args.config)

    if args.verb == "list":
        entries = filter_entries(catalog, args.card, args.status)
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "filter": {"card": args.card, "status": args.status},
                "total_count": len(catalog),
                "filtered_count": len(entries),
                "cards": cards(catalog),
                "entries": entries,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_list_human(entries, catalog, meta), end="")
        return 0

    if args.verb == "show":
        entries = filter_entries(catalog, args.card, None)
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "card": args.card,
                "entries": entries,
                "established_count": sum(1 for e in entries
                                         if e.get("status") == "established"),
                "non_established_count": sum(1 for e in entries
                                             if e.get("status") == "non-established"),
                "overlay": meta,
            }, indent=2))
        else:
            print(render_show_human(args.card, entries), end="")
        return 0

    if args.verb == "gaps":
        non_est = [e for e in catalog if e.get("status") == "non-established"]
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "gap_count": len(non_est),
                "entries": non_est,
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R295 GPU validation gaps (E1.M23) — {len(non_est)} non-established ──")
            for e in non_est:
                print(f"  • {e.get('card')}: {e.get('capability')}")
                if e.get("evidence"):
                    print(f"      {e['evidence']}")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
