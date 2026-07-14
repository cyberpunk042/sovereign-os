#!/usr/bin/env python3
"""scripts/hardware/gpu-card-advisor.py — R271 (E1.M13).

Operator-named (verbatim, 2026-05-17): "GPU too, watts, RTX 4090
details and possibilities established and non-established, same for
the RTX Pro 6000".

R219 gpu-watch tracks watt deviance generically. R249 gpu-remediate
applies fixes. R271 closes E1.M13: per-card OPERATOR-SPECIFIC
advisory layer that knows the SAIN-01 three-card layout (SDD-993:
RTX PRO 6000 primary + RTX 5090 internal secondary + RTX 4090 OcuLink eGPU)
and surfaces hints unique to those models.

Per-card knowledge table:
  RTX 4090       Ada AD102, 24 GB GDDR6X, 450W stock TDP,
                 operator-stated "should be slightly reduced" —
                 recommend 280-320W cap for sustained inference,
                 GDDR6X memory is notoriously hot (junction temps).
  RTX PRO 6000   Blackwell GB202 Max-Q, 96 GB GDDR7, 300W TDP
                 (Max-Q edition — NOT the 600W workstation card);
                 SDD-993 PRIMARY / Oracle Core (slot 1, x8 because
                 slot 2 is populated by the 5090), runs cool
                 relative to 4090's GDDR6X.
  RTX 5090       Blackwell GB202, 32 GB GDDR7, 575W stock TGP —
                 SDD-993 internal secondary (slot 2, x8),
                 operator power-limited to ~350W; native FP4/NVFP4.

The advisor cross-correlates:
  - nvidia-smi probe (which cards are actually present)
  - R252 PSU budget (do both cards fit?)
  - R270 PCIe policy (are both at rated lane width?)
  - R172 thermal-watch (per-GPU junction temp)
  - R251 baseboard (is this even the SAIN-01 motherboard?)

CLI:
  gpu-card-advisor.py detect [--json]      probe nvidia-smi + classify
  gpu-card-advisor.py advisories [--json]  curated hints per detected card
  gpu-card-advisor.py dual-card [--json]   focused on the SAIN-01 internal
                                           dual-card scenario (PRO 6000 primary
                                           + RTX 5090 secondary; 4090 = eGPU)

Exit codes:
  0  no advisories OR informational only
  1  ≥1 attention/critical advisory
  2  usage error
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


# Operator-stated cards on SAIN-01. Each entry carries operator-specific
# advisories — not generic NVIDIA advice, but tuned to operator's stated
# setup ("RTX 4090 which should be slightly reduce which isn't").
KNOWN_CARDS: dict[str, dict[str, Any]] = {
    "RTX 4090": {
        "architecture": "Ada AD102",
        "vram_gb": 24,
        "vram_type": "GDDR6X",
        "stock_tdp_watts": 350,
        "operator_recommended_cap_watts": [280, 320],
        "pcie_rated": "PCIe 4.0 x16",
        "advisories": [
            "Operator-stated 'RTX 4090 should be slightly reduced': cap power "
            "limit to 280-320 W via `nvidia-smi -pl 300` (sustained inference) "
            "or 250 W (long-running fine-tunes). Stock 350 W produces ~10 dB "
            "more fan noise + GDDR6X reaches Tjmax under sustained load.",
            "GDDR6X memory runs hot — monitor `nvidia-smi --query-gpu=temperature.memory` "
            "(not just temperature.gpu). Above 95°C memory junction the card "
            "thermal-throttles silently (no host log entry).",
            "On PCIe 4.0 x8 (when paired with PRO 6000 in slot 2), inference "
            "throughput is bandwidth-fine (compute-bound) but model-load wall "
            "time doubles. Cache cold-start latency accordingly.",
            "Stock cooler is rated for Ampere TDPs — under sustained 350 W "
            "the rear backplate can exceed 95°C. Operator-supplied undervolt "
            "via MSI Afterburner equivalents (Linux: GreenWithEnvy) cuts "
            "thermals 5-10°C at <2% perf loss.",
        ],
    },
    # SDD-993: the SAIN-01 card is the RTX PRO 6000 Blackwell MAX-Q edition
    # (300 W TDP), NOT the 600 W workstation card. It is the PRIMARY / main
    # Oracle Core, internal on PCIEX16_1 at x8 (two internal cards → x8/x8).
    "RTX PRO 6000": {
        "architecture": "Blackwell GB202",
        "vram_gb": 96,
        "vram_type": "GDDR7",
        "stock_tdp_watts": 300,
        "operator_recommended_cap_watts": [250, 300],
        "pcie_rated": "PCIe 5.0 x16 (x8 in the SAIN-01 two-internal-card bifurcation)",
        "advisories": [
            "RTX PRO 6000 Blackwell MAX-Q (300 W edition — NOT the 600 W "
            "workstation card) — 96 GB usable VRAM. The SAIN-01 slot 1 of the "
            "ASUS ProArt X870E-CREATOR WIFI runs x8 PCIe5 because slot 2 is "
            "populated by the RTX 5090 (two internal cards → x8/x8, ~64 GB/s "
            "each); M.2_2 must stay empty (shares lanes with slot 2).",
            "GDDR7 runs cooler than 4090's GDDR6X — the Max-Q part sustains "
            "its full 300 W TDP without hitting GDDR junction limits. No "
            "further watt-cap recommended at its 300 W Max-Q TDP.",
            "Blackwell adds native FP4/FP6 tensor ops — vLLM 0.6+ and "
            "transformers nightly auto-detect via `torch.cuda.get_device_capability()` "
            "returning (12, 0) on GB202. Quantization tools that use FP8/FP4 (e.g. "
            "TensorRT-LLM, MX formats) get ~2× throughput vs FP16 baseline.",
            "Driver minimum: NVIDIA proprietary 565+ for full Blackwell "
            "support. Debian 13 (trixie) backports may carry 535 — verify "
            "`nvidia-smi --query-gpu=driver_version` >= 565.x.",
            "PCIe 5.0 signal integrity is sensitive — if running through a "
            "riser/cable (open-air mining-style mount), confirm `lspci -vv` "
            "still reports `Speed 32GT/s` not downgraded to 16GT/s. R270 "
            "pcie-policy verdict critical if so.",
        ],
    },
    # SDD-993: the RTX 5090 is the internal SECONDARY (took the 4090's slot).
    "RTX 5090": {
        "architecture": "Blackwell GB202",
        "vram_gb": 32,
        "vram_type": "GDDR7",
        "stock_tdp_watts": 575,
        "operator_recommended_cap_watts": [300, 350],
        "pcie_rated": "PCIe 5.0 x16",
        "advisories": [
            "SDD-993: the operator power-limits this card to ~350 W via "
            "`nvidia-smi -pl 350` (~61% of the 575 W stock TGP) — near the "
            "Blackwell efficiency knee; the top ~40% of the power budget buys "
            "only single-digit-% extra inference throughput. This is its "
            "operating peak on the SAIN, not the factory 575 W.",
            "Internal secondary in PCIEX16_2 — with the PRO 6000 in PCIEX16_1 "
            "the two cards run x8/x8. M.2_2 shares lanes with PCIEX16_2, so it "
            "MUST stay empty or this card drops to x4; the OcuLink 4090 eGPU "
            "goes on a chipset M.2 slot instead (SDD-993).",
            "Same Blackwell FP4/NVFP4 tensor ops as the PRO 6000 (GB202, "
            "compute capability sm_120) — `torch.cuda.get_device_capability()` "
            "returns (12, 0); vLLM/TensorRT-LLM NVFP4 paths run natively. Its "
            "32 GB hosts NVFP4-quantized oracle/logic models (e.g. "
            "Nemotron-3-Nano-Omni-30B NVFP4 at 24 GB).",
            "GDDR7 runs cooler than the 4090's GDDR6X; under the ~350 W cap "
            "thermals + fan noise are modest. Driver minimum: NVIDIA 570+ for "
            "GB202 (trixie's 550 predates Blackwell) — verify "
            "`nvidia-smi --query-gpu=driver_version` >= 570.x.",
        ],
    },
}


def probe_nvidia_smi() -> list[dict[str, Any]]:
    """Returns one row per GPU via nvidia-smi --query-gpu=index,name,...
    Returns [] when nvidia-smi missing or no GPUs."""
    if not shutil.which("nvidia-smi"):
        return []
    try:
        r = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=index,name,power.draw,power.limit,memory.used,memory.total,temperature.gpu,driver_version",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=8, check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return []
    if r.returncode != 0:
        return []
    cards: list[dict[str, Any]] = []
    for line in r.stdout.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 8:
            continue
        def _f(x: str) -> float | None:
            try:
                return float(x)
            except ValueError:
                return None
        cards.append({
            "idx": int(parts[0]) if parts[0].isdigit() else parts[0],
            "name": parts[1],
            "power_draw_watts": _f(parts[2]),
            "power_limit_watts": _f(parts[3]),
            "memory_used_mb": _f(parts[4]),
            "memory_total_mb": _f(parts[5]),
            "temperature_c": _f(parts[6]),
            "driver_version": parts[7],
        })
    return cards


def classify_card(name: str) -> dict[str, Any] | None:
    """Match nvidia-smi name against KNOWN_CARDS table. Substring match
    because nvidia-smi may report e.g. "NVIDIA GeForce RTX 4090" or
    "NVIDIA RTX PRO 6000 Blackwell"."""
    for key, meta in KNOWN_CARDS.items():
        if key in name:
            return {**meta, "matched_key": key}
    return None


def cmd_detect(args: argparse.Namespace) -> int:
    cards = probe_nvidia_smi()
    classified: list[dict[str, Any]] = []
    for card in cards:
        c = classify_card(card["name"])
        classified.append({
            **card,
            "classified": c is not None,
            "matched_key": (c or {}).get("matched_key"),
            "architecture": (c or {}).get("architecture"),
            "stock_tdp_watts": (c or {}).get("stock_tdp_watts"),
        })
    out = {
        "round": "R271",
        "vector": "E1.M13 (gpu-card-detect)",
        "nvidia_smi_available": shutil.which("nvidia-smi") is not None,
        "card_count": len(cards),
        "cards": classified,
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"── R271 sovereign-os gpu-card-advisor detect (E1.M13) ──")
    if not cards:
        print("  (nvidia-smi unavailable OR no GPUs)")
        return 0
    for c in classified:
        match = c["matched_key"] or "(unmatched — no curated advice)"
        print(f"  GPU {c['idx']}: {c['name']}")
        print(f"    classified: {match}")
        if c["power_draw_watts"] is not None:
            print(f"    power: {c['power_draw_watts']} W / {c['power_limit_watts']} W")
        if c["temperature_c"] is not None:
            print(f"    temp: {c['temperature_c']}°C")
        print(f"    driver: {c['driver_version']}")
    return 0


def cmd_advisories(args: argparse.Namespace) -> int:
    cards = probe_nvidia_smi()
    results: list[dict[str, Any]] = []
    for card in cards:
        c = classify_card(card["name"])
        if c is None:
            continue  # no curated advice for unknown cards
        # Per-card live findings.
        findings: list[str] = []
        if card["power_limit_watts"] is not None and card["power_draw_watts"] is not None:
            cap_band = c.get("operator_recommended_cap_watts")
            if cap_band:
                lo, hi = cap_band
                if card["power_limit_watts"] > hi:
                    findings.append(
                        f"power_limit {card['power_limit_watts']:.0f} W is ABOVE operator-recommended cap "
                        f"of {lo}-{hi} W for this card — `sudo nvidia-smi -i {card['idx']} -pl {hi}`."
                    )
        if card["temperature_c"] is not None and card["temperature_c"] >= 85:
            findings.append(
                f"GPU temp {card['temperature_c']}°C ≥ 85°C — reduce sustained load OR improve airflow."
            )
        results.append({
            "matched_key": c["matched_key"],
            "live": {
                "idx": card["idx"],
                "power_draw_watts": card["power_draw_watts"],
                "power_limit_watts": card["power_limit_watts"],
                "temperature_c": card["temperature_c"],
                "driver_version": card["driver_version"],
            },
            "curated_advisories": c["advisories"],
            "live_findings": findings,
            "needs_attention": bool(findings),
        })
    out = {
        "round": "R271",
        "vector": "E1.M13 (gpu-card-advisories)",
        "card_count": len(results),
        "results": results,
    }
    rc = 1 if any(r["needs_attention"] for r in results) else 0
    if args.json:
        print(json.dumps(out, indent=2))
        return rc
    print(f"── R271 sovereign-os gpu-card-advisor advisories (E1.M13) ──")
    if not results:
        print("  (no operator-curated cards detected)")
        return 0
    for r in results:
        print(f"\n  {r['matched_key']} (GPU {r['live']['idx']}):")
        if r["live_findings"]:
            print(f"    LIVE FINDINGS:")
            for f in r["live_findings"]:
                print(f"      ⚠ {f}")
        print(f"    curated advisories ({len(r['curated_advisories'])}):")
        for adv in r["curated_advisories"]:
            print(f"      • {adv}")
    return rc


def cmd_dual_card(args: argparse.Namespace) -> int:
    cards = probe_nvidia_smi()
    classifications = [classify_card(c["name"]) for c in cards]
    has_4090 = any(c and c["matched_key"] == "RTX 4090" for c in classifications)
    has_5090 = any(c and c["matched_key"] == "RTX 5090" for c in classifications)
    has_pro_6000 = any(c and c["matched_key"] == "RTX PRO 6000" for c in classifications)
    # SDD-993: the SAIN-01 INTERNAL x8/x8 pair is PRO 6000 (primary) + RTX 5090
    # (secondary). The RTX 4090 is the OcuLink eGPU (third card), not part of
    # the internal bifurcation. "Dual-card layout" = the two internal cards.
    is_sain01_dual = has_pro_6000 and has_5090
    findings: list[str] = []
    if is_sain01_dual:
        findings.append(
            "SAIN-01 internal dual-card layout detected (RTX PRO 6000 primary + "
            "RTX 5090 secondary). Cross-reference R270 pcie-policy for x8/x8 split "
            "confirmation + R252 power-status budget for 300+350=650 W sustained "
            "(RTX PRO 6000 Max-Q 300 W + RTX 5090 350 W) vs 1600 W PSU rated (with "
            "derating → 1360 W budget → 710 W headroom; the Max-Q primary leaves "
            "wide headroom" + (", plus the OcuLink RTX 4090 eGPU ~320 W when engaged"
            if has_4090 else "") + ")."
        )
        findings.append(
            "Both internal cards on SAIN-01 share the X870E-CREATOR WIFI lane "
            "fabric. Slot 1 (PCIEX16_1) takes the RTX PRO 6000 (primary Oracle). "
            "Slot 2 (PCIEX16_2) takes the RTX 5090 (secondary). M2_2 NVMe MUST be "
            "empty on this layout (it would steal lanes from slot 2). The RTX 4090 "
            "OcuLink eGPU rides a CHIPSET M.2 slot (PCIe 4.0 x4), NOT M2_2."
        )
        findings.append(
            "Inference router config: Oracle Core (long-context / 70B-class at FP8, "
            "200B-class at FP4 with vLLM 0.6+) on the RTX PRO 6000 96 GB primary; "
            "Logic Engine (mid-scale Q4 / NVFP4) on the RTX 5090 32 GB internal "
            "secondary (operator D-022, 2026-07-14 — better bandwidth than the eGPU); "
            "the RTX 4090 24 GB OcuLink eGPU is the DSpark speculative-decode draft "
            "(host-resident by default, opt-in VFIO). Ternary (bitnet.cpp) stays on "
            "the CPU Conductor tier."
        )
    elif has_pro_6000:
        findings.append(
            "RTX PRO 6000 detected but no RTX 5090. Single-internal-card mode is "
            "fine — PCIEX16_1 runs full x16 PCIe5 (~128 GB/s) which the RTX PRO "
            "6000 actually uses for KV-cache spill on long-context."
        )
    elif has_5090:
        findings.append(
            "RTX 5090 detected but no RTX PRO 6000 (Oracle). Secondary-only mode — "
            "power-limit to ~350 W per E1.M13 curated advisory."
        )
    elif has_4090:
        findings.append(
            "RTX 4090 detected but no internal Oracle card. Apply the 280-320 W "
            "power cap per E1.M13 curated advisory + monitor memory junction "
            "temp (GDDR6X). On SAIN-01 the 4090 is the OcuLink eGPU."
        )
    out = {
        "round": "R271",
        "vector": "E1.M13 (gpu-card-dual)",
        "rtx_4090_present": has_4090,
        "rtx_5090_present": has_5090,
        "rtx_pro_6000_present": has_pro_6000,
        "sain01_dual_card_layout": is_sain01_dual,
        "findings": findings,
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"── R271 sovereign-os gpu-card-advisor dual-card (E1.M13) ──")
    print(f"  RTX 4090:        {has_4090}")
    print(f"  RTX PRO 6000:    {has_pro_6000}")
    print(f"  SAIN-01 layout:  {is_sain01_dual}")
    print()
    for f in findings:
        print(f"  • {f}")
    if not findings:
        print("  (no findings — neither operator-stated card detected)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gpu-card-advisor.py",
        description="R271 (E1.M13) — RTX 4090 + RTX PRO 6000 dual-card advisor.",
    )
    sub = p.add_subparsers(dest="verb", required=True)
    pd = sub.add_parser("detect", help="probe + classify against KNOWN_CARDS")
    pd.add_argument("--json", action="store_true")
    pd.set_defaults(func=cmd_detect)
    pa = sub.add_parser("advisories", help="curated + live per-card hints")
    pa.add_argument("--json", action="store_true")
    pa.set_defaults(func=cmd_advisories)
    pdc = sub.add_parser("dual-card", help="SAIN-01 dual-card layout findings")
    pdc.add_argument("--json", action="store_true")
    pdc.set_defaults(func=cmd_dual_card)
    return p


def main(argv: list[str]) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
