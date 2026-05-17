#!/usr/bin/env python3
"""scripts/hardware/memory-profile.py — R257 (SDD-026 Z-17 follow-up).

Operator-named (verbatim, 2026-05-17 expansion): "considering XMP
profile and OC profile and room for each and estimated at 100% usage
and then real time tracking and intelligence around it."

R251 ships the raw DIMM probe (rated_speed vs configured_speed via
dmidecode). R257 ships the OPINIONATED diff: per-DIMM whether the
operator's configured RAM speed matches its rated speed — surfaces
the XMP/EXPO-not-enabled scenario with an actionable BIOS hint.

Logic:
  - dmidecode -t memory → per-DIMM Speed (rated) + Configured Memory
    Speed (live JEDEC or XMP/EXPO).
  - When rated > configured by ≥10% → operator left their RAM on the
    JEDEC default. Emit advisory: "enable XMP (Intel) / EXPO (AMD)
    in BIOS to recover ~N% memory bandwidth."
  - When configured > rated → operator manually OC'd. Note the
    overclock + warn about stability if extreme.
  - When configured == rated → operator's XMP/EXPO is honored. Green.
  - Cross-reference with R251 baseboard-product → cite the matching
    BIOS-advisory if available (e.g. ASUS X870E EXPO firmware fix).

CLI:
  memory-profile.py status [--json]   per-DIMM verdict
  memory-profile.py advisory [--json] only the actionable hint

Exit codes:
  0  every DIMM at rated speed (or no DIMM info available)
  1  ≥1 DIMM under-clocked (XMP/EXPO not enabled — operator action)
  2  usage error
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def parse_mts(value: str) -> int | None:
    """'5600 MT/s' → 5600; returns None for 'Unknown', '', etc."""
    if not value or value.lower() in {"unknown", "none"}:
        return None
    m = re.search(r"(\d+)", value)
    if m is None:
        return None
    return int(m.group(1))


def probe_baseboard_product() -> str | None:
    """Same logic as bios-info.py — reuse via subprocess."""
    if not shutil.which("dmidecode"):
        sysfs = Path("/sys/class/dmi/id/board_name")
        if sysfs.exists():
            try:
                return sysfs.read_text().strip() or None
            except OSError:
                return None
        return None
    try:
        r = subprocess.run(
            ["dmidecode", "-t", "baseboard"],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if r.returncode != 0:
        return None
    for line in r.stdout.splitlines():
        if "Product Name:" in line:
            return line.split(":", 1)[1].strip()
    return None


def probe_dimms() -> list[dict[str, Any]]:
    """Per-DIMM with rated_mts + configured_mts + delta_pct + verdict."""
    txt = ""
    if shutil.which("dmidecode"):
        try:
            r = subprocess.run(
                ["dmidecode", "-t", "memory"],
                capture_output=True, text=True, timeout=5, check=False,
            )
            if r.returncode == 0:
                txt = r.stdout
        except (subprocess.TimeoutExpired, OSError):
            pass
    if not txt:
        return []
    out: list[dict[str, Any]] = []
    cur: dict[str, str] | None = None
    in_block = False
    for line in txt.splitlines():
        if line.startswith("Handle "):
            if cur is not None:
                out.append(cur)
            cur = None
            in_block = False
            continue
        if not line.startswith("\t") and not line.startswith(" "):
            in_block = (line.strip() == "Memory Device")
            cur = {} if in_block else None
            continue
        if in_block and cur is not None and ":" in line:
            k, _, v = line.strip().partition(":")
            cur[k.strip()] = v.strip()
    if cur is not None:
        out.append(cur)
    # Filter populated + classify.
    rows: list[dict[str, Any]] = []
    for blk in out:
        size = blk.get("Size", "")
        if size.lower() in {"no module installed", ""}:
            continue
        rated = parse_mts(blk.get("Speed", ""))
        configured = parse_mts(blk.get("Configured Memory Speed", ""))
        if rated and configured:
            delta_pct = (configured - rated) / rated * 100.0
        else:
            delta_pct = None
        if rated is None or configured is None:
            verdict = "unknown"
        elif abs(delta_pct or 0) < 2.0:
            verdict = "at-rated"
        elif (delta_pct or 0) < -10.0:
            verdict = "underclocked-xmp-disabled"
        elif (delta_pct or 0) < -2.0:
            verdict = "slightly-underclocked"
        elif (delta_pct or 0) > 10.0:
            verdict = "manually-overclocked"
        else:
            verdict = "slightly-overclocked"
        rows.append({
            "slot": blk.get("Locator"),
            "size": blk.get("Size"),
            "type": blk.get("Type"),
            "rated_mts": rated,
            "configured_mts": configured,
            "delta_pct": round(delta_pct, 1) if delta_pct is not None else None,
            "verdict": verdict,
            "manufacturer": blk.get("Manufacturer"),
            "part_number": blk.get("Part Number"),
        })
    return rows


def derive_advisory(dimms: list[dict[str, Any]], product: str | None) -> dict[str, Any]:
    if not dimms:
        return {"verdict": "no-data", "message": None}
    underclocked = [d for d in dimms if d["verdict"] == "underclocked-xmp-disabled"]
    over = [d for d in dimms if d["verdict"] == "manually-overclocked"]
    if underclocked:
        avg_recovery = sum((d["rated_mts"] - d["configured_mts"])
                           for d in underclocked) // len(underclocked)
        # Detect AMD vs Intel via product name heuristic.
        amd_hint = ""
        if product and any(s in product for s in ("X870", "X670", "B650", "B850")):
            amd_hint = "AMD EXPO"
        elif product and any(s in product for s in ("Z790", "Z890", "B760")):
            amd_hint = "Intel XMP"
        else:
            amd_hint = "XMP/EXPO"
        return {
            "verdict": "xmp-expo-disabled",
            "underclocked_count": len(underclocked),
            "avg_recovery_mts": avg_recovery,
            "message": (
                f"{len(underclocked)} DIMM(s) running JEDEC-default speed "
                f"({underclocked[0]['configured_mts']} MT/s) instead of rated "
                f"{underclocked[0]['rated_mts']} MT/s. Enable {amd_hint} in "
                f"BIOS to recover ~{avg_recovery} MT/s of memory bandwidth."
            ),
        }
    if over:
        return {
            "verdict": "manually-overclocked",
            "overclocked_count": len(over),
            "message": (
                f"{len(over)} DIMM(s) manually overclocked above rated speed. "
                "Confirm stability with `memtest86+` if you haven't already."
            ),
        }
    return {
        "verdict": "ok",
        "message": (
            "Every populated DIMM is running at or near its rated speed — "
            "XMP/EXPO honored (or no headroom available)."
        ),
    }


def cmd_status(args: argparse.Namespace) -> int:
    dimms = probe_dimms()
    product = probe_baseboard_product()
    advisory = derive_advisory(dimms, product)
    out = {
        "round": "R257",
        "vector": "SDD-026 Z-17 follow-up (memory-profile)",
        "baseboard_product": product,
        "dimm_count": len(dimms),
        "dimms": dimms,
        "advisory": advisory,
    }
    rc = 1 if advisory.get("verdict") == "xmp-expo-disabled" else 0
    if args.json:
        print(json.dumps(out, indent=2))
        return rc
    print(f"── R257 sovereign-os memory-profile status (SDD-026 Z-17 follow-up) ──")
    print(f"  baseboard: {product or '(unknown)'}")
    if not dimms:
        print(f"  (no DIMM data — dmidecode missing or non-root)")
        return 0
    print(f"  populated DIMM(s): {len(dimms)}")
    for d in dimms:
        glyph = {
            "at-rated": "✓",
            "slightly-overclocked": "✓",
            "manually-overclocked": "↑",
            "slightly-underclocked": "·",
            "underclocked-xmp-disabled": "⚠",
            "unknown": "?",
        }.get(d["verdict"], "?")
        print(f"  {glyph} {d['slot']:<10}  {d['size']}  rated={d['rated_mts']} MT/s  "
              f"configured={d['configured_mts']} MT/s  Δ={d['delta_pct']}%  "
              f"({d['verdict']})")
    if advisory.get("message"):
        print(f"\n  advisory: {advisory['message']}")
    return rc


def cmd_advisory(args: argparse.Namespace) -> int:
    dimms = probe_dimms()
    product = probe_baseboard_product()
    advisory = derive_advisory(dimms, product)
    out = {
        "round": "R257",
        "vector": "SDD-026 Z-17 follow-up (memory-profile advisory)",
        "baseboard_product": product,
        **advisory,
    }
    rc = 1 if advisory.get("verdict") == "xmp-expo-disabled" else 0
    if args.json:
        print(json.dumps(out, indent=2))
        return rc
    print(f"── R257 sovereign-os memory-profile advisory ──")
    print(f"  verdict: {advisory.get('verdict')}")
    if advisory.get("message"):
        print(f"\n  {advisory['message']}")
    return rc


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="memory-profile.py",
        description="R257 (SDD-026 Z-17 follow-up) — DIMM rated vs configured speed verdict.",
    )
    sub = p.add_subparsers(dest="verb", required=True)
    for name, fn, helptxt in [
        ("status", cmd_status, "per-DIMM verdict"),
        ("advisory", cmd_advisory, "actionable XMP/EXPO hint"),
    ]:
        sp = sub.add_parser(name, help=helptxt)
        sp.add_argument("--json", action="store_true")
        sp.set_defaults(func=fn)
    return p


def main(argv: list[str]) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
