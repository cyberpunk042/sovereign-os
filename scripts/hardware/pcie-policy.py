#!/usr/bin/env python3
"""scripts/hardware/pcie-policy.py — R270 (E1.M12).

Operator-named (verbatim, 2026-05-17 mandate): "pci lane splits and
whatever like virtualization or what we find relevant via search
online and such."

R255 ships generic virt-info pci sub-probe (LnkSta width + speed
per device). R270 closes E1.M12: PCIe lane-allocation POLICY layer
— derives whether each GPU is running at its rated lane width, when
NVMe drives are stealing lanes from a GPU slot (board-specific
contention), and operator-actionable hints for X870E + Z890 +
similar known-lane-sharing boards.

Probes:
  lspci -vv → LnkSta + LnkCap per PCIe device
  baseboard product from R251 → board-specific lane-share table

Per-device finding:
  device          BDF + name
  current_width   x16 / x8 / x4 / x1
  capable_width   max width the slot supports
  current_speed   16GT/s (PCIe 4.0) / 32GT/s (PCIe 5.0) / 64GT/s (PCIe 6.0)
  capable_speed   max speed the slot supports
  degradation     "ok" / "width-degraded" / "speed-degraded" / "both"
  advisory        operator hint when degraded

Policy verdict:
  ok        every GPU at rated width + speed
  attention ≥1 device width OR speed below capable
  critical  ≥1 device dropped to x1 OR x4 when capable is x16

CLI:
  pcie-policy.py status [--json]    per-device degradation table
  pcie-policy.py share [--json]     known board-specific lane-share map

Exit codes:
  0  ok / informational
  1  attention or critical
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


# Known board lane-share rules. operator-pull table.
BOARD_LANE_RULES: dict[str, dict[str, Any]] = {
    "ProArt X870E-CREATOR WIFI": {
        "rules": [
            {
                "trigger": "M2_2 populated",
                "effect": "PCIEX16_2 drops from x8 to (M2_2 takes those lanes)",
                "operator_hint": (
                    "On ProArt X870E-CREATOR WIFI: M2_2 NVMe and PCIEX16_2 "
                    "share lanes off the CPU. Populating M2_2 disables PCIE5 "
                    "on PCIEX16_2 — your second GPU loses its connection. "
                    "Either use the chipset-attached M.2 slots (M2_3/M2_4) "
                    "for high-frequency-write NVMe, OR accept the trade-off."
                ),
            },
            {
                "trigger": "PCIEX16_2 populated",
                "effect": "PCIEX16_1 drops from x16 to x8 (bifurcation)",
                "operator_hint": (
                    "Both PCIEX16_1 and PCIEX16_2 active → both run at PCIe5 "
                    "x8 (~64 GB/s each). Fine for AI inference (compute-bound, "
                    "not bandwidth-bound). If running ONE GPU only, populate "
                    "PCIEX16_1 alone to keep the full x16."
                ),
            },
            {
                "trigger": "RTX PRO 6000 at <x16",
                "effect": "RTX PRO 6000 not running at rated PCIe5 x16 — "
                          "bandwidth halved during long-context inference",
                "operator_hint": (
                    "RTX PRO 6000 is designed for PCIe5 x16. If lspci reports "
                    "x8 OR PCIe4 speed, check: (1) second GPU populated → "
                    "expected x8 trade-off; (2) board firmware ≥ 1303 for "
                    "PCIe5 stability fix; (3) cable / riser quality (PCIe5 "
                    "is very sensitive to signal integrity)."
                ),
            },
        ],
    },
}


def parse_lspci_lnk() -> list[dict[str, Any]]:
    """Returns one row per PCI device with link state."""
    if not shutil.which("lspci"):
        return []
    try:
        r = subprocess.run(
            ["lspci", "-vv"], capture_output=True, text=True,
            timeout=10, check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return []
    if r.returncode != 0:
        return []

    devices: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None
    for line in r.stdout.splitlines():
        if not line.startswith("\t") and not line.startswith(" "):
            if cur is not None:
                devices.append(cur)
            parts = line.split(":", 1)
            bdf = parts[0].strip() if parts else ""
            name = parts[1].strip() if len(parts) > 1 else ""
            cur = {"bdf": bdf, "name": name}
            continue
        if cur is None:
            continue
        stripped = line.strip()
        if stripped.startswith("LnkCap:"):
            cur["lnk_cap_raw"] = stripped[len("LnkCap:"):].strip()
        elif stripped.startswith("LnkSta:"):
            cur["lnk_sta_raw"] = stripped[len("LnkSta:"):].strip()
    if cur is not None:
        devices.append(cur)
    return devices


def parse_lnk_field(raw: str) -> dict[str, str]:
    """'Speed 32GT/s, Width x16' → {speed, width}."""
    out: dict[str, str] = {}
    for tok in raw.split(","):
        tok = tok.strip()
        if tok.startswith("Speed "):
            out["speed"] = tok.split(" ", 1)[1].split("(")[0].strip()
        elif tok.startswith("Width "):
            out["width"] = tok.split(" ", 1)[1].split("(")[0].strip()
        # LnkCap formats differ; second part of "Port #1, Speed 32GT/s, Width x16"
        elif "Speed " in tok:
            out["speed"] = tok.split("Speed ", 1)[1].split("(")[0].strip()
        elif "Width " in tok:
            out["width"] = tok.split("Width ", 1)[1].split("(")[0].strip()
    return out


def speed_to_pcie_gen(speed: str) -> str:
    """'32GT/s' → 'PCIe5.0'."""
    m = re.match(r"(\d+(?:\.\d+)?)\s*GT/s", speed)
    if not m:
        return "?"
    val = float(m.group(1))
    if val >= 64:
        return "PCIe6.0"
    if val >= 32:
        return "PCIe5.0"
    if val >= 16:
        return "PCIe4.0"
    if val >= 8:
        return "PCIe3.0"
    if val >= 5:
        return "PCIe2.0"
    return "PCIe1.x"


def is_interesting(name: str) -> bool:
    n = name.lower()
    return any(k in n for k in ("vga", "3d controller", "nvm express", "ethernet"))


def classify_device(d: dict[str, Any]) -> dict[str, Any]:
    sta = parse_lnk_field(d.get("lnk_sta_raw", ""))
    cap = parse_lnk_field(d.get("lnk_cap_raw", ""))
    cur_w = sta.get("width")
    cap_w = cap.get("width")
    cur_s = sta.get("speed")
    cap_s = cap.get("speed")
    width_deg = (cur_w and cap_w and cur_w != cap_w)
    speed_deg = (cur_s and cap_s and cur_s != cap_s)
    if width_deg and speed_deg:
        degradation = "both"
    elif width_deg:
        degradation = "width-degraded"
    elif speed_deg:
        degradation = "speed-degraded"
    else:
        degradation = "ok"
    # Severity: x1/x4 GPU when capable x16 = critical; otherwise attention.
    severity = "ok"
    if degradation != "ok":
        if cur_w in {"x1", "x4"} and cap_w == "x16" and "VGA" in d.get("name", ""):
            severity = "critical"
        else:
            severity = "attention"
    return {
        **d,
        "current_width": cur_w,
        "capable_width": cap_w,
        "current_speed": cur_s,
        "capable_speed": cap_s,
        "current_pcie_gen": speed_to_pcie_gen(cur_s or ""),
        "capable_pcie_gen": speed_to_pcie_gen(cap_s or ""),
        "degradation": degradation,
        "severity": severity,
    }


def probe_baseboard_product() -> str | None:
    if not shutil.which("dmidecode"):
        return Path("/sys/class/dmi/id/board_name").read_text().strip() \
            if Path("/sys/class/dmi/id/board_name").exists() else None
    try:
        r = subprocess.run(
            ["dmidecode", "-t", "baseboard"], capture_output=True, text=True,
            timeout=5, check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if r.returncode != 0:
        return None
    for line in r.stdout.splitlines():
        if "Product Name:" in line:
            return line.split(":", 1)[1].strip()
    return None


def cmd_status(args: argparse.Namespace) -> int:
    raw = parse_lspci_lnk()
    interesting = [d for d in raw if is_interesting(d.get("name", "")) and d.get("lnk_sta_raw")]
    classified = [classify_device(d) for d in interesting]
    summary = {
        "ok": sum(1 for c in classified if c["severity"] == "ok"),
        "attention": sum(1 for c in classified if c["severity"] == "attention"),
        "critical": sum(1 for c in classified if c["severity"] == "critical"),
        "total": len(classified),
    }
    if summary["critical"] > 0:
        verdict = "critical"
    elif summary["attention"] > 0:
        verdict = "attention"
    elif summary["total"] == 0:
        verdict = "unavailable"
    else:
        verdict = "ok"
    out = {
        "round": "R270",
        "vector": "E1.M12 (pcie-lane-policy)",
        "lspci_available": shutil.which("lspci") is not None,
        "verdict": verdict,
        "summary": summary,
        "devices": classified,
    }
    rc = 1 if verdict in {"attention", "critical"} else 0
    if args.json:
        print(json.dumps(out, indent=2))
        return rc
    print(f"── R270 sovereign-os pcie-policy status (E1.M12) ──")
    if not classified:
        print("  (lspci unavailable OR no interesting devices)")
        return rc
    for c in classified:
        mark = {"ok": "✓", "attention": "⚠", "critical": "⛔"}.get(c["severity"], "?")
        print(f"  {mark} {c['bdf']}  {c['name']}")
        print(f"      current: {c['current_width']} {c['current_pcie_gen']}  "
              f"capable: {c['capable_width']} {c['capable_pcie_gen']}  "
              f"deg={c['degradation']}")
    print(f"\n  verdict: {verdict}  (ok={summary['ok']} attention={summary['attention']} critical={summary['critical']})")
    return rc


def cmd_share(args: argparse.Namespace) -> int:
    product = probe_baseboard_product()
    rules = []
    matched = None
    if product:
        for board_id, board in BOARD_LANE_RULES.items():
            if board_id in product:
                matched = board_id
                rules = board.get("rules") or []
                break
    out = {
        "round": "R270",
        "vector": "E1.M12 (board-specific lane-share rules)",
        "baseboard_product": product,
        "matched_board": matched,
        "rule_count": len(rules),
        "rules": rules,
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"── R270 sovereign-os pcie-policy share (E1.M12) ──")
    print(f"  baseboard: {product or '(unknown)'}")
    if not matched:
        print(f"  (no curated lane-share rules for this board yet)")
        return 0
    print(f"  matched:   {matched}")
    print(f"  rules ({len(rules)}):")
    for r in rules:
        print(f"\n  trigger: {r['trigger']}")
        print(f"    effect: {r['effect']}")
        print(f"    hint:   {r['operator_hint']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pcie-policy.py",
        description="R270 (E1.M12) — PCIe lane allocation policy advisor.",
    )
    sub = p.add_subparsers(dest="verb", required=True)
    ps = sub.add_parser("status", help="per-device degradation table")
    ps.add_argument("--json", action="store_true")
    ps.set_defaults(func=cmd_status)
    pl = sub.add_parser("share", help="board-specific lane-share rules")
    pl.add_argument("--json", action="store_true")
    pl.set_defaults(func=cmd_share)
    return p


def main(argv: list[str]) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
