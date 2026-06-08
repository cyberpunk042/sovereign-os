#!/usr/bin/env python3
"""scripts/hardware/bios-directives.py — R299 (E1.M24).

Operator-named (§1b mandate row, verbatim): "bios settings directives
and admonition of things that might also not be possible on some
board, possibly detecting the ASUS ProArt X870E-CREATOR WIFI and its
settings and potential optimisations and fixes". Closes E1.M24.

A STRUCTURED catalog of BIOS-level settings the operator should
configure on the SAIN-01 reference board (ASUS ProArt X870E-CREATOR
WIFI), with per-setting:

  - menu_path        — BIOS menu hierarchy (Advanced > AMD CBS > ...)
  - recommended      — operator-recommended value
  - default          — board's factory-default (for diff calc)
  - rationale        — operator-readable WHY
  - workload_axis    — which workload(s) this setting affects (XMP /
                        OC / virt / VFIO / AVX-512 / etc)
  - can_probe        — can sovereign-os runtime confirm this setting
                        is applied? (some are only verifiable from BIOS)
  - probe_command    — when can_probe=true, the command + expected match
  - operator_caveat  — board / firmware constraints

R251 (bios-info) already ships text advisories. R299 promotes them
to STRUCTURED directives with per-setting verification surface.

CLI:
  bios-directives.py list  [--axis X] [--config P] [--json|--human]
  bios-directives.py show  <setting> [--config P] [--json|--human]
  bios-directives.py check [--config P] [--json|--human]
                            run can_probe commands + compare to
                            recommended values; rc=1 if any mismatch

Operator-overlay (R283/SDD-030): /etc/sovereign-os/bios-directives.toml
adds/replaces directives.

Exit codes:
  0  rendered / all probable settings match recommended
  1  ≥1 probe mismatched recommended OR unknown setting
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

REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
try:
    from operator_overlay import load_with_overlay  # type: ignore
except Exception:  # pragma: no cover
    load_with_overlay = None


SCHEMA_VERSION = "1.0.0"
ROUND = "R299"
SDD_VECTOR = "E1.M24"


# ── BIOS directives catalog ─────────────────────────────────────────
DEFAULT_DIRECTIVES: list[dict[str, Any]] = [
    {
        "name": "AMD EXPO",
        "menu_path": "Ai Tweaker > Ai Overclock Tuner > [EXPO I]",
        "recommended": "EXPO I (or EXPO II for tightened sub-timings)",
        "default": "Auto (JEDEC-5600)",
        "rationale": "JEDEC default wastes the kit's rated 6000+ MT/s. "
                     "EXPO unlocks the operator's pinned XMP profile.",
        "workload_axis": ["xmp", "memory-bandwidth", "ai-inference"],
        "can_probe": True,
        "probe_command": "dmidecode -t memory | grep -E 'Configured.*Speed'",
        "probe_match": "Configured Memory Speed: 6000",
        "operator_caveat": "ProArt X870E firmware ≥ 1303 fixes the "
                           "EXPO-instability bug on 64GB-density DIMMs.",
    },
    {
        "name": "SVM Mode",
        "menu_path": "Advanced > CPU Configuration > SVM Mode > [Enabled]",
        "recommended": "Enabled",
        "default": "Disabled (some firmware revs)",
        "rationale": "AMD-V virtualization; required for KVM / nspawn / "
                     "containers using user-space hardware acceleration.",
        "workload_axis": ["virt", "kvm", "nspawn"],
        "can_probe": True,
        "probe_command": "grep -E '^flags' /proc/cpuinfo | head -1",
        "probe_match": "svm",
        "operator_caveat": None,
    },
    {
        "name": "IOMMU",
        "menu_path": "Advanced > AMD CBS > NBIO Common Options > IOMMU > [Enabled]",
        "recommended": "Enabled",
        "default": "Auto (often disabled)",
        "rationale": "Required for VFIO GPU passthrough (Stage-3+ "
                     "virt workloads), DMA protection, and certain "
                     "kernel hardening.",
        "workload_axis": ["virt", "vfio", "security"],
        "can_probe": True,
        "probe_command": "ls /sys/kernel/iommu_groups/",
        "probe_match": "(nonzero number of entries)",
        "operator_caveat": "Also requires `iommu=pt amd_iommu=on` on the "
                           "kernel cmdline.",
    },
    {
        "name": "Above 4G Decoding",
        "menu_path": "Advanced > PCI Subsystem Settings > Above 4G Decoding > [Enabled]",
        "recommended": "Enabled",
        "default": "Auto",
        "rationale": "Required for large PCI BAR allocations (Resizable "
                     "BAR for GPUs). Without it, RTX PRO 6000's 98 GB "
                     "VRAM map fails.",
        "workload_axis": ["gpu", "rebar", "ai-inference"],
        "can_probe": True,
        "probe_command": "lspci -vv | grep -A 1 'Region.*Memory.*64-bit'",
        "probe_match": "(64-bit BAR entries present)",
        "operator_caveat": "Disable CSM to allow Above 4G + Re-Size BAR.",
    },
    {
        "name": "Re-Size BAR Support",
        "menu_path": "Advanced > PCI Subsystem Settings > Re-Size BAR Support > [Enabled]",
        "recommended": "Enabled",
        "default": "Disabled",
        "rationale": "Lets CPU access full GPU VRAM in one mapping "
                     "instead of 256 MB windows; required by modern "
                     "CUDA + Vulkan paths for max throughput.",
        "workload_axis": ["gpu", "rebar", "ai-inference"],
        "can_probe": True,
        "probe_command": "nvidia-smi --query-gpu=resizable_bar --format=csv,noheader",
        "probe_match": "Enabled",
        "operator_caveat": "Both BIOS AND nvidia driver must agree; "
                           "ReBAR off in driver makes BIOS setting "
                           "moot.",
    },
    {
        "name": "PCIe Gen Speed (PCIEX16_1)",
        "menu_path": "Advanced > AMD CBS > PCIe / GFX Configuration > PCIEX16_1 > [Gen5]",
        "recommended": "Gen5 (or Auto)",
        "default": "Auto",
        "rationale": "RTX PRO 6000 + RTX 3090 dual-card means both "
                     "drop to x8. Gen5 x8 = Gen4 x16 bandwidth. Force "
                     "Gen5 to keep tensor-parallel split happy.",
        "workload_axis": ["pcie", "dual-gpu", "ai-inference"],
        "can_probe": True,
        "probe_command": "lspci -vv | grep 'LnkSta:' | head -2",
        "probe_match": "Speed 32GT/s",  # Gen5
        "operator_caveat": "Cable / riser quality can force fallback "
                           "to Gen4 at runtime even if BIOS = Gen5.",
    },
    {
        "name": "AVX-512 Support",
        "menu_path": "Advanced > AMD CBS > CPU Common Options > AVX-512 Support > [Enabled]",
        "recommended": "Enabled",
        "default": "Auto",
        "rationale": "Zen5 9900X ships full AVX-512 (VNNI + BF16 + FP16 "
                     "+ VBMI2). DISABLING it would kill the bitnet.cpp "
                     "VPDPBUSD ternary fast path (master spec §17).",
        "workload_axis": ["cpu", "avx512", "ai-inference", "ternary"],
        "can_probe": True,
        "probe_command": "grep -E '^flags' /proc/cpuinfo | head -1",
        "probe_match": "avx512f",
        "operator_caveat": "Some early AGESA disabled AVX-512 by "
                           "default. Verify after every BIOS flash.",
    },
    {
        "name": "Q-Fan Control (fan curves)",
        "menu_path": "Monitor > Q-Fan Configuration > "
                     "CPU/Chassis Fan Q-Fan Control > [Manual/Turbo]",
        "recommended": "Manual (early-ramp curve) or Turbo",
        "default": "Standard",
        "rationale": "An AI host runs sustained GPU + AVX-512 CPU load, so "
                     "the chassis/CPU fans must ramp BEFORE thermals climb, "
                     "not after. The default Standard curve is tuned for "
                     "bursty desktop loads and lets temps drift up under "
                     "sustained inference — the exact condition R296 "
                     "thermal-oc-budget + R316 wattage-heat-trend warn about. "
                     "A Manual early-ramp curve (or Turbo) keeps thermal "
                     "headroom so the GPUs don't hit their own throttle "
                     "point first.",
        "workload_axis": ["thermal", "ai-inference", "sustained-load"],
        "can_probe": False,
        "probe_command": None,
        "probe_match": None,
        "operator_caveat": "BIOS Q-Fan curves aren't OS-visible to set, but "
                           "fan RPMs ARE readable — cross-check actual "
                           "ramp behaviour with `sovereign-osctl thermal "
                           "status` (R172 thermal-watch reads hwmon fan "
                           "tachometers) under a sustained load.",
    },
    {
        "name": "Fast Boot",
        "menu_path": "Boot > Fast Boot > [Disabled]",
        "recommended": "Disabled",
        "default": "Enabled",
        "rationale": "Operator workflow needs full POST visibility "
                     "+ predictable boot timing. Fast Boot skips PCIe "
                     "/ RAM training, which can mask EXPO failures.",
        "workload_axis": ["boot", "diagnostics"],
        "can_probe": False,
        "probe_command": None,
        "probe_match": None,
        "operator_caveat": None,
    },
    {
        "name": "CSM (Compatibility Support Module)",
        "menu_path": "Boot > CSM (Compatibility Support Module) > [Disabled]",
        "recommended": "Disabled",
        "default": "Auto",
        "rationale": "Required for Re-Size BAR / Above 4G Decoding + "
                     "UEFI Secure Boot. Operator-mandated UEFI-only "
                     "boot path.",
        "workload_axis": ["uefi", "rebar", "secureboot"],
        "can_probe": True,
        "probe_command": "[ -d /sys/firmware/efi ] && echo UEFI || echo BIOS",
        "probe_match": "UEFI",
        "operator_caveat": None,
    },
    {
        "name": "Onboard 2.5GbE (Intel I226-V)",
        "menu_path": "Advanced > Onboard Devices Configuration > Intel I226-V > [Enabled]",
        "recommended": "Enabled",
        "default": "Enabled",
        "rationale": "Reliable LAN baseline. Onboard 10 GbE (Marvell "
                     "AQC113) MAY clash with cloudflared on some "
                     "kernel revs — keep 2.5 GbE as fallback.",
        "workload_axis": ["network"],
        "can_probe": True,
        "probe_command": "lspci | grep -i 'I226'",
        "probe_match": "I226",
        "operator_caveat": "If TX hangs on 10 GbE, disable TSO/GSO via "
                           "`ethtool -K <iface> tso off gso off`.",
    },
    {
        "name": "CPU PBO (Precision Boost Overdrive)",
        "menu_path": "Advanced > AMD Overclocking > Precision Boost Overdrive > [Advanced]",
        "recommended": "Advanced (operator-tuned curves)",
        "default": "Auto",
        "rationale": "Zen5 9900X PBO unlocks higher sustained "
                     "all-core boost when thermal headroom allows. "
                     "PAIR with sovereign-osctl thermal-oc-budget "
                     "to stay safe.",
        "workload_axis": ["cpu", "oc", "ai-inference"],
        "can_probe": False,
        "probe_command": None,
        "probe_match": None,
        "operator_caveat": "PBO Advanced requires curve-optimizer "
                           "stability testing per chip — sample-of-one.",
    },
    {
        "name": "Memory Context Restore",
        "menu_path": "Advanced > AMD CBS > UMC Common Options > Memory Context Restore > [Enabled]",
        "recommended": "Enabled",
        "default": "Disabled",
        "rationale": "Skips RAM training on subsequent boots if "
                     "config unchanged — operator saves ~20s per boot.",
        "workload_axis": ["boot", "memory"],
        "can_probe": False,
        "probe_command": None,
        "probe_match": None,
        "operator_caveat": "Disable if you frequently change DIMMs / "
                           "RAM-train every boot for stability.",
    },
]


# ── Lookups + assemble ─────────────────────────────────────────────
def load_directives(overlay_path: Path | None) -> tuple[list[dict], dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    catalog = list(DEFAULT_DIRECTIVES)
    if load_with_overlay is not None:
        cfg = load_with_overlay(
            "bios-directives",
            {"directives": []},
            explicit_path=overlay_path,
        )
        meta["_source"] = cfg.get("_source", meta["_source"])
        meta["_overlay_keys"] = cfg.get("_overlay_keys", [])
        if cfg.get("_parse_error"):
            meta["_parse_error"] = cfg["_parse_error"]
        if cfg.get("directives"):
            catalog = list(cfg["directives"])
    return catalog, meta


def filter_axis(catalog: list[dict], axis: str | None) -> list[dict]:
    if axis is None:
        return list(catalog)
    return [d for d in catalog
            if isinstance(d, dict) and axis in (d.get("workload_axis") or [])]


def resolve_setting(catalog: list[dict], name: str) -> dict | None:
    for d in catalog:
        if isinstance(d, dict) and d.get("name") == name:
            return d
    return None


# ── Probe runner ────────────────────────────────────────────────────
def run_probe(setting: dict) -> dict[str, Any]:
    if not setting.get("can_probe") or not setting.get("probe_command"):
        return {"probable": False, "match": None,
                "detail": "setting is not runtime-probable from sovereign-os"}
    cmd = setting["probe_command"]
    # Use shell since probe commands include pipes / grep.
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=8, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"probable": True, "match": None,
                "detail": f"probe command failed: {e}"}
    output = r.stdout.strip()
    expected = setting.get("probe_match", "")
    if expected.startswith("(") and expected.endswith(")"):
        # "(64-bit BAR entries present)" — heuristic check: nonzero stdout
        match = bool(output)
    else:
        match = expected in output
    return {
        "probable": True,
        "match": match,
        "stdout_preview": output[:200],
        "detail": (f"probe-match" if match else f"probe-mismatch — "
                   f"expected `{expected}` not found"),
    }


# ── Renderers ───────────────────────────────────────────────────────
def render_list_human(entries: list[dict], meta: dict) -> str:
    lines = ["── R299 sovereign-os BIOS directives (E1.M24) ──"]
    lines.append(f"  source:    {meta.get('_source')}")
    lines.append(f"  entries:   {len(entries)}")
    lines.append(f"  board:     ASUS ProArt X870E-CREATOR WIFI (operator-pinned)")
    lines.append("")
    for d in entries:
        if not isinstance(d, dict):
            continue
        probable_mark = "✓-probable" if d.get("can_probe") else "  bios-only"
        axes = ", ".join(d.get("workload_axis") or [])
        lines.append(f"  • {d.get('name')}   [{probable_mark}]")
        lines.append(f"      axes:        {axes}")
        lines.append(f"      recommend:   {d.get('recommended')}")
    return "\n".join(lines) + "\n"


def render_show_human(d: dict) -> str:
    lines = [f"── R299 BIOS directive: {d.get('name')} (E1.M24) ──"]
    lines.append(f"  menu path:    {d.get('menu_path')}")
    lines.append(f"  recommended:  {d.get('recommended')}")
    lines.append(f"  default:      {d.get('default')}")
    axes = ", ".join(d.get("workload_axis") or [])
    lines.append(f"  workload axes: {axes}")
    lines.append(f"  can probe:    {d.get('can_probe')}")
    if d.get("probe_command"):
        lines.append(f"  probe cmd:    {d['probe_command']}")
        lines.append(f"  probe match:  {d.get('probe_match')}")
    if d.get("operator_caveat"):
        lines.append(f"  caveat:       {d['operator_caveat']}")
    lines.append("")
    lines.append(f"  rationale: {d.get('rationale')}")
    return "\n".join(lines) + "\n"


# ── Main ────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="bios-directives.py")
    sub = p.add_subparsers(dest="verb", required=True)

    pl = sub.add_parser("list")
    pl.add_argument("--axis")
    pl.add_argument("--config", type=Path)
    fl = pl.add_mutually_exclusive_group()
    fl.add_argument("--json", dest="fmt", action="store_const", const="json")
    fl.add_argument("--human", dest="fmt", action="store_const", const="human")
    pl.set_defaults(fmt="json")

    ps = sub.add_parser("show")
    ps.add_argument("setting")
    ps.add_argument("--config", type=Path)
    fs = ps.add_mutually_exclusive_group()
    fs.add_argument("--json", dest="fmt", action="store_const", const="json")
    fs.add_argument("--human", dest="fmt", action="store_const", const="human")
    ps.set_defaults(fmt="json")

    pc = sub.add_parser("check")
    pc.add_argument("--config", type=Path)
    fc = pc.add_mutually_exclusive_group()
    fc.add_argument("--json", dest="fmt", action="store_const", const="json")
    fc.add_argument("--human", dest="fmt", action="store_const", const="human")
    pc.set_defaults(fmt="json")

    args = p.parse_args(argv)
    catalog, meta = load_directives(args.config)

    if args.verb == "list":
        entries = filter_axis(catalog, args.axis)
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "board": "ASUS ProArt X870E-CREATOR WIFI",
                "axis_filter": args.axis,
                "total_count": len(catalog),
                "filtered_count": len(entries),
                "directives": entries,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_list_human(entries, meta), end="")
        return 0

    if args.verb == "show":
        d = resolve_setting(catalog, args.setting)
        if d is None:
            print(json.dumps({
                "error": f"unknown setting: {args.setting}",
                "known": [x.get("name") for x in catalog if isinstance(x, dict)],
                "round": ROUND,
            }, indent=2), file=sys.stderr)
            return 1
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "directive": d,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_show_human(d), end="")
        return 0

    if args.verb == "check":
        results = []
        any_mismatch = False
        for d in catalog:
            if not isinstance(d, dict):
                continue
            probe = run_probe(d)
            row = {
                "name": d.get("name"),
                "recommended": d.get("recommended"),
                "can_probe": d.get("can_probe"),
                "probe_result": probe,
            }
            results.append(row)
            if probe.get("match") is False:
                any_mismatch = True
        rc = 1 if any_mismatch else 0
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "board": "ASUS ProArt X870E-CREATOR WIFI",
                "any_mismatch": any_mismatch,
                "results": results,
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R299 BIOS directive check (E1.M24) ──")
            for r in results:
                p = r["probe_result"]
                if not r["can_probe"]:
                    mark = "--"
                elif p.get("match"):
                    mark = "OK"
                elif p.get("match") is False:
                    mark = "!!"
                else:
                    mark = "??"
                print(f"  [{mark}] {r['name']}: {p.get('detail', '')}")
            print()
            print(f"  any_mismatch: {any_mismatch}")
        return rc

    return 2


if __name__ == "__main__":
    sys.exit(main())
