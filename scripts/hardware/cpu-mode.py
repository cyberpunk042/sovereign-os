#!/usr/bin/env python3
"""scripts/hardware/cpu-mode.py — R221 (SDD-026 Z-4) CPU hotswap modes.

Operator-named: "Hotswap from one CPU mode to another to another
with some auto option(s)".

Four operator-meaningful CPU profiles ("modes"), each pinning the
scaling_governor + optional knobs:

  ultra-low-power   powersave     — minimum draw; background daemons only
  balanced          schedutil     — default; mixed workload, low-latency
  sustained-burst   performance   — multi-hour inference; pegged clocks
  peak-inference    performance   — sustained-burst + idle-state cap
                                    (energy_perf_bias = performance)

Operations:
  show       — current governor per CPU + which mode (if any) matches
  list       — enumerate the 4 modes + their effective knob settings
  set <mode> — write /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
               (requires root; non-root invocation prints the actual
                shell command operator should run + exits 2)

Read-mostly philosophy: `show` and `list` NEVER write; only
`set <mode>` writes, and even then it prints a confirmation banner
before the operator sees the new state via `show`.

Exit codes:
  0  operation succeeded
  1  set <mode> partially failed (some cores didn't accept the write)
  2  usage error / cpufreq unavailable / set without root
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

CPUFREQ_GLOB = "/sys/devices/system/cpu/cpu[0-9]*/cpufreq"

MODES: dict[str, dict[str, Any]] = {
    "ultra-low-power": {
        "governor": "powersave",
        "energy_perf_bias": "power",
        "summary": "minimum draw — background daemons + idle agents only",
    },
    "balanced": {
        "governor": "schedutil",
        "energy_perf_bias": "balance_power",
        "summary": "default — mixed workload + low-latency desktop feel",
    },
    "sustained-burst": {
        "governor": "performance",
        "energy_perf_bias": "performance",
        "summary": "multi-hour inference; pegged clocks; full TDP",
    },
    "peak-inference": {
        "governor": "performance",
        "energy_perf_bias": "performance",
        "summary": (
            "sustained-burst + minimum-latency knobs — operator-driven for "
            "synchronous low-batch inference"
        ),
    },
}


def cpufreq_dirs() -> list[Path]:
    base = Path("/sys/devices/system/cpu")
    if not base.exists():
        return []
    out = []
    for entry in sorted(base.iterdir()):
        if not entry.name.startswith("cpu"):
            continue
        rest = entry.name[3:]
        if not rest.isdigit():
            continue
        cpufreq = entry / "cpufreq"
        if cpufreq.is_dir():
            out.append(cpufreq)
    return out


def read_current_governor() -> dict[int, str]:
    out: dict[int, str] = {}
    for d in cpufreq_dirs():
        cpu_idx = int(d.parent.name[3:])
        f = d / "scaling_governor"
        if f.is_file():
            try:
                out[cpu_idx] = f.read_text().strip()
            except OSError:
                out[cpu_idx] = "(unreadable)"
        else:
            out[cpu_idx] = "(missing)"
    return out


def identify_mode(governors: dict[int, str]) -> str | None:
    """Returns the mode name when EVERY policed CPU is in agreement
    with that mode's governor; else None (mixed)."""
    if not governors:
        return None
    govs = set(governors.values())
    if len(govs) != 1:
        return None
    g = next(iter(govs))
    for name, spec in MODES.items():
        if spec["governor"] == g:
            return name
    return None


def cmd_show(json_out: bool) -> int:
    governors = read_current_governor()
    if not governors:
        msg = "(cpufreq subsystem unavailable on this host)"
        if json_out:
            print(json.dumps({"cpus": {}, "matched_mode": None, "note": msg}))
        else:
            print(msg)
        return 0
    mode = identify_mode(governors)
    if json_out:
        print(
            json.dumps(
                {
                    "cpus": {str(k): v for k, v in governors.items()},
                    "matched_mode": mode,
                    "available_modes": list(MODES.keys()),
                },
                indent=2,
            )
        )
        return 0
    print("── R221 sovereign-os cpu-mode (SDD-026 Z-4) ──")
    # Group consecutive CPUs sharing the same governor.
    sorted_items = sorted(governors.items())
    runs: list[tuple[int, int, str]] = []
    start_idx, last_idx, last_gov = (
        sorted_items[0][0],
        sorted_items[0][0],
        sorted_items[0][1],
    )
    for idx, gov in sorted_items[1:]:
        if gov == last_gov and idx == last_idx + 1:
            last_idx = idx
        else:
            runs.append((start_idx, last_idx, last_gov))
            start_idx, last_idx, last_gov = idx, idx, gov
    runs.append((start_idx, last_idx, last_gov))
    for s, e, g in runs:
        rng = f"cpu{s}" if s == e else f"cpu{s}..cpu{e}"
        print(f"  {rng:<14} {g}")
    if mode is None:
        print()
        print("  current mode: MIXED (no single mode owns every CPU)")
    else:
        print()
        print(f"  current mode: {mode}  — {MODES[mode]['summary']}")
    return 0


def cmd_list(json_out: bool) -> int:
    if json_out:
        print(json.dumps({"modes": MODES}, indent=2))
        return 0
    print("── R221 sovereign-os cpu-mode — available modes ──")
    for name, spec in MODES.items():
        print(f"  {name:<18} → governor={spec['governor']}")
        print(f"  {'':<20} energy_perf_bias={spec['energy_perf_bias']}")
        print(f"  {'':<20} {spec['summary']}")
    return 0


def cmd_set(mode: str) -> int:
    if mode not in MODES:
        print(f"ERROR unknown mode {mode!r}; run `cpu-mode list`", file=sys.stderr)
        return 2
    spec = MODES[mode]
    target_governor = spec["governor"]
    dirs = cpufreq_dirs()
    if not dirs:
        print("ERROR cpufreq subsystem unavailable on this host", file=sys.stderr)
        return 2
    if os.geteuid() != 0:
        # Print the actionable command instead of attempting + failing.
        cmd = (
            f"for f in /sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_governor; "
            f"do echo {target_governor} | sudo tee \"$f\" >/dev/null; done"
        )
        print(
            f"# Not running as root — to set mode {mode!r} run:\n  {cmd}",
            file=sys.stderr,
        )
        return 2
    failures: list[tuple[Path, str]] = []
    for d in dirs:
        f = d / "scaling_governor"
        try:
            f.write_text(target_governor)
        except OSError as e:
            failures.append((f, str(e)))
    if failures:
        for f, e in failures:
            print(f"ERROR write {f}: {e}", file=sys.stderr)
        return 1
    print(
        f"# R221: set mode {mode!r} ({target_governor}) on "
        f"{len(dirs)} CPU(s)."
    )
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="R221 (SDD-026 Z-4) CPU hotswap modes.")
    sub = p.add_subparsers(dest="action", required=True)
    p_show = sub.add_parser("show", help="show current per-CPU governor + matched mode")
    p_show.add_argument("--json", action="store_true")
    p_list = sub.add_parser("list", help="enumerate the 4 named modes")
    p_list.add_argument("--json", action="store_true")
    p_set = sub.add_parser("set", help="switch to a named mode (requires root)")
    p_set.add_argument("mode", choices=list(MODES.keys()))
    args = p.parse_args()
    if args.action == "show":
        return cmd_show(args.json)
    if args.action == "list":
        return cmd_list(args.json)
    if args.action == "set":
        return cmd_set(args.mode)
    return 2


if __name__ == "__main__":
    sys.exit(main())
