#!/usr/bin/env python3
"""scripts/hardware/gpu-wattage-catalog.py — R303 (E1.M28).

Operator-named (§1b mandate row, verbatim): "GPU too, watts, RTX 3090
details and possibilities established and non-established, same for
the RTX Pro 6000". Closes E1.M28.

Per-card, per-operational-mode wattage catalog. Each entry binds:

  - card                 RTX 3090 / RTX PRO 6000
  - mode                 idle / typical-inference / peak-training / oc-peak
  - watts                operator-pinned reference (datasheet + bench)
  - source               where the number came from (datasheet, R258 sampler)
  - operator_note        when this mode actually fires in the operator's
                          workload

Composed with R292 oc-headroom for dual-card budget projection:
operator picks per-card mode, script sums and compares to PSU
planning budget.

CLI:
  gpu-wattage-catalog.py list   [--card C] [--mode M] [--config P] [--json|--human]
  gpu-wattage-catalog.py show   <card> <mode> [--config P] [--json|--human]
  gpu-wattage-catalog.py budget [--config-3090 M] [--config-pro6000 M]
                                 [--config P] [--json|--human]
                            sums per-card mode → operator-readable
                            dual-card budget projection

Operator-overlay (R283/SDD-030): /etc/sovereign-os/gpu-wattage-catalog.toml
for adding new cards / re-pinning wattages.

Exit codes:
  0  rendered
  1  unknown card or mode
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
ROUND = "R303"
SDD_VECTOR = "E1.M28"


# ── Per-card per-mode wattage catalog ──────────────────────────────
DEFAULT_CATALOG: list[dict[str, Any]] = [
    # ── RTX 3090 (Ampere, GA102, 24 GB GDDR6X) ──────────────────
    {
        "card": "RTX 3090",
        "mode": "idle",
        "watts": 22,
        "source": "datasheet + R258 sampler typical desktop idle",
        "operator_note": "Display-on idle with operator's monitors lit.",
    },
    {
        "card": "RTX 3090",
        "mode": "typical-inference",
        "watts": 220,
        "source": "operator-pinned: BF16 inference at ~70% utilization",
        "operator_note": "Steady-state inference serving for "
                         "operator-helpdesk-eval task on Qwen2-7B.",
    },
    {
        "card": "RTX 3090",
        "mode": "peak-training",
        "watts": 350,
        "source": "datasheet TGP (factory)",
        "operator_note": "Fine-tune training under TRL SFT with full "
                         "BF16 + AdamW — saturates power_limit.",
    },
    {
        "card": "RTX 3090",
        "mode": "oc-peak",
        "watts": 420,
        "source": "operator-mandate §1b 'OC profile' headroom + NVIDIA "
                  "msi-afterburner-style +20% slider",
        "operator_note": "Available only when nvidia-smi -pl 420 + "
                         "BIOS allows; pulls full PCIe slot power.",
    },

    # ── RTX PRO 6000 (Blackwell PRO, GB202, 96-98 GB GDDR7 ECC) ──
    {
        "card": "RTX PRO 6000",
        "mode": "idle",
        "watts": 35,
        "source": "datasheet + workstation-SKU baseline",
        "operator_note": "Higher idle than 3090 due to ECC + 96 GB "
                         "memory refresh — operator pays the floor.",
    },
    {
        "card": "RTX PRO 6000",
        "mode": "typical-inference",
        "watts": 380,
        "source": "operator-pinned: FP8 inference at ~70% utilization",
        "operator_note": "Steady-state inference for large-context "
                         "workloads (70B-class on 98 GB VRAM).",
    },
    {
        "card": "RTX PRO 6000",
        "mode": "peak-training",
        "watts": 600,
        "source": "datasheet TGP (factory)",
        "operator_note": "Full BF16 + FP8 training; Blackwell tensor "
                         "engines saturate power_limit.",
    },
    {
        "card": "RTX PRO 6000",
        "mode": "oc-peak",
        "watts": 720,
        "source": "operator-mandate §1b 'OC profile' + nvidia-smi -pl "
                  "+20% slider (workstation SKU ceiling)",
        "operator_note": "Available when BIOS PBO + driver allow; "
                         "operator must verify thermals via R296.",
    },
]


def load_catalog(overlay_path: Path | None) -> tuple[list[dict], dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    catalog = list(DEFAULT_CATALOG)
    if load_with_overlay is not None:
        cfg = load_with_overlay(
            "gpu-wattage-catalog",
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


def resolve_entry(catalog: list[dict], card: str, mode: str) -> dict | None:
    for e in catalog:
        if isinstance(e, dict) and e.get("card") == card and e.get("mode") == mode:
            return e
    return None


def cards_in(catalog: list[dict]) -> list[str]:
    seen = set()
    out = []
    for e in catalog:
        if isinstance(e, dict):
            c = e.get("card")
            if c and c not in seen:
                seen.add(c)
                out.append(c)
    return out


def modes_for_card(catalog: list[dict], card: str) -> list[str]:
    return [e["mode"] for e in catalog
            if isinstance(e, dict) and e.get("card") == card]


def filter_entries(catalog: list[dict], card: str | None,
                   mode: str | None) -> list[dict]:
    out = []
    for e in catalog:
        if not isinstance(e, dict):
            continue
        if card is not None and e.get("card") != card:
            continue
        if mode is not None and e.get("mode") != mode:
            continue
        out.append(e)
    return out


# ── Renderers ───────────────────────────────────────────────────────
def render_list_human(entries: list[dict], catalog: list[dict],
                      meta: dict) -> str:
    lines = ["── R303 sovereign-os GPU wattage catalog (E1.M28) ──"]
    lines.append(f"  source:    {meta.get('_source')}")
    lines.append(f"  total:     {len(catalog)}")
    lines.append(f"  filtered:  {len(entries)}")
    lines.append(f"  cards:     {', '.join(cards_in(catalog))}")
    lines.append("")
    for c in cards_in(catalog):
        card_entries = [e for e in entries if e.get("card") == c]
        if not card_entries:
            continue
        lines.append(f"  ── {c} ──")
        for e in sorted(card_entries, key=lambda x: x.get("watts", 0)):
            lines.append(f"    [{e.get('mode'):20s}] "
                         f"{e.get('watts', '?'):>4} W   "
                         f"src: {e.get('source', '?')[:60]}")
        lines.append("")
    return "\n".join(lines)


def render_show_human(e: dict) -> str:
    lines = [f"── R303 {e.get('card')} @ {e.get('mode')} (E1.M28) ──"]
    lines.append(f"  watts:          {e.get('watts')} W")
    lines.append(f"  source:         {e.get('source')}")
    if e.get("operator_note"):
        lines.append(f"  operator note:  {e['operator_note']}")
    return "\n".join(lines) + "\n"


# ── Main ────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="gpu-wattage-catalog.py")
    sub = p.add_subparsers(dest="verb", required=True)

    pl = sub.add_parser("list")
    pl.add_argument("--card")
    pl.add_argument("--mode")
    pl.add_argument("--config", type=Path)
    fl = pl.add_mutually_exclusive_group()
    fl.add_argument("--json", dest="fmt", action="store_const", const="json")
    fl.add_argument("--human", dest="fmt", action="store_const", const="human")
    pl.set_defaults(fmt="json")

    ps = sub.add_parser("show")
    ps.add_argument("card")
    ps.add_argument("mode")
    ps.add_argument("--config", type=Path)
    fs = ps.add_mutually_exclusive_group()
    fs.add_argument("--json", dest="fmt", action="store_const", const="json")
    fs.add_argument("--human", dest="fmt", action="store_const", const="human")
    ps.set_defaults(fmt="json")

    pb = sub.add_parser("budget")
    pb.add_argument("--mode-3090", default="typical-inference",
                     help="operational mode for RTX 3090 (default: typical-inference)")
    pb.add_argument("--mode-pro6000", default="typical-inference",
                     help="operational mode for RTX PRO 6000")
    pb.add_argument("--psu-rated-watts", type=int, default=1600,
                     help="PSU rated wattage for budget projection (default: 1600)")
    pb.add_argument("--cpu-tdp-watts", type=int, default=170)
    pb.add_argument("--chassis-baseline-watts", type=int, default=80)
    pb.add_argument("--config", type=Path)
    fb = pb.add_mutually_exclusive_group()
    fb.add_argument("--json", dest="fmt", action="store_const", const="json")
    fb.add_argument("--human", dest="fmt", action="store_const", const="human")
    pb.set_defaults(fmt="json")

    args = p.parse_args(argv)
    catalog, meta = load_catalog(args.config)

    if args.verb == "list":
        entries = filter_entries(catalog, args.card, args.mode)
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "filter": {"card": args.card, "mode": args.mode},
                "total_count": len(catalog),
                "filtered_count": len(entries),
                "cards": cards_in(catalog),
                "entries": entries,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_list_human(entries, catalog, meta), end="")
        return 0

    if args.verb == "show":
        e = resolve_entry(catalog, args.card, args.mode)
        if e is None:
            print(json.dumps({
                "error": f"no entry: card={args.card!r} mode={args.mode!r}",
                "known_cards": cards_in(catalog),
                "known_modes_for_card": modes_for_card(catalog, args.card),
                "round": ROUND,
            }, indent=2), file=sys.stderr)
            return 1
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "entry": e,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_show_human(e), end="")
        return 0

    if args.verb == "budget":
        e3090 = resolve_entry(catalog, "RTX 3090", args.mode_3090)
        epro = resolve_entry(catalog, "RTX PRO 6000", args.mode_pro6000)
        if e3090 is None or epro is None:
            print(json.dumps({
                "error": "could not resolve one of the GPU modes",
                "rtx_3090_mode": args.mode_3090,
                "rtx_3090_resolved": e3090 is not None,
                "rtx_pro_6000_mode": args.mode_pro6000,
                "rtx_pro_6000_resolved": epro is not None,
                "round": ROUND,
            }, indent=2), file=sys.stderr)
            return 1
        gpu_total = e3090["watts"] + epro["watts"]
        projected = args.cpu_tdp_watts + gpu_total + args.chassis_baseline_watts
        headroom = args.psu_rated_watts - projected
        headroom_pct = round((headroom / args.psu_rated_watts) * 100.0, 1) \
            if args.psu_rated_watts > 0 else 0.0
        verdict = ("over-budget" if headroom < 0
                   else "headroom-tight" if headroom_pct < 20
                   else "headroom-safe")
        doc = {
            "schema_version": SCHEMA_VERSION,
            "round": ROUND,
            "sdd_vector": SDD_VECTOR,
            "rtx_3090": {"mode": args.mode_3090, "watts": e3090["watts"]},
            "rtx_pro_6000": {"mode": args.mode_pro6000, "watts": epro["watts"]},
            "gpu_total_watts": gpu_total,
            "cpu_tdp_watts": args.cpu_tdp_watts,
            "chassis_baseline_watts": args.chassis_baseline_watts,
            "projected_total_watts": projected,
            "psu_rated_watts": args.psu_rated_watts,
            "psu_headroom_watts": headroom,
            "psu_headroom_pct": headroom_pct,
            "verdict": verdict,
            "overlay": meta,
        }
        if args.fmt == "json":
            print(json.dumps(doc, indent=2))
        else:
            print(f"── R303 GPU dual-card budget (E1.M28) ──")
            print(f"  RTX 3090       @ {args.mode_3090:20s}  {e3090['watts']:>4} W")
            print(f"  RTX PRO 6000   @ {args.mode_pro6000:20s}  {epro['watts']:>4} W")
            print(f"  + CPU TDP                                  {args.cpu_tdp_watts:>4} W")
            print(f"  + chassis baseline                         {args.chassis_baseline_watts:>4} W")
            print(f"  = projected total                          {projected:>4} W")
            print(f"  PSU rated                                  {args.psu_rated_watts:>4} W")
            print(f"  PSU headroom                               {headroom:>4} W ({headroom_pct}%)")
            print(f"  verdict: {verdict}")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
