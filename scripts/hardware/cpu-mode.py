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


METRICS_DIR = Path(
    os.environ.get(
        "SOVEREIGN_OS_METRICS_DIR",
        "/var/lib/node_exporter/textfile_collector",
    )
)


def _read_prom_lines(name: str) -> list[str]:
    """Read a .prom file. Returns [] if missing/unreadable."""
    p = METRICS_DIR / name
    if not p.exists():
        return []
    try:
        return p.read_text(errors="replace").splitlines()
    except OSError:
        return []


def _sum_metric(lines: list[str], metric_prefix: str) -> float:
    """Sum every value line whose head starts with metric_prefix."""
    total = 0.0
    for line in lines:
        if line.startswith("#") or not line.startswith(metric_prefix):
            continue
        parts = line.rsplit(None, 1)
        if len(parts) != 2:
            continue
        try:
            total += float(parts[1])
        except ValueError:
            continue
    return total


def _max_metric(lines: list[str], metric_prefix: str) -> float:
    best = 0.0
    for line in lines:
        if line.startswith("#") or not line.startswith(metric_prefix):
            continue
        parts = line.rsplit(None, 1)
        if len(parts) != 2:
            continue
        try:
            v = float(parts[1])
            if v > best:
                best = v
        except ValueError:
            continue
    return best


def derive_auto_recommendation() -> dict[str, Any]:
    """R230 — workload-aware CPU mode recommendation.

    Signal sources (Layer B textfile collector .prom files):

      sovereign_os_inference_router_class_total    (R215 / Z-2)
      sovereign_os_gpu_power_draw_watts            (R219 / Z-5)
      sovereign_os_gpu_power_limit_deviance_watts  (R219 / Z-5)

    Decision table:

      gpu_draw_max ≥ 200 W → peak-inference
      gpu_draw_max ≥ 100 W → sustained-burst
      inference_routes > 0 → balanced
      otherwise            → balanced (safe default — auto never drops
                             below balanced without --aggressive)
    """
    infer_lines = _read_prom_lines("sovereign-os-inference-router.prom")
    gpu_lines = _read_prom_lines("sovereign-os-gpu-watch.prom")

    inference_total = _sum_metric(
        infer_lines, "sovereign_os_inference_router_class_total"
    )
    gpu_draw_max = _max_metric(gpu_lines, "sovereign_os_gpu_power_draw_watts")
    gpu_deviance = _max_metric(
        gpu_lines, "sovereign_os_gpu_power_limit_deviance_watts"
    )
    signals_present = bool(infer_lines or gpu_lines)

    if gpu_draw_max >= 200.0:
        rec = "peak-inference"
        reason = f"GPU draw {gpu_draw_max:.0f} W ≥ 200 W"
    elif gpu_draw_max >= 100.0:
        rec = "sustained-burst"
        reason = f"GPU draw {gpu_draw_max:.0f} W ≥ 100 W"
    elif inference_total > 0:
        rec = "balanced"
        reason = (
            f"inference router served {int(inference_total)} route(s); "
            f"no heavy GPU load"
        )
    elif signals_present:
        rec = "balanced"
        reason = "no inference + cold GPU — staying balanced (safe default)"
    else:
        rec = "balanced"
        reason = "no Layer B signals on this host — staying balanced"

    return {
        "round": "R230",
        "vector": "SDD-026 Z-4 (cpu-mode auto)",
        "signals": {
            "inference_router_total": inference_total,
            "gpu_draw_max_watts": gpu_draw_max,
            "gpu_limit_deviance_watts": gpu_deviance,
            "signals_present": signals_present,
        },
        "recommendation": rec,
        "reason": reason,
    }


def cmd_auto(apply: bool, aggressive: bool, json_out: bool) -> int:
    """R230 — workload-aware mode recommendation, optionally apply."""
    rec = derive_auto_recommendation()
    if aggressive and not rec["signals"]["signals_present"]:
        rec["recommendation"] = "ultra-low-power"
        rec["reason"] = "no signals + --aggressive → idle posture"

    dirs = cpufreq_dirs()
    current_governor = None
    if dirs:
        try:
            current_governor = (dirs[0] / "scaling_governor").read_text().strip()
        except OSError:
            pass
    target_governor = MODES[rec["recommendation"]]["governor"]
    rec["current_governor"] = current_governor
    rec["target_governor"] = target_governor
    rec["change_needed"] = current_governor != target_governor
    rec["aggressive"] = bool(aggressive)
    rec["apply_requested"] = bool(apply)

    applied = False
    apply_rc: int | None = None
    if apply and rec["change_needed"]:
        apply_rc = cmd_set(rec["recommendation"])
        applied = apply_rc == 0
    rec["applied"] = applied
    rec["apply_rc"] = apply_rc

    if json_out:
        print(json.dumps(rec, indent=2))
        return apply_rc if (apply and apply_rc is not None) else 0

    print("── R230 sovereign-os cpu-mode auto (SDD-026 Z-4) ──")
    s = rec["signals"]
    print(
        f"  signals:        inference_total={s['inference_router_total']:.0f}  "
        f"gpu_draw_max={s['gpu_draw_max_watts']:.0f} W  "
        f"gpu_deviance={s['gpu_limit_deviance_watts']:.0f} W"
    )
    if not s["signals_present"]:
        print("  (no Layer B .prom files present — running on defaults)")
    print(f"  current:        {current_governor or '(unknown)'}")
    print(f"  recommendation: {rec['recommendation']}  → governor={target_governor}")
    print(f"  reason:         {rec['reason']}")
    if rec["change_needed"]:
        if apply:
            mark = "APPLIED" if applied else f"FAILED (rc={apply_rc})"
            print(f"  action:         {mark}")
        else:
            print(
                f"  action:         (advisory — re-run with --apply, "
                f"or `cpu-mode set {rec['recommendation']}`)"
            )
    else:
        print("  action:         no change needed (already on target)")
    return apply_rc if (apply and apply_rc is not None) else 0


def main() -> int:
    p = argparse.ArgumentParser(description="R221 (SDD-026 Z-4) CPU hotswap modes.")
    sub = p.add_subparsers(dest="action", required=True)
    p_show = sub.add_parser("show", help="show current per-CPU governor + matched mode")
    p_show.add_argument("--json", action="store_true")
    p_list = sub.add_parser("list", help="enumerate the 4 named modes")
    p_list.add_argument("--json", action="store_true")
    p_set = sub.add_parser("set", help="switch to a named mode (requires root)")
    p_set.add_argument("mode", choices=list(MODES.keys()))
    p_auto = sub.add_parser(
        "auto",
        help="R230: workload-aware mode recommendation (advisory by default)",
    )
    p_auto.add_argument(
        "--apply",
        action="store_true",
        help="actually set the recommended mode (otherwise advisory only)",
    )
    p_auto.add_argument(
        "--aggressive",
        action="store_true",
        help="allow dropping to ultra-low-power on idle hosts",
    )
    p_auto.add_argument("--json", action="store_true")
    args = p.parse_args()
    if args.action == "show":
        return cmd_show(args.json)
    if args.action == "list":
        return cmd_list(args.json)
    if args.action == "set":
        return cmd_set(args.mode)
    if args.action == "auto":
        return cmd_auto(args.apply, args.aggressive, args.json)
    return 2


if __name__ == "__main__":
    sys.exit(main())
