#!/usr/bin/env python3
"""scripts/hardware/inventory-catalog.py — R317 (E1.M37).

Operator-named (§1b spec drop verbatim): declares operator's EXACT
hardware identifiers so other advisors compose against ONE truth
instead of duplicating defaults across 30+ rounds.

Operator-supplied verbatim (this round's spec drop):
  - UPS:    APC Smart-UPS 2200VA 1980W LCD Tower SmartConnect 20A
            120V SMT2200C
  - RAM:    2× CORSAIR Vengeance DDR5 RAM 128GB (2x64GB) — 6400MHz
            CL42-52-52-104 1.35V Intel XMP 3.0
            (CMK128GX5M2B6400C42) → 256GB total across 4 DIMMs
  - NVMe:   2× Samsung 990 EVO Plus 2TB PCIe Gen4 x4 / Gen5 x2
            NVMe 2.0 M.2
  - PSU:    be Quiet! Dark Power Pro 13 1600W (R313)
  - Board:  ASUS ProArt X870E-Creator WiFi (R312)
  - CPU:    Ryzen 9 9900X (Zen5, AVX-512 native)
  - GPU1:   RTX 4090 24GB
  - GPU2:   RTX PRO 6000 98GB

Operator caveat: "Not that we want to be rigid but if that help for
anything." → catalog ships defaults; operator overlay swaps any slot.

CLI:
  inventory-catalog.py list   [--category X] [--config P] [--json|--human]
  inventory-catalog.py show   <slot> [--config P] [--json|--human]
  inventory-catalog.py audit  [--config P] [--json|--human]
                                summarize what's declared per category

Operator-overlay (R283/SDD-030): /etc/sovereign-os/inventory-catalog.toml
overrides any slot via [[components]] entry matching by `slot`.

Exit codes:
  0  rendered
  1  unknown slot (show)
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
ROUND = "R317"
SDD_VECTOR = "E1.M37"


DEFAULT_COMPONENTS: list[dict[str, Any]] = [
    # ── CPU ──────────────────────────────────────────────
    {
        "slot": "cpu-0",
        "category": "cpu",
        "model": "AMD Ryzen 9 9900X",
        "vendor": "AMD",
        "tdp_w": 120,
        "cores": 12,
        "threads": 24,
        "arch": "Zen5 (Granite Ridge)",
        "features": ["AVX-512 native", "VPDPBUSD", "AMD-PSTATE"],
        "operator_caveat": None,
    },

    # ── PSU ──────────────────────────────────────────────
    {
        "slot": "psu-0",
        "category": "psu",
        "model": "be Quiet! Dark Power Pro 13 1600W",
        "vendor": "be Quiet!",
        "wattage_rated_w": 1600,
        "form_factor": "ATX 3.1",
        "efficiency": "80 Plus Titanium",
        "oc_switch_present": True,
        "related_advisor": "R313 (psu-oc-mode)",
        "operator_caveat": "Physical OC switch on rear face; "
                            "operator declares state via R313 overlay.",
    },

    # ── UPS ──────────────────────────────────────────────
    {
        "slot": "ups-0",
        "category": "ups",
        "model": "APC Smart-UPS 2200VA 1980W LCD Tower",
        "vendor": "APC",
        "sku": "SMT2200C",
        "va_rating": 2200,
        "watt_rating": 1980,
        "form_factor": "Tower",
        "voltage_v": 120,
        "amp_rating": 20,
        "smart_connect": True,
        "related_advisor": "R252 (power-status) + R302 (battery-ladder) "
                            "+ R314 (apc-profile)",
        "operator_caveat": "Refurbished unit (SKU "
                            "SMT2200C-Refurbished-SMT2200C-1YR); 1YR "
                            "warranty. 1980W rating < operator's PSU "
                            "rating (1600W draw + headroom) — sustained "
                            "dual-GPU peak may exceed UPS budget when "
                            "AC is gone. Pair with R314 aggressive "
                            "profile.",
    },

    # ── Memory (4 DIMMs across 2 kits) ──────────────────
    {
        "slot": "ram-dimm-0",
        "category": "ram",
        "model": "CORSAIR Vengeance DDR5",
        "vendor": "Corsair",
        "sku": "CMK128GX5M2B6400C42",
        "kit_part_of": "Kit A (2-DIMM kit)",
        "capacity_gib": 64,
        "speed_mhz": 6400,
        "timing": "CL42-52-52-104",
        "voltage_v": 1.35,
        "xmp_profile": "Intel XMP 3.0",
        "related_advisor": "R257 (memory-profile) + R315 (xmp-oc-room)",
        "operator_caveat": None,
    },
    {
        "slot": "ram-dimm-1",
        "category": "ram",
        "model": "CORSAIR Vengeance DDR5",
        "vendor": "Corsair",
        "sku": "CMK128GX5M2B6400C42",
        "kit_part_of": "Kit A (2-DIMM kit)",
        "capacity_gib": 64,
        "speed_mhz": 6400,
        "timing": "CL42-52-52-104",
        "voltage_v": 1.35,
        "xmp_profile": "Intel XMP 3.0",
        "related_advisor": "R257 (memory-profile) + R315 (xmp-oc-room)",
        "operator_caveat": None,
    },
    {
        "slot": "ram-dimm-2",
        "category": "ram",
        "model": "CORSAIR Vengeance DDR5",
        "vendor": "Corsair",
        "sku": "CMK128GX5M2B6400C42",
        "kit_part_of": "Kit B (2-DIMM kit)",
        "capacity_gib": 64,
        "speed_mhz": 6400,
        "timing": "CL42-52-52-104",
        "voltage_v": 1.35,
        "xmp_profile": "Intel XMP 3.0",
        "related_advisor": "R257 (memory-profile) + R315 (xmp-oc-room)",
        "operator_caveat": "Two kits combined to 4×64GB=256GB — XMP "
                            "may fail to train at advertised 6400MHz "
                            "with 4 DIMM populated; operator may need "
                            "to drop to 6000MHz or use AMD's EXPO "
                            "kit-compatibility lookup.",
    },
    {
        "slot": "ram-dimm-3",
        "category": "ram",
        "model": "CORSAIR Vengeance DDR5",
        "vendor": "Corsair",
        "sku": "CMK128GX5M2B6400C42",
        "kit_part_of": "Kit B (2-DIMM kit)",
        "capacity_gib": 64,
        "speed_mhz": 6400,
        "timing": "CL42-52-52-104",
        "voltage_v": 1.35,
        "xmp_profile": "Intel XMP 3.0",
        "related_advisor": "R257 (memory-profile) + R315 (xmp-oc-room)",
        "operator_caveat": None,
    },

    # ── NVMe ─────────────────────────────────────────────
    {
        "slot": "nvme-m2-0",
        "category": "nvme",
        "model": "Samsung 990 EVO Plus 2TB",
        "vendor": "Samsung",
        "capacity_gb": 2000,
        "interface": "PCIe Gen4 x4 / Gen5 x2 NVMe 2.0",
        "form_factor": "M.2",
        "board_slot": "M.2_1",
        "negotiated_speed_note": "On X870E PCIE_1, this NVMe negotiates "
                                  "Gen5 x2 in M.2_1 (Gen5 slot) by default.",
        "related_advisor": "R298 (storage-health)",
        "operator_caveat": None,
    },
    {
        "slot": "nvme-m2-1",
        "category": "nvme",
        "model": "Samsung 990 EVO Plus 2TB",
        "vendor": "Samsung",
        "capacity_gb": 2000,
        "interface": "PCIe Gen4 x4 / Gen5 x2 NVMe 2.0",
        "form_factor": "M.2",
        "board_slot": "M.2_2",
        "negotiated_speed_note": "Second Gen5 slot — operator can "
                                  "alternatively use as Gen4 x4 to "
                                  "preserve Gen5 lanes for PCIE_1 GPU.",
        "related_advisor": "R298 (storage-health)",
        "operator_caveat": None,
    },

    # ── GPU ──────────────────────────────────────────────
    {
        "slot": "gpu-pcie-0",
        "category": "gpu",
        "model": "NVIDIA GeForce RTX 4090",
        "vendor": "NVIDIA",
        "vram_gib": 24,
        "board_slot": "PCIE_1 or PCIE_3 (operator choice)",
        "tgp_w": 350,
        "sustained_w": 420,
        "related_advisor": "R303 (gpu-wattage) + R315 (xmp-oc-room)",
        "operator_caveat": "When dual GPU active, pair with PRO 6000 "
                            "+ enable PCIe bifurcation per R312.",
    },
    {
        "slot": "gpu-pcie-1",
        "category": "gpu",
        "model": "NVIDIA RTX PRO 6000",
        "vendor": "NVIDIA",
        "vram_gib": 98,
        "board_slot": "PCIE_1 (primary)",
        "tgp_w": 600,
        "sustained_w": 600,
        "related_advisor": "R303 (gpu-wattage) + R315 (xmp-oc-room)",
        "operator_caveat": "Primary GPU — gets PCIE_1 full Gen5 x16 "
                            "by operator preference per R312.",
    },

    # ── Board ────────────────────────────────────────────
    {
        "slot": "board-0",
        "category": "board",
        "model": "ASUS ProArt X870E-Creator WiFi",
        "vendor": "ASUSTeK COMPUTER INC.",
        "chipset": "AMD X870E",
        "socket": "AM5",
        "related_advisor": "R312 (board-advisor)",
        "operator_caveat": None,
    },
]


def load_catalog(overlay_path: Path | None) -> tuple[list[dict], dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    catalog = list(DEFAULT_COMPONENTS)
    if load_with_overlay is not None:
        cfg = load_with_overlay(
            "inventory-catalog", {"components": []},
            explicit_path=overlay_path,
        )
        meta["_source"] = cfg.get("_source", meta["_source"])
        meta["_overlay_keys"] = cfg.get("_overlay_keys", [])
        if cfg.get("_parse_error"):
            meta["_parse_error"] = cfg["_parse_error"]
        if cfg.get("components"):
            # Overlay components replace by `slot` match; new slots append.
            by_slot = {c["slot"]: c for c in catalog if isinstance(c, dict) and c.get("slot")}
            for c in cfg["components"]:
                if isinstance(c, dict) and c.get("slot"):
                    by_slot[c["slot"]] = c
            catalog = list(by_slot.values())
    return catalog, meta


def filter_category(catalog: list[dict], category: str | None) -> list[dict]:
    if category is None:
        return list(catalog)
    return [c for c in catalog if isinstance(c, dict) and c.get("category") == category]


def resolve(catalog: list[dict], slot: str) -> dict | None:
    for c in catalog:
        if isinstance(c, dict) and c.get("slot") == slot:
            return c
    return None


def render_list_human(entries: list[dict]) -> str:
    lines = [f"── R317 sovereign-os hardware inventory (E1.M37) ──",
             f"  components: {len(entries)}", ""]
    cats = sorted({c.get("category", "?") for c in entries if isinstance(c, dict)})
    for cat in cats:
        items = [c for c in entries if c.get("category") == cat]
        if not items:
            continue
        lines.append(f"  ── {cat} ({len(items)}) ──")
        for c in items:
            lines.append(f"    {c.get('slot'):16s}  {c.get('model')}")
        lines.append("")
    return "\n".join(lines)


def render_show_human(c: dict) -> str:
    lines = [f"── R317 inventory: {c.get('slot')} (E1.M37) ──"]
    for k, v in c.items():
        if k == "operator_caveat" and v:
            continue
        lines.append(f"  {k:>22s}: {v}")
    if c.get("operator_caveat"):
        lines.append("")
        lines.append(f"  caveat: {c['operator_caveat']}")
    return "\n".join(lines) + "\n"


def audit(catalog: list[dict]) -> dict[str, Any]:
    """Summarize what's declared per category."""
    cats: dict[str, list[str]] = {}
    for c in catalog:
        if not isinstance(c, dict):
            continue
        cats.setdefault(c.get("category", "?"), []).append(c.get("slot"))
    total_ram = sum(c.get("capacity_gib", 0)
                    for c in catalog
                    if isinstance(c, dict) and c.get("category") == "ram")
    total_nvme = sum(c.get("capacity_gb", 0)
                      for c in catalog
                      if isinstance(c, dict) and c.get("category") == "nvme")
    total_vram = sum(c.get("vram_gib", 0)
                      for c in catalog
                      if isinstance(c, dict) and c.get("category") == "gpu")
    return {
        "category_counts": {k: len(v) for k, v in cats.items()},
        "category_slots": cats,
        "totals": {
            "ram_gib": total_ram,
            "nvme_gb": total_nvme,
            "gpu_vram_gib": total_vram,
        },
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="inventory-catalog.py")
    sub = p.add_subparsers(dest="verb", required=True)

    pl = sub.add_parser("list")
    pl.add_argument("--category")
    pl.add_argument("--config", type=Path)
    fl = pl.add_mutually_exclusive_group()
    fl.add_argument("--json", dest="fmt", action="store_const", const="json")
    fl.add_argument("--human", dest="fmt", action="store_const", const="human")
    pl.set_defaults(fmt="json")

    ps = sub.add_parser("show")
    ps.add_argument("slot")
    ps.add_argument("--config", type=Path)
    fs = ps.add_mutually_exclusive_group()
    fs.add_argument("--json", dest="fmt", action="store_const", const="json")
    fs.add_argument("--human", dest="fmt", action="store_const", const="human")
    ps.set_defaults(fmt="json")

    pa = sub.add_parser("audit")
    pa.add_argument("--config", type=Path)
    fa = pa.add_mutually_exclusive_group()
    fa.add_argument("--json", dest="fmt", action="store_const", const="json")
    fa.add_argument("--human", dest="fmt", action="store_const", const="human")
    pa.set_defaults(fmt="json")

    args = p.parse_args(argv)
    catalog, meta = load_catalog(args.config)

    if args.verb == "list":
        entries = filter_category(catalog, args.category)
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "category_filter": args.category,
                "total_count": len(catalog),
                "filtered_count": len(entries),
                "components": entries,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_list_human(entries), end="")
        return 0

    if args.verb == "show":
        c = resolve(catalog, args.slot)
        if c is None:
            print(json.dumps({
                "error": f"unknown slot: {args.slot}",
                "known_slots": [x.get("slot") for x in catalog
                                if isinstance(x, dict)],
                "round": ROUND,
            }, indent=2), file=sys.stderr)
            return 1
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "component": c,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_show_human(c), end="")
        return 0

    if args.verb == "audit":
        a = audit(catalog)
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "total_components": len(catalog),
                **a,
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R317 inventory audit (E1.M37) ──")
            print(f"  total components: {len(catalog)}")
            print()
            print(f"  per-category counts:")
            for k, n in sorted(a["category_counts"].items()):
                print(f"    {k:>10s}: {n}")
            print()
            print(f"  totals:")
            for k, v in a["totals"].items():
                print(f"    {k:>16s}: {v}")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
