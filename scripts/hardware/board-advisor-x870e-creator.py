#!/usr/bin/env python3
"""scripts/hardware/board-advisor-x870e-creator.py — R312 (E1.M32).

Operator-named (§1b mandate row, verbatim): "possibly detecting the
ASUS ProArt X870E-CREATOR WIFI and its settings and potential
optimisations and fixes. pci lane splits and whatever". Closes
E1.M32.

R251 ships generic BIOS-info (vendor / version / SMBIOS). R312 adds
the BOARD-SPECIFIC tuning catalog for the operator's exact board:
ASUS ProArt X870E-CREATOR WIFI. Items are board-specific:

  - PCIe slot allocation table (CPU vs chipset lanes per slot)
  - M.2 slot speed matrix (Gen5/Gen4 + bifurcation rules)
  - Dual-GPU bifurcation modes (x16/x16 vs x16/x0)
  - BIOS-flashback recipe (USB-A port + button)
  - Memory training timeout (CMOS-clear conditions)
  - Known issues + workarounds (Q-code reference, etc.)

Detects host board via dmidecode-format /sys/devices/virtual/dmi/id/
files. When host board matches, status verb returns full
recommendation set. When it doesn't, operator can still query the
catalog via `advise <board>` (operator-pull from another host).

CLI:
  board-advisor-x870e-creator.py status     [--config P] [--json|--human]
                                              host board detection +
                                              recommendation if match
  board-advisor-x870e-creator.py advise     [--board NAME] [--config P]
                                            [--json|--human]
                                              dump catalog (or one
                                              board's recommendations)
  board-advisor-x870e-creator.py slot-map   [--config P] [--json|--human]
                                              PCIe slot allocation table
                                              for the matched board

Operator-overlay (R283/SDD-030): /etc/sovereign-os/board-advisor.toml
adds [[boards]] entries for other reference boards.

Exit codes:
  0  rendered
  1  host board doesn't match catalog (status)
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
ROUND = "R312"
SDD_VECTOR = "E1.M32"

DMI_BASE = Path("/sys/devices/virtual/dmi/id")


DEFAULT_BOARDS: list[dict[str, Any]] = [
    {
        "match_vendor": "ASUSTeK COMPUTER INC.",
        "match_name": "ProArt X870E-Creator WiFi",
        "name": "asus-proart-x870e-creator-wifi",
        "display_name": "ASUS ProArt X870E-Creator WiFi",
        "chipset": "AMD X870E",
        "socket": "AM5",
        "supported_cpus": ["Ryzen 9000 series (Granite Ridge)",
                            "Ryzen 8000 series (Phoenix2)",
                            "Ryzen 7000 series (Raphael)"],
        "pcie_slots": [
            {"label": "PCIE_1",
             "lanes": "x16 (CPU Gen5)",
             "shared_with": "(none — full x16 when M.2_1/M.2_2 not in Gen5 mode)",
             "operator_note": "Primary GPU slot. Use for RTX PRO 6000 "
                              "(98 GiB) — gets full Gen5 x16."},
            {"label": "PCIE_2",
             "lanes": "x4 (chipset Gen4)",
             "shared_with": "(none)",
             "operator_note": "Secondary expansion. Lower bandwidth — "
                              "use for NIC / capture card, NOT a GPU."},
            {"label": "PCIE_3",
             "lanes": "x16 (CPU Gen5; physical x16, electrical x4 by default)",
             "shared_with": "M.2_3 (when bifurcated x4/x4/x4/x4)",
             "operator_note": "Wires for the SECOND GPU. Operator MUST "
                              "enable PCIe bifurcation in BIOS to get x8 "
                              "from primary; otherwise GPU2 lands at "
                              "Gen5 x4 (still fast but suboptimal). "
                              "See R270 pcie-lanes."},
        ],
        "m2_slots": [
            {"label": "M.2_1", "speed": "Gen5 x4", "operator_note": "Hottest slot — operator's primary NVMe OS."},
            {"label": "M.2_2", "speed": "Gen5 x4", "operator_note": "Second Gen5 — model storage."},
            {"label": "M.2_3", "speed": "Gen4 x4", "operator_note": "Third — bulk storage / scratch."},
            {"label": "M.2_4", "speed": "Gen4 x4 (chipset)", "operator_note": "Backup / less-hot data."},
        ],
        "dual_gpu_bifurcation_modes": [
            {"mode": "x16/x0", "rationale": "Default — PRO 6000 in PCIE_1, no second GPU."},
            {"mode": "x8/x8 (CPU bifurcation)", "rationale": "Operator's dual-GPU target. Enable in BIOS Advanced → AMD PBS → PCIe Bifurcation."},
            {"mode": "x4/x4/x4/x4", "rationale": "Quad-NVMe via M.2 expansion card; loses one GPU slot. NOT for operator's dual-GPU workload."},
        ],
        "bios_flashback_recipe": (
            "1. Rename BIOS file to PAX870E.CAP on a FAT32 USB stick "
            "(formatted single partition). 2. Insert into the rear USB "
            "port labeled BIOS FlashBack (the dedicated white port). "
            "3. Hold BIOS FlashBack button for 3s — LED blinks "
            "during flash; solid when done; ~5 min."
        ),
        "memory_training_timeout_advice": (
            "X870E with 4× DIMM populated at EXPO/DOCP may take "
            "60-90s on first POST after CMOS clear. Operator should "
            "NOT power-cycle during this window — Q-code stays in "
            "0x15 / 0x4F range. Subsequent POSTs are <5s once trained."
        ),
        "known_issues": [
            {"issue": "USB drop on long sleep (S3)",
             "workaround": "Set CPU C-states → C2 max (not C6) under "
                            "BIOS Advanced → AMD CBS → SOC. Operator "
                            "tradeoff: ~3W more idle."},
            {"issue": "ReBAR conflict with some older NVMe firmware",
             "workaround": "Disable ReBAR temporarily, update NVMe "
                            "firmware via vendor tool, re-enable."},
            {"issue": "PCIe Gen5 + long extension riser instability",
             "workaround": "Force PCIE_1 to Gen4 in BIOS if using "
                            "extension > 20cm. RTX PRO 6000 still "
                            "benefits from Gen4 x16 — runs at full "
                            "perf."},
        ],
        "operator_caveat": "Tuning above is operator-pull. Always "
                            "verify BIOS version before applying — "
                            "older BIOSes may not expose all options.",
    },
]


def read_dmi() -> dict[str, str | None]:
    out = {}
    for key, fname in [
        ("board_vendor", "board_vendor"),
        ("board_name", "board_name"),
        ("board_version", "board_version"),
        ("bios_vendor", "bios_vendor"),
        ("bios_version", "bios_version"),
        ("bios_date", "bios_date"),
        ("product_name", "product_name"),
    ]:
        p = DMI_BASE / fname
        try:
            out[key] = p.read_text().strip()
        except OSError:
            out[key] = None
    return out


def match_board(dmi: dict, catalog: list[dict]) -> dict | None:
    vendor = (dmi.get("board_vendor") or "").strip()
    name = (dmi.get("board_name") or "").strip()
    for b in catalog:
        if not isinstance(b, dict):
            continue
        mv = (b.get("match_vendor") or "").strip()
        mn = (b.get("match_name") or "").strip()
        if mv and mn and vendor.lower() == mv.lower() and name.lower() == mn.lower():
            return b
    return None


def load_catalog(overlay_path: Path | None) -> tuple[list[dict], dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    catalog = list(DEFAULT_BOARDS)
    if load_with_overlay is not None:
        cfg = load_with_overlay(
            "board-advisor", {"boards": []}, explicit_path=overlay_path,
        )
        meta["_source"] = cfg.get("_source", meta["_source"])
        meta["_overlay_keys"] = cfg.get("_overlay_keys", [])
        if cfg.get("_parse_error"):
            meta["_parse_error"] = cfg["_parse_error"]
        if cfg.get("boards"):
            catalog = list(cfg["boards"])
    return catalog, meta


def render_status_human(dmi: dict, board: dict | None) -> str:
    lines = [f"── R312 sovereign-os board advisor (E1.M32) ──"]
    lines.append(f"  detected vendor: {dmi.get('board_vendor')}")
    lines.append(f"  detected board:  {dmi.get('board_name')}")
    lines.append(f"  bios version:    {dmi.get('bios_version')} ({dmi.get('bios_date')})")
    lines.append("")
    if board is None:
        lines.append("  verdict: board not in catalog — operator may run "
                     "`advise --board NAME` to query manually.")
        return "\n".join(lines) + "\n"
    lines.append(f"  matched: {board['display_name']}")
    lines.append(f"  chipset: {board.get('chipset')}")
    lines.append(f"  socket:  {board.get('socket')}")
    lines.append("")
    lines.append(f"  PCIe slots ({len(board.get('pcie_slots', []))}):")
    for s in board.get("pcie_slots", []):
        lines.append(f"    {s.get('label')}: {s.get('lanes')}")
        if s.get('shared_with'):
            lines.append(f"      shared_with: {s['shared_with']}")
    lines.append("")
    lines.append(f"  M.2 slots ({len(board.get('m2_slots', []))}):")
    for s in board.get("m2_slots", []):
        lines.append(f"    {s.get('label')}: {s.get('speed')}")
    lines.append("")
    lines.append(f"  Dual-GPU bifurcation modes:")
    for m in board.get("dual_gpu_bifurcation_modes", []):
        lines.append(f"    {m.get('mode')}: {m.get('rationale')}")
    lines.append("")
    lines.append(f"  Known issues ({len(board.get('known_issues', []))}):")
    for ki in board.get("known_issues", []):
        lines.append(f"    • {ki.get('issue')}")
        lines.append(f"        {ki.get('workaround')}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="board-advisor-x870e-creator.py")
    sub = p.add_subparsers(dest="verb", required=True)

    pst = sub.add_parser("status")
    pst.add_argument("--config", type=Path)
    fst = pst.add_mutually_exclusive_group()
    fst.add_argument("--json", dest="fmt", action="store_const", const="json")
    fst.add_argument("--human", dest="fmt", action="store_const", const="human")
    pst.set_defaults(fmt="json")

    pad = sub.add_parser("advise")
    pad.add_argument("--board", help="board name (default: all catalog entries)")
    pad.add_argument("--config", type=Path)
    fad = pad.add_mutually_exclusive_group()
    fad.add_argument("--json", dest="fmt", action="store_const", const="json")
    fad.add_argument("--human", dest="fmt", action="store_const", const="human")
    pad.set_defaults(fmt="json")

    psm = sub.add_parser("slot-map")
    psm.add_argument("--config", type=Path)
    fsm = psm.add_mutually_exclusive_group()
    fsm.add_argument("--json", dest="fmt", action="store_const", const="json")
    fsm.add_argument("--human", dest="fmt", action="store_const", const="human")
    psm.set_defaults(fmt="json")

    args = p.parse_args(argv)
    catalog, meta = load_catalog(args.config)

    if args.verb == "status":
        dmi = read_dmi()
        board = match_board(dmi, catalog)
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "dmi": dmi,
                "matched_board": board,
                "verdict": "matched" if board else "board-not-in-catalog",
                "rc": 0 if board else 1,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_status_human(dmi, board), end="")
        return 0 if board else 1

    if args.verb == "advise":
        if args.board:
            target = None
            for b in catalog:
                if isinstance(b, dict) and b.get("name") == args.board:
                    target = b
                    break
            if target is None:
                print(json.dumps({
                    "error": f"unknown board: {args.board}",
                    "known": [b.get("name") for b in catalog if isinstance(b, dict)],
                    "round": ROUND,
                }, indent=2), file=sys.stderr)
                return 1
            if args.fmt == "json":
                print(json.dumps({
                    "schema_version": SCHEMA_VERSION,
                    "round": ROUND,
                    "sdd_vector": SDD_VECTOR,
                    "board": target,
                    "overlay": meta,
                }, indent=2))
            else:
                print(render_status_human({}, target), end="")
            return 0
        # No board specified — dump full catalog.
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "total_count": len(catalog),
                "boards": catalog,
                "overlay": meta,
            }, indent=2))
        else:
            for b in catalog:
                print(render_status_human({}, b), end="")
                print("")
        return 0

    if args.verb == "slot-map":
        dmi = read_dmi()
        board = match_board(dmi, catalog)
        if board is None:
            print(json.dumps({
                "error": "host board not in catalog",
                "dmi": dmi,
                "round": ROUND,
            }, indent=2), file=sys.stderr)
            return 1
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "board_name": board.get("name"),
                "pcie_slots": board.get("pcie_slots", []),
                "m2_slots": board.get("m2_slots", []),
                "dual_gpu_bifurcation_modes": board.get("dual_gpu_bifurcation_modes", []),
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R312 PCIe/M.2 slot map: {board.get('display_name')} (E1.M32) ──")
            print()
            print("  PCIe slots:")
            for s in board.get("pcie_slots", []):
                print(f"    {s.get('label')}: {s.get('lanes')}")
                if s.get('operator_note'):
                    print(f"      {s['operator_note']}")
            print()
            print("  M.2 slots:")
            for s in board.get("m2_slots", []):
                print(f"    {s.get('label')}: {s.get('speed')}")
                if s.get('operator_note'):
                    print(f"      {s['operator_note']}")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
