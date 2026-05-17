#!/usr/bin/env python3
"""scripts/hardware/bios-info.py — R251 (SDD-026 Z-17 new vector).

Operator-named (verbatim, 2026-05-17 expansion): "Memory too I guess
and bios settings directives and admonition of things that might also
not be possible on some board, possibly detecting the ASUS ProArt
X870E-CREATOR WIFI and its settings and potential optimisations and
fixes. pci lane splits and whatever like virtualization or what we
find relevant via search online and such."

Opens Z-17: the BIOS / motherboard / memory advisory surface.

Probes (all read-only, all stdlib + standard CLI tools):

  dmidecode -t bios       BIOS vendor + version + release date
  dmidecode -t baseboard  Motherboard vendor / product / version
  dmidecode -t memory     Per-DIMM capacity, speed, configured speed,
                          channel/slot, manufacturer, part_number
  /proc/cpuinfo           CPU model (cross-checked with dmidecode)
  lspci                   PCI device tree (used for lane-split heuristic)
  /sys/class/dmi/id/*     Operator-facing DMI snapshot fallback when
                          dmidecode is missing or non-root

Board-specific advisories: when the detected baseboard matches a
known operator-target (e.g. ASUS ProArt X870E-CREATOR WIFI), the
script emits operator-curated optimization hints (XMP profile state,
PCI x8/x8 split, virtualization enablement, secure boot posture).

CLI:
  bios-info.py show [--json]              full snapshot
  bios-info.py memory [--json]            DIMM-only detail
  bios-info.py advisories [--json]        board-specific hints only

Exit codes:
  0  rendered (rc=1 reserved for future "critical advisory active")
  2  usage error
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_KNOWN_BOARDS_CONFIG = Path("/etc/sovereign-os/known-boards.toml")
DEV_KNOWN_BOARDS_CONFIG = REPO_ROOT / "config" / "known-boards.toml.example"


# Operator-named board with R251 cycle-8 hardcoded advisories.
# R260 (SDD-029 R260): operators can override / extend this table by
# dropping /etc/sovereign-os/known-boards.toml (see
# config/known-boards.toml.example). Hardcoded table stays as the
# always-on baseline so the script works without a config file.
KNOWN_BOARDS: dict[str, dict[str, Any]] = {
    "ProArt X870E-CREATOR WIFI": {
        "vendor": "ASUSTeK COMPUTER INC.",
        "chipset": "AMD X870E",
        "socket": "AM5",
        "memory_channels": 2,
        "memory_max_speed_jedec": 5600,
        "memory_max_speed_exp_oc": 8000,  # ASUS-advertised OC
        "pcie_layout": {
            # Operator-readable; matches the ASUS X870E-CREATOR manual.
            "PCIEX16_1": "x16 / x8 (drops to x8 when PCIEX16_2 populated)",
            "PCIEX16_2": "x8 (active only when populated; steals from slot 1)",
            "M2_1":     "PCIe 5.0 x4 from CPU",
            "M2_2":     "PCIe 5.0 x4 from CPU (steals lanes from PCIEX16_2)",
        },
        "advisories": [
            "Enable AMD EXPO (XMP-equivalent) in BIOS to hit DDR5-6000+ — "
            "default JEDEC-5600 wastes the kit's rated speed.",
            "If running RTX 3090 + RTX PRO 6000 simultaneously, populate "
            "PCIEX16_1 AND PCIEX16_2; both drop to PCIe5 x8 which is fine "
            "for inference (~64 GB/s each).",
            "Enable SVM Mode (AMD-V) in BIOS for KVM / nspawn virtualization "
            "— off by default on some firmware revs.",
            "Enable IOMMU + ACS Override in BIOS if you plan VFIO GPU "
            "passthrough (sovereign-os Stage-3 only).",
            "ProArt X870E firmware ≥ 1303 fixes the EXPO-instability bug "
            "when paired with high-density 64GB DIMMs. Check `dmidecode -t "
            "bios` for the version + flash if older.",
            "Onboard 10 GbE (Marvell AQC113) MAY clash with cloudflared on "
            "some kernel versions; if you see TX hangs, switch to the 2.5 "
            "GbE port (Intel I226-V) or disable TSO/GSO via ethtool.",
        ],
    },
}


def run_or_none(argv: list[str]) -> str | None:
    if not shutil.which(argv[0]):
        return None
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=8, check=False)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if r.returncode != 0:
        return None
    return r.stdout


def read_dmi_id(field: str) -> str | None:
    """Fallback when dmidecode unavailable: read /sys/class/dmi/id/<field>."""
    p = Path("/sys/class/dmi/id") / field
    if not p.exists():
        return None
    try:
        return p.read_text().strip() or None
    except OSError:
        return None


def parse_dmidecode_section(text: str, section: str) -> list[dict[str, str]]:
    """Returns a list of {key: value} dicts, one per `Handle 0x...` block of
    type `<section>` (e.g. 'BIOS Information', 'Base Board Information',
    'Memory Device')."""
    blocks: list[dict[str, str]] = []
    cur: dict[str, str] | None = None
    in_target = False
    for raw_line in text.splitlines():
        if raw_line.startswith("Handle "):
            if cur is not None:
                blocks.append(cur)
                cur = None
            in_target = False
            continue
        line = raw_line.rstrip()
        if not line:
            if cur is not None:
                blocks.append(cur)
                cur = None
            in_target = False
            continue
        if not line.startswith("\t") and not line.startswith(" "):
            # Section title (e.g. "Memory Device")
            if line.strip() == section:
                in_target = True
                cur = {}
            else:
                in_target = False
                cur = None
            continue
        if in_target and cur is not None and ":" in line:
            k, _, v = line.strip().partition(":")
            cur[k.strip()] = v.strip()
    if cur is not None:
        blocks.append(cur)
    return blocks


def probe_bios() -> dict[str, Any]:
    txt = run_or_none(["dmidecode", "-t", "bios"])
    if txt:
        for blk in parse_dmidecode_section(txt, "BIOS Information"):
            return {
                "vendor": blk.get("Vendor"),
                "version": blk.get("Version"),
                "release_date": blk.get("Release Date"),
                "revision": blk.get("BIOS Revision"),
                "source": "dmidecode",
            }
    # Fallback to /sys/class/dmi/id
    vendor = read_dmi_id("bios_vendor")
    version = read_dmi_id("bios_version")
    release = read_dmi_id("bios_date")
    if any([vendor, version, release]):
        return {
            "vendor": vendor,
            "version": version,
            "release_date": release,
            "revision": None,
            "source": "sysfs",
        }
    return {"vendor": None, "version": None, "release_date": None, "source": "unavailable"}


def probe_baseboard() -> dict[str, Any]:
    txt = run_or_none(["dmidecode", "-t", "baseboard"])
    if txt:
        for blk in parse_dmidecode_section(txt, "Base Board Information"):
            return {
                "vendor": blk.get("Manufacturer"),
                "product": blk.get("Product Name"),
                "version": blk.get("Version"),
                "serial": blk.get("Serial Number"),
                "source": "dmidecode",
            }
    return {
        "vendor": read_dmi_id("board_vendor"),
        "product": read_dmi_id("board_name"),
        "version": read_dmi_id("board_version"),
        "serial": read_dmi_id("board_serial"),
        "source": "sysfs",
    }


def probe_memory() -> list[dict[str, Any]]:
    """Per-DIMM: capacity, speed (configured + rated), channel/slot, part_number."""
    txt = run_or_none(["dmidecode", "-t", "memory"])
    out: list[dict[str, Any]] = []
    if not txt:
        return out
    for blk in parse_dmidecode_section(txt, "Memory Device"):
        # Skip empty slots.
        size = blk.get("Size", "")
        if size.lower() in {"no module installed", ""}:
            continue
        out.append(
            {
                "slot": blk.get("Locator"),
                "channel": blk.get("Bank Locator"),
                "size": size,
                "type": blk.get("Type"),
                "speed_rated_mts": blk.get("Speed"),
                "speed_configured_mts": blk.get("Configured Memory Speed"),
                "manufacturer": blk.get("Manufacturer"),
                "part_number": blk.get("Part Number"),
                "rank": blk.get("Rank"),
                "form_factor": blk.get("Form Factor"),
            }
        )
    return out


def probe_pci_gpus() -> list[dict[str, Any]]:
    """Per-GPU PCIe link speed + width via lspci -vv."""
    txt = run_or_none(["lspci", "-vv"])
    out: list[dict[str, Any]] = []
    if not txt:
        return out
    cur: dict[str, Any] | None = None
    for line in txt.splitlines():
        if not line.startswith("\t") and not line.startswith(" "):
            # Device header line: 'XX:XX.X VGA compatible controller: ...'
            if cur is not None and cur.get("link_speed"):
                out.append(cur)
            if "VGA" in line or "3D controller" in line:
                parts = line.split(":", 1)
                cur = {
                    "bdf": parts[0].strip(),
                    "name": parts[1].strip() if len(parts) > 1 else "?",
                }
            else:
                cur = None
            continue
        if cur is None:
            continue
        stripped = line.strip()
        if stripped.startswith("LnkSta:"):
            # LnkSta: Speed 32GT/s (ok), Width x16 (ok)
            cur["link_speed"] = stripped[len("LnkSta:"):].strip()
        elif stripped.startswith("LnkCap:"):
            cur["link_capability"] = stripped[len("LnkCap:"):].strip()
    if cur is not None and cur.get("link_speed"):
        out.append(cur)
    return out


def resolve_known_boards_config_path() -> Path | None:
    env = os.environ.get("SOVEREIGN_OS_KNOWN_BOARDS")
    if env:
        p = Path(env)
        return p if p.exists() else None
    if DEFAULT_KNOWN_BOARDS_CONFIG.exists():
        return DEFAULT_KNOWN_BOARDS_CONFIG
    if DEV_KNOWN_BOARDS_CONFIG.exists():
        return DEV_KNOWN_BOARDS_CONFIG
    return None


def load_known_boards_from_toml(path: Path | None) -> dict[str, dict[str, Any]]:
    """R260: load operator-pull board registry. Returns merged dict
    of {board_id: { vendor, chipset, socket, memory_channels,
    memory_max_speed_jedec, memory_max_speed_exp_oc, pcie_layout,
    advisories }} compatible with the hardcoded KNOWN_BOARDS shape.

    Missing path / unparseable file = empty dict (silent — the
    hardcoded baseline still works).
    """
    if path is None or not path.exists():
        return {}
    try:
        with path.open("rb") as fh:
            doc = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for board_id, blk in (doc.get("boards") or {}).items():
        if not isinstance(blk, dict):
            continue
        # Translate TOML keys → in-memory shape.
        match_id = blk.get("match_id") or board_id
        # pcie_layout in TOML is a list of "key: description" strings;
        # the in-memory shape expects a dict. Parse on the fly.
        layout: dict[str, str] = {}
        for line in blk.get("pcie_layout") or []:
            if ":" in line:
                k, _, v = line.partition(":")
                layout[k.strip()] = v.strip()
        out[match_id] = {
            "vendor": blk.get("vendor"),
            "chipset": blk.get("chipset"),
            "socket": blk.get("socket"),
            "memory_channels": blk.get("memory_channels"),
            "memory_max_speed_jedec": blk.get("memory_max_speed_jedec_mts"),
            "memory_max_speed_exp_oc": blk.get("memory_max_speed_exp_oc_mts"),
            "pcie_layout": layout,
            "advisories": blk.get("advisories") or [],
        }
    return out


def merged_known_boards() -> dict[str, dict[str, Any]]:
    """Hardcoded baseline + TOML overrides (TOML wins on key collision)."""
    out: dict[str, dict[str, Any]] = dict(KNOWN_BOARDS)
    overrides = load_known_boards_from_toml(resolve_known_boards_config_path())
    for k, v in overrides.items():
        out[k] = v
    return out


def derive_advisories(baseboard: dict[str, Any]) -> dict[str, Any]:
    product = baseboard.get("product") or ""
    match: dict[str, Any] | None = None
    matched_id: str | None = None
    for board_id, board in merged_known_boards().items():
        if board_id in product:
            match = board
            matched_id = board_id
            break
    if match is None:
        return {
            "matched_board": None,
            "advisories": [],
            "note": (
                "no curated advisories for this baseboard yet — submit your "
                "model + tested optimization knobs to grow the KNOWN_BOARDS table"
            ),
        }
    return {
        "matched_board": matched_id,
        "board_meta": {
            "vendor": match["vendor"],
            "chipset": match["chipset"],
            "socket": match["socket"],
            "memory_channels": match["memory_channels"],
            "memory_max_speed_jedec_mts": match["memory_max_speed_jedec"],
            "memory_max_speed_exp_oc_mts": match["memory_max_speed_exp_oc"],
        },
        "pcie_layout": match["pcie_layout"],
        "advisories": match["advisories"],
    }


def cmd_show(args: argparse.Namespace) -> int:
    bios = probe_bios()
    baseboard = probe_baseboard()
    memory = probe_memory()
    pci_gpus = probe_pci_gpus()
    advisories = derive_advisories(baseboard)
    out = {
        "round": "R251",
        "vector": "SDD-026 Z-17 (bios/board/memory)",
        "bios": bios,
        "baseboard": baseboard,
        "memory": {
            "dimm_count": len(memory),
            "dimms": memory,
        },
        "pci_gpus": pci_gpus,
        "advisories": advisories,
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"── R251 sovereign-os bios-info show (SDD-026 Z-17) ──")
    print(f"\n  BIOS")
    print(f"    vendor:   {bios.get('vendor')}")
    print(f"    version:  {bios.get('version')}")
    print(f"    released: {bios.get('release_date')}  ({bios.get('source')})")
    print(f"\n  BASEBOARD")
    print(f"    vendor:   {baseboard.get('vendor')}")
    print(f"    product:  {baseboard.get('product')}")
    print(f"    version:  {baseboard.get('version')}")
    if memory:
        print(f"\n  MEMORY ({len(memory)} populated DIMM(s))")
        for d in memory:
            print(
                f"    {d.get('slot','?'):<10}  {d.get('size'):<10}  "
                f"{d.get('type','?'):<5}  rated={d.get('speed_rated_mts','?'):<12}"
                f"  configured={d.get('speed_configured_mts','?'):<12}"
                f"  {d.get('part_number','?')}"
            )
    if pci_gpus:
        print(f"\n  PCI GPU LINK STATE")
        for g in pci_gpus:
            print(f"    {g['bdf']}  {g['name']}")
            print(f"      LnkSta: {g.get('link_speed','?')}")
    if advisories.get("matched_board"):
        print(f"\n  BOARD-SPECIFIC ADVISORIES ({advisories['matched_board']})")
        for a in advisories["advisories"]:
            print(f"    • {a}")
    else:
        print(f"\n  (no curated advisories for {baseboard.get('product')!r})")
    return 0


def cmd_memory(args: argparse.Namespace) -> int:
    memory = probe_memory()
    if args.json:
        print(json.dumps({"round": "R251", "dimm_count": len(memory), "dimms": memory}, indent=2))
        return 0
    print(f"── R251 sovereign-os bios-info memory ({len(memory)} DIMM(s)) ──")
    if not memory:
        print("  (no DIMM info available — dmidecode missing or non-root)")
        return 0
    for d in memory:
        print(f"  {d.get('slot','?'):<10}  {d.get('size','?'):<10}  {d.get('type','?'):<5}")
        print(f"    rated:      {d.get('speed_rated_mts','?')}")
        print(f"    configured: {d.get('speed_configured_mts','?')}")
        print(f"    part_number:{d.get('part_number','?')}  mfr={d.get('manufacturer','?')}")
    return 0


def cmd_advisories(args: argparse.Namespace) -> int:
    advisories = derive_advisories(probe_baseboard())
    if args.json:
        print(json.dumps({"round": "R251", **advisories}, indent=2))
        return 0
    print(f"── R251 sovereign-os bios-info advisories ──")
    if not advisories.get("matched_board"):
        print(f"  {advisories.get('note','(none)')}")
        return 0
    print(f"  board: {advisories['matched_board']}")
    print()
    for a in advisories.get("advisories", []):
        print(f"  • {a}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bios-info.py",
        description="R251 (SDD-026 Z-17) — BIOS + baseboard + memory snapshot with board-specific advisories.",
    )
    sub = p.add_subparsers(dest="verb", required=True)
    ps = sub.add_parser("show", help="full snapshot")
    ps.add_argument("--json", action="store_true")
    ps.set_defaults(func=cmd_show)
    pm = sub.add_parser("memory", help="DIMM-only detail")
    pm.add_argument("--json", action="store_true")
    pm.set_defaults(func=cmd_memory)
    pa = sub.add_parser("advisories", help="board-specific optimization hints")
    pa.add_argument("--json", action="store_true")
    pa.set_defaults(func=cmd_advisories)
    return p


def main(argv: list[str]) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
