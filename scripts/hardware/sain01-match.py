#!/usr/bin/env python3
"""sovereign-os mirror of selfdef SDD-017 Sain01Match (R166).

Same 5-dimensional fitness verdict that selfdef computes, run from the
sovereign-os side so operators can ask "is THIS box the SAIN-01 spec?"
from either CLI. The two implementations stay in agreement by
reading the same /proc/* + /sys/* sources and applying the same logic.

Dimensions (all from master spec § 1 + § 22):
  - cpu_avx512_vnni      (required: master spec § 22 check 01)
  - cpu_avx512_bf16      (bonus, but required for FullMatch when present)
  - memory_at_least_256gb
  - gpu_count_at_least_2  (RTX PRO 6000 primary + RTX 5090 secondary + RTX 4090 OcuLink eGPU = 3 cards per SDD-993; the >=2 predicate still holds)
  - pcie_dual_x8_present  (master spec § 1.2 — best-effort via lspci)
  - motherboard_proart_x870e (bonus when DMI readable)

Verdict:
  FullMatch    — every accounted dimension hits
  PartialMatch — some hit, some miss
  NoMatch      — nothing hits

CLI:
  sain01-match.py                # human-readable
  sain01-match.py --json         # machine-readable
  sain01-match.py --verdict-only # just FullMatch/PartialMatch/NoMatch

Exit codes:
  0  FullMatch or PartialMatch (informational)
  2  NoMatch (script / CI can gate on this)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

BYTES_256_GB = 256 * 1024 * 1024 * 1024
HOST_FENCED_SYSCALLS = ("sys_execve", "sys_execveat", "tcp_connect", "tcp_sendmsg")


def read_cpu_features(cpuinfo_path: Path) -> tuple[str, str, int, set[str]]:
    """Return (vendor, model_name, logical_threads, features_set)."""
    if not cpuinfo_path.exists():
        return ("", "", 0, set())
    vendor = ""
    model_name = ""
    processor_count = 0
    features: set[str] = set()
    try:
        body = cpuinfo_path.read_text(errors="ignore")
    except OSError:
        return (vendor, model_name, processor_count, features)
    for line in body.splitlines():
        if line.startswith("processor"):
            if ":" in line:
                processor_count += 1
        elif ":" in line:
            k, _, v = line.partition(":")
            k = k.strip()
            v = v.strip()
            if k == "vendor_id":
                vendor = v
            elif k == "model name":
                model_name = v
            elif k == "flags":
                for f in v.split():
                    features.add(f)
    return (vendor, model_name, processor_count, features)


def read_memory_bytes(meminfo_path: Path) -> int:
    if not meminfo_path.exists():
        return 0
    try:
        body = meminfo_path.read_text(errors="ignore")
    except OSError:
        return 0
    for line in body.splitlines():
        if line.startswith("MemTotal:"):
            toks = line.split()
            # MemTotal:  268435456 kB
            if len(toks) >= 2 and toks[1].isdigit():
                return int(toks[1]) * 1024
    return 0


def read_gpu_count(dev_dir: Path) -> tuple[int, list[str]]:
    """Count /dev/nvidia<N> nodes (skip nvidiactl/nvidia-uvm)."""
    if not dev_dir.exists():
        return (0, [])
    nodes: list[str] = []
    try:
        for entry in dev_dir.iterdir():
            name = entry.name
            if not name.startswith("nvidia"):
                continue
            rest = name[len("nvidia"):]
            if not rest or not rest.isdigit():
                continue
            nodes.append(str(entry))
    except OSError:
        return (0, [])
    nodes.sort()
    return (len(nodes), nodes)


def read_motherboard(dmi_dir: Path) -> tuple[str | None, str | None]:
    if not dmi_dir.exists():
        return (None, None)

    def _read(name: str) -> str | None:
        p = dmi_dir / name
        try:
            v = p.read_text(errors="ignore").strip()
            return v or None
        except OSError:
            return None

    return (_read("board_vendor"), _read("board_name"))


def motherboard_is_proart_x870e(vendor: str | None, product: str | None) -> bool:
    v = (vendor or "").lower()
    p = (product or "").lower()
    return "asus" in v and "proart" in p and "x870e" in p


def read_pcie_dual_x8() -> tuple[int, bool]:
    """Best-effort PCIe walk via `lspci -vv`. Counts slots reporting
    `LnkSta: Speed ... Width x8`. Returns (count, is_dual_x8).
    Returns (0, False) when lspci is unavailable or returns nothing
    (operator should run sovereign-osctl friction-audit for the
    authoritative read on real hardware)."""
    try:
        r = subprocess.run(
            ["lspci", "-vv"], capture_output=True, text=True, timeout=5, check=False
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return (0, False)
    if r.returncode != 0 or not r.stdout:
        return (0, False)
    x8_count = 0
    for line in r.stdout.splitlines():
        line = line.strip()
        if line.startswith("LnkSta:"):
            # Look for "Width x8" + Gen 4 (16GT/s) or Gen 5 (32GT/s)
            if "Width x8" in line and re.search(r"Speed (16|32)[.0-9]*GT/s", line):
                x8_count += 1
    return (x8_count, x8_count >= 2)


def render_match(snapshot: dict) -> dict:
    cpu = snapshot["cpu"]
    avx512_vnni = "avx512_vnni" in cpu["features"]
    avx512_bf16 = "avx512_bf16" in cpu["features"]
    mem_ok = snapshot["memory"]["total_bytes"] >= BYTES_256_GB
    gpu_ok = snapshot["gpus"]["count"] >= 2
    pcie_ok = snapshot["pcie"]["dual_x8"]
    mb = snapshot["motherboard"]
    if mb["vendor"] is None and mb["product_name"] is None:
        mb_match: bool | None = None
    else:
        mb_match = motherboard_is_proart_x870e(mb["vendor"], mb["product_name"])
    hits = 0
    total = 4
    for v in (avx512_vnni, mem_ok, gpu_ok, pcie_ok):
        if v:
            hits += 1
    if avx512_bf16:
        hits += 1
        total += 1
    if mb_match is True:
        hits += 1
        total += 1
    elif mb_match is False:
        total += 1
    if hits == total:
        overall = "FullMatch"
    elif hits == 0:
        overall = "NoMatch"
    else:
        overall = "PartialMatch"
    return {
        "overall": overall,
        "cpu_avx512_vnni": avx512_vnni,
        "cpu_avx512_bf16": avx512_bf16,
        "memory_at_least_256gb": mem_ok,
        "gpu_count_at_least_2": gpu_ok,
        "pcie_dual_x8_present": pcie_ok,
        "motherboard_proart_x870e": mb_match,
    }


def probe() -> dict:
    vendor, model_name, threads, features = read_cpu_features(Path("/proc/cpuinfo"))
    mem_bytes = read_memory_bytes(Path("/proc/meminfo"))
    gpu_count, gpu_nodes = read_gpu_count(Path("/dev"))
    mb_vendor, mb_product = read_motherboard(Path("/sys/class/dmi/id"))
    pcie_x8, pcie_dual = read_pcie_dual_x8()
    return {
        "cpu": {
            "vendor": vendor,
            "model_name": model_name,
            "logical_threads": threads,
            "features": sorted(features),
            "avx512_present": any(f.startswith("avx512") for f in features),
            "avx512_vnni": "avx512_vnni" in features,
            "avx512_bf16": "avx512_bf16" in features,
        },
        "memory": {"total_bytes": mem_bytes},
        "gpus": {"count": gpu_count, "nodes": gpu_nodes},
        "motherboard": {"vendor": mb_vendor, "product_name": mb_product},
        "pcie": {
            "gen4_or_higher_x8_slot_count": pcie_x8,
            "dual_x8": pcie_dual,
        },
        "probed_at_unix": int(time.time()),
    }


def render_human(snap: dict, m: dict) -> str:
    out = ["# sovereign-osctl hardware sain01-match (selfdef SDD-017 mirror)", ""]
    cpu = snap["cpu"]
    out.append("## CPU")
    out.append(f"  vendor:          {cpu['vendor'] or '(unknown)'}")
    out.append(f"  model:           {cpu['model_name'] or '(unknown)'}")
    out.append(f"  logical_threads: {cpu['logical_threads']}")
    out.append(f"  avx512_vnni:     {cpu['avx512_vnni']}")
    out.append(f"  avx512_bf16:     {cpu['avx512_bf16']}")
    out.append("")
    out.append("## Memory")
    mem = snap["memory"]["total_bytes"]
    gib = mem / (1024**3)
    out.append(f"  total_bytes:     {mem} ({gib:.1f} GiB)")
    out.append("")
    out.append("## GPUs")
    if snap["gpus"]["count"] == 0:
        out.append("  (none detected)")
    else:
        for n in snap["gpus"]["nodes"]:
            out.append(f"  {n}")
    out.append("")
    out.append("## Motherboard")
    mb = snap["motherboard"]
    if mb["vendor"] is None and mb["product_name"] is None:
        out.append("  (DMI unreadable)")
    else:
        out.append(f"  vendor:          {mb['vendor'] or '(unknown)'}")
        out.append(f"  product_name:    {mb['product_name'] or '(unknown)'}")
    out.append("")
    out.append("## PCIe")
    out.append(f"  x8_slot_count:   {snap['pcie']['gen4_or_higher_x8_slot_count']}")
    out.append(f"  dual_x8_present: {snap['pcie']['dual_x8']}")
    out.append("")
    out.append("## Sain01Match verdict")
    out.append(f"  overall:                  {m['overall']}")
    out.append(f"  cpu_avx512_vnni:          {m['cpu_avx512_vnni']}")
    out.append(f"  cpu_avx512_bf16:          {m['cpu_avx512_bf16']}")
    out.append(f"  memory_at_least_256gb:    {m['memory_at_least_256gb']}")
    out.append(f"  gpu_count_at_least_2:     {m['gpu_count_at_least_2']}")
    out.append(f"  pcie_dual_x8_present:     {m['pcie_dual_x8_present']}")
    if m["motherboard_proart_x870e"] is None:
        out.append("  motherboard_proart_x870e: (DMI unreadable)")
    else:
        out.append(f"  motherboard_proart_x870e: {m['motherboard_proart_x870e']}")
    return "\n".join(out) + "\n"


def verdict_exit(overall: str) -> int:
    return 0 if overall in ("FullMatch", "PartialMatch") else 2


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SAIN-01 hardware match (selfdef SDD-017 mirror)"
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "--verdict-only",
        action="store_true",
        help="print the verdict label and exit",
    )
    args = parser.parse_args()

    snap = probe()
    m = render_match(snap)

    if args.verdict_only:
        print(m["overall"])
    elif args.json:
        print(json.dumps({"snapshot": snap, "sain01_match": m}, indent=2))
    else:
        sys.stdout.write(render_human(snap, m))
    return verdict_exit(m["overall"])


if __name__ == "__main__":
    sys.exit(main())
