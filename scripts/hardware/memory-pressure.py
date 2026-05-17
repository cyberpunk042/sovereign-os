#!/usr/bin/env python3
"""scripts/hardware/memory-pressure.py — R269 (E1.M15).

Operator-named (verbatim, 2026-05-17 mandate): "system usage,
partitions and global and such. insights" + AI workloads ("fine-tune,
parameters, build, run, use and train") — fine-tunes + large
inference batches OOM hard. R269 surfaces memory pressure ahead of
the OOM killer.

Three signal sources (read-only):
  /proc/meminfo           classic free/available/swap
  /proc/pressure/memory   PSI (kernel 4.20+) — % of time stalled
                          on memory allocation (some/full × 10s/60s/300s)
  /sys/fs/cgroup/...      cgroup v2 memory.pressure + memory.events
                          (oom + oom_kill counters)
  journalctl              recent OOM-killer events (last N)

Posture verdict:
  ok           available_mb high, swap low, PSI low
  attention    available_mb < 15% OR swap > 50% OR PSI some.avg60 > 20%
  critical     available_mb < 5%  OR PSI full.avg10 > 5%  OR recent OOM kill
  unavailable  /proc/pressure missing (pre-4.20 kernel)

CLI:
  memory-pressure.py status [--json]    full snapshot
  memory-pressure.py psi [--json]       PSI counters only
  memory-pressure.py oom-events [--lines N] [--json]
                                        journalctl OOM-killer scan

Exit codes:
  0  posture ok / unavailable (informational)
  1  posture attention OR critical
  2  usage error
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def parse_meminfo() -> dict[str, int]:
    """/proc/meminfo → {key: value_kb}."""
    out: dict[str, int] = {}
    p = Path("/proc/meminfo")
    if not p.exists():
        return out
    try:
        for line in p.read_text().splitlines():
            m = re.match(r"^(\w+):\s+(\d+)(?:\s+kB)?$", line)
            if m:
                out[m.group(1)] = int(m.group(2))
    except OSError:
        pass
    return out


def parse_psi(path: str) -> dict[str, dict[str, float]] | None:
    """Parse /proc/pressure/<resource>. Returns {some: {avg10, avg60,
    avg300, total}, full: {...}} or None when PSI unavailable."""
    p = Path(path)
    if not p.exists():
        return None
    out: dict[str, dict[str, float]] = {}
    try:
        for line in p.read_text().splitlines():
            # Format: 'some avg10=0.00 avg60=0.00 avg300=0.00 total=0'
            parts = line.split()
            if not parts or parts[0] not in {"some", "full"}:
                continue
            kind = parts[0]
            out[kind] = {}
            for tok in parts[1:]:
                if "=" in tok:
                    k, _, v = tok.partition("=")
                    try:
                        out[kind][k] = float(v)
                    except ValueError:
                        pass
    except OSError:
        return None
    return out or None


def parse_cgroup_v2_memory() -> dict[str, Any]:
    """cgroup v2 root memory.events + memory.pressure when present."""
    out: dict[str, Any] = {}
    root = Path("/sys/fs/cgroup")
    if not (root / "cgroup.controllers").exists():
        return out
    events = root / "memory.events"
    if events.exists():
        try:
            ev: dict[str, int] = {}
            for line in events.read_text().splitlines():
                parts = line.split()
                if len(parts) == 2 and parts[1].isdigit():
                    ev[parts[0]] = int(parts[1])
            out["events"] = ev
        except OSError:
            pass
    pressure = root / "memory.pressure"
    if pressure.exists():
        psi = parse_psi(str(pressure))
        if psi:
            out["pressure"] = psi
    return out


def scan_recent_oom_events(lines: int = 200) -> dict[str, Any]:
    """journalctl scan for OOM-killer activity in the recent past."""
    if not shutil.which("journalctl"):
        return {"available": False, "events": []}
    try:
        r = subprocess.run(
            ["journalctl", "-k", "--since", "1 day ago", "-n", str(lines),
             "--no-pager", "-o", "short-iso"],
            capture_output=True, text=True, timeout=8, check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return {"available": False, "events": [], "error": "journalctl failed"}
    if r.returncode != 0:
        return {"available": True, "events": [], "error": (r.stderr or "")[:200]}
    events: list[dict[str, Any]] = []
    # Match kernel OOM-killer lines.
    for line in r.stdout.splitlines():
        if "out of memory" in line.lower() or "killed process" in line.lower() or "oom-kill" in line.lower():
            events.append({"line": line})
    return {"available": True, "scanned_lines": len(r.stdout.splitlines()),
            "events": events, "event_count": len(events)}


def derive_verdict(mi: dict[str, int], mem_psi: dict | None,
                   cgroup: dict[str, Any], oom: dict[str, Any]) -> dict[str, Any]:
    advisories: list[str] = []
    total_mb = mi.get("MemTotal", 0) / 1024
    available_mb = mi.get("MemAvailable", 0) / 1024
    swap_total_mb = mi.get("SwapTotal", 0) / 1024
    swap_free_mb = mi.get("SwapFree", 0) / 1024
    swap_used_mb = swap_total_mb - swap_free_mb if swap_total_mb else 0
    available_pct = (available_mb / total_mb * 100) if total_mb else 0
    swap_used_pct = (swap_used_mb / swap_total_mb * 100) if swap_total_mb else 0

    full_avg10 = (mem_psi or {}).get("full", {}).get("avg10") if mem_psi else None
    some_avg60 = (mem_psi or {}).get("some", {}).get("avg60") if mem_psi else None

    cgroup_oom_kill = (cgroup.get("events") or {}).get("oom_kill", 0)
    recent_oom_kernel = oom.get("event_count", 0)

    verdict = "ok"

    if available_pct > 0 and available_pct < 5:
        verdict = "critical"
        advisories.append(
            f"MemAvailable {available_pct:.1f}% (<5%) — host is one allocation "
            "away from invoking the OOM killer. Stop inference / fine-tune NOW."
        )
    elif available_pct > 0 and available_pct < 15:
        if verdict == "ok":
            verdict = "attention"
        advisories.append(
            f"MemAvailable {available_pct:.1f}% (<15%) — risk of OOM kill. "
            "Cap batch size OR reduce GPU model count."
        )

    if full_avg10 is not None and full_avg10 > 5.0:
        verdict = "critical"
        advisories.append(
            f"PSI full.avg10 = {full_avg10}% — kernel reports ALL tasks "
            "stalling on memory >5% of the last 10s. Imminent OOM."
        )
    elif some_avg60 is not None and some_avg60 > 20.0:
        if verdict == "ok":
            verdict = "attention"
        advisories.append(
            f"PSI some.avg60 = {some_avg60}% — at least one task stalling "
            "on memory >20% of last minute. Memory pressure rising."
        )

    if swap_total_mb > 0 and swap_used_pct > 50:
        if verdict == "ok":
            verdict = "attention"
        advisories.append(
            f"swap {swap_used_pct:.0f}% used ({swap_used_mb:.0f}/{swap_total_mb:.0f} MB) "
            "— working set exceeds RAM. Inference latency will spike on swap-in."
        )

    if cgroup_oom_kill > 0:
        verdict = "critical"
        advisories.append(
            f"cgroup memory.events.oom_kill = {cgroup_oom_kill} — kernel HAS "
            "killed tasks for memory. Inspect with `dmesg -T | tail -200`."
        )
    if recent_oom_kernel > 0:
        verdict = "critical"
        advisories.append(
            f"{recent_oom_kernel} OOM-killer event(s) in journalctl (last 24h). "
            "Use `journalctl -k --since '1 day ago' | grep -i 'out of memory'`."
        )

    return {
        "verdict": verdict,
        "advisories": advisories,
        "metrics": {
            "mem_total_mb": round(total_mb, 1),
            "mem_available_mb": round(available_mb, 1),
            "mem_available_pct": round(available_pct, 2),
            "swap_total_mb": round(swap_total_mb, 1),
            "swap_used_mb": round(swap_used_mb, 1),
            "swap_used_pct": round(swap_used_pct, 2),
            "psi_some_avg60_pct": some_avg60,
            "psi_full_avg10_pct": full_avg10,
            "cgroup_oom_kill_count": cgroup_oom_kill,
            "journal_oom_event_count": recent_oom_kernel,
        },
    }


def cmd_status(args: argparse.Namespace) -> int:
    mi = parse_meminfo()
    mem_psi = parse_psi("/proc/pressure/memory")
    cgroup = parse_cgroup_v2_memory()
    oom = scan_recent_oom_events(lines=200)
    result = derive_verdict(mi, mem_psi, cgroup, oom)
    if mem_psi is None and not mi:
        result["verdict"] = "unavailable"
        result["advisories"].insert(0, "/proc/meminfo + /proc/pressure unavailable — "
                                        "host kernel lacks PSI (pre-4.20) OR /proc not mounted.")
    out = {
        "round": "R269",
        "vector": "E1.M15 (memory-pressure)",
        "psi_available": mem_psi is not None,
        "cgroup_v2_present": bool(cgroup),
        "oom_journal_scan": oom,
        **result,
    }
    rc = 1 if result["verdict"] in {"attention", "critical"} else 0
    if args.json:
        print(json.dumps(out, indent=2))
        return rc
    print(f"── R269 sovereign-os memory-pressure status (E1.M15) ──")
    m = result["metrics"]
    print(f"  mem:        {m['mem_available_mb']} / {m['mem_total_mb']} MB available  ({m['mem_available_pct']}%)")
    if m["swap_total_mb"]:
        print(f"  swap:       {m['swap_used_mb']} / {m['swap_total_mb']} MB used  ({m['swap_used_pct']}%)")
    if mem_psi is not None:
        print(f"  PSI some.avg60:  {m['psi_some_avg60_pct']}%")
        print(f"  PSI full.avg10:  {m['psi_full_avg10_pct']}%")
    else:
        print(f"  PSI:        unavailable (kernel < 4.20 OR /proc/pressure missing)")
    if oom.get("event_count"):
        print(f"  journal OOM events (24h): {oom['event_count']}")
    if m["cgroup_oom_kill_count"]:
        print(f"  cgroup oom_kill counter:  {m['cgroup_oom_kill_count']}")
    print()
    print(f"  verdict: {result['verdict']}")
    for a in result["advisories"]:
        print(f"    ⚠ {a}")
    return rc


def cmd_psi(args: argparse.Namespace) -> int:
    psi = parse_psi("/proc/pressure/memory")
    out = {
        "round": "R269",
        "vector": "E1.M15 (memory PSI)",
        "available": psi is not None,
        "psi": psi or {},
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"── R269 sovereign-os memory-pressure psi (E1.M15) ──")
    if psi is None:
        print("  /proc/pressure/memory unavailable.")
        return 0
    for kind, vals in psi.items():
        print(f"  {kind:<6} avg10={vals.get('avg10')}  avg60={vals.get('avg60')}  avg300={vals.get('avg300')}  total={vals.get('total')}")
    return 0


def cmd_oom_events(args: argparse.Namespace) -> int:
    res = scan_recent_oom_events(lines=args.lines)
    out = {
        "round": "R269",
        "vector": "E1.M15 (oom-journal-scan)",
        **res,
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 1 if res.get("event_count", 0) > 0 else 0
    print(f"── R269 memory-pressure oom-events (E1.M15) ──")
    if not res.get("available"):
        print("  journalctl unavailable.")
        return 0
    print(f"  events in last 24h: {res.get('event_count', 0)}")
    for e in res.get("events", [])[:20]:
        print(f"    {e['line']}")
    return 1 if res.get("event_count", 0) > 0 else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="memory-pressure.py",
        description="R269 (E1.M15) — memory pressure + OOM watcher.",
    )
    sub = p.add_subparsers(dest="verb", required=True)
    ps = sub.add_parser("status", help="full snapshot + verdict")
    ps.add_argument("--json", action="store_true")
    ps.set_defaults(func=cmd_status)
    pp = sub.add_parser("psi", help="PSI counters only")
    pp.add_argument("--json", action="store_true")
    pp.set_defaults(func=cmd_psi)
    po = sub.add_parser("oom-events", help="journalctl OOM scan")
    po.add_argument("--lines", type=int, default=200)
    po.add_argument("--json", action="store_true")
    po.set_defaults(func=cmd_oom_events)
    return p


def main(argv: list[str]) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
