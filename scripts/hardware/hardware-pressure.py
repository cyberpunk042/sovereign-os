#!/usr/bin/env python3
"""scripts/hardware/hardware-pressure.py — unified hardware-pressure core
(M060 D-09 / R10102-R10105).

Aggregates EVERY live hardware-pressure signal the operator's AI
workstation exposes into one snapshot, the data model behind the D-09
cockpit dashboard:

  - Linux PSI (M045)         /proc/pressure/{cpu,memory,io} — % of time
                             stalled (some/full × avg10/avg60/avg300)
  - Dual-CCD topology (M070) per-CCD core set + L3-miss + Infinity
                             Fabric latency (Zen 5 9950X: CCD0 cores 0-7,
                             CCD1 cores 8-15)
  - GPU (Blackwell + 3090)   util / VRAM / temp / power via nvidia-smi
                             (+ KV-cache + VFIO-sandbox status when the
                             inference layer publishes them)
  - ZFS (M068)               pool IOPS + read/write latency + per-dataset
                             sync mode via zpool/zfs
  - Scheduler backpressure   (M058 R09823-R09825) per-rule state

Sovereignty: stdlib-only, zero added deps. Every probe degrades
gracefully — a missing kernel interface / absent tool / no GPU yields
`null` (rendered as `—` in the dashboard), NEVER a crash. This is the
`core` surface of the §1g 8-surface ladder for the hardware-pressure
module; `hardware-pressure-api.py` serves it, `sovereign-osctl
hardware-pressure` drives it ad-hoc, the D-09 webapp renders it.

  hardware-pressure.py status [--json]   full pressure snapshot
  hardware-pressure.py psi    [--json]   PSI counters only
  hardware-pressure.py zfs    [--json]   ZFS datasets + pool latency only
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

SCHEMA_VERSION = "1.0.0"

# CCD topology for the operator-named Zen 5 9950X (M070). Override via env
# for other silicon (comma-separated core ranges per CCD).
CCD_CORE_MAP_DEFAULT = "0-7,8-15"


def _run(cmd: list[str], timeout: float = 4.0) -> str | None:
    """Best-effort subprocess capture — None on any failure/absence."""
    if shutil.which(cmd[0]) is None:
        return None
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return r.stdout


# ---------------------------------------------------------------- PSI ------

def parse_psi(path: str) -> dict[str, dict[str, float]] | None:
    """Parse /proc/pressure/<resource>. Returns {some:{avg10,avg60,avg300,
    total}, full:{...}} or None when PSI is unavailable (pre-4.20 kernel /
    PSI not compiled in). Mirrors scripts/hardware/memory-pressure.py."""
    p = Path(path)
    if not p.exists():
        return None
    out: dict[str, dict[str, float]] = {}
    try:
        for line in p.read_text().splitlines():
            # 'some avg10=0.00 avg60=0.00 avg300=0.00 total=0'
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


def _psi_flat(resource: str) -> dict[str, Any]:
    """Flatten /proc/pressure/<resource> to the dashboard's field names
    (some_10s/some_60s/some_300s/full_10s/full_60s/full_300s). Absent →
    all-null + available:false."""
    raw = parse_psi(f"/proc/pressure/{resource}")
    if raw is None:
        return {
            "available": False,
            "some_10s": None, "some_60s": None, "some_300s": None,
            "full_10s": None, "full_60s": None, "full_300s": None,
        }
    some = raw.get("some", {})
    full = raw.get("full", {})
    return {
        "available": True,
        "some_10s": some.get("avg10"),
        "some_60s": some.get("avg60"),
        "some_300s": some.get("avg300"),
        "full_10s": full.get("avg10"),
        "full_60s": full.get("avg60"),
        "full_300s": full.get("avg300"),
    }


def collect_psi() -> dict[str, Any]:
    return {r: _psi_flat(r) for r in ("cpu", "memory", "io")}


# ---------------------------------------------------------------- CCD ------

def _parse_core_ranges(spec: str) -> list[list[int]]:
    ccds: list[list[int]] = []
    for grp in spec.split(","):
        grp = grp.strip()
        if not grp:
            continue
        if "-" in grp:
            a, _, b = grp.partition("-")
            try:
                ccds.append(list(range(int(a), int(b) + 1)))
            except ValueError:
                continue
        else:
            try:
                ccds.append([int(grp)])
            except ValueError:
                continue
    return ccds


def _cpu_busy_pct(core: int) -> float | None:
    """Per-core busy% from two /proc/stat samples (100ms apart)."""
    def snap() -> tuple[int, int] | None:
        try:
            for line in Path("/proc/stat").read_text().splitlines():
                if line.startswith(f"cpu{core} "):
                    f = [int(x) for x in line.split()[1:]]
                    idle = f[3] + (f[4] if len(f) > 4 else 0)
                    return sum(f), idle
        except (OSError, ValueError):
            return None
        return None

    import time
    a = snap()
    if a is None:
        return None
    time.sleep(0.1)
    b = snap()
    if b is None:
        return None
    dt, di = b[0] - a[0], b[1] - a[1]
    if dt <= 0:
        return None
    return round(100.0 * (dt - di) / dt, 1)


def collect_ccd() -> dict[str, Any]:
    """Per-CCD core utilisation. L3-miss + Infinity-Fabric latency require
    perf/uncore counters (not always permitted in a container) — null when
    unreadable, never fabricated."""
    spec = os.environ.get("SOVEREIGN_OS_CCD_CORE_MAP", CCD_CORE_MAP_DEFAULT)
    out: dict[str, Any] = {}
    for idx, cores in enumerate(_parse_core_ranges(spec)):
        core_busy = {str(c): _cpu_busy_pct(c) for c in cores}
        entry: dict[str, Any] = {"cores": core_busy, "l3_miss": None}
        if idx == 1:
            # Inter-CCD Infinity Fabric latency (Zen): perf-only, null here.
            entry["infinity_fabric_ns"] = None
        out[str(idx)] = entry
    return out


# ---------------------------------------------------------------- GPU ------

def collect_gpu() -> dict[str, Any]:
    """Per-GPU util/VRAM/temp/power via nvidia-smi CSV. KV-cache% and
    VFIO-sandbox status are published by the inference layer (M058) — left
    null here until that wiring lands. Absent nvidia-smi → empty dict."""
    out = _run([
        "nvidia-smi",
        "--query-gpu=index,utilization.gpu,memory.used,temperature.gpu,power.draw",
        "--format=csv,noheader,nounits",
    ])
    if out is None:
        return {}
    gpus: dict[str, Any] = {}
    for line in out.strip().splitlines():
        cells = [c.strip() for c in line.split(",")]
        if len(cells) < 5:
            continue

        def num(v: str) -> float | None:
            try:
                return float(v)
            except ValueError:
                return None

        idx = cells[0]
        mem_mib = num(cells[2])
        gpus[idx] = {
            "util_pct": num(cells[1]),
            "vram_used_gb": round(mem_mib / 1024, 1) if mem_mib is not None else None,
            "temp_c": num(cells[3]),
            "power_w": num(cells[4]),
            "kv_cache_pct": None,
            "sandbox_status": None,
        }
    return gpus


# ---------------------------------------------------------------- ZFS ------

def collect_zfs() -> dict[str, Any]:
    """Pool IOPS + read/write latency (zpool iostat) and per-dataset sync
    mode (zfs list). Absent zpool/zfs → nulls + empty datasets."""
    result: dict[str, Any] = {
        "iops": None, "read_lat_us": None, "write_lat_us": None,
        "datasets": [],
    }
    # Per-dataset sync mode (M068: state-fabric datasets must be sync=always).
    ds_out = _run(["zfs", "list", "-H", "-o", "name,used,avail,mountpoint,sync"])
    if ds_out:
        for line in ds_out.strip().splitlines():
            cols = line.split("\t")
            if len(cols) >= 5:
                result["datasets"].append({
                    "name": cols[0], "used": cols[1], "avail": cols[2],
                    "mountpoint": cols[3], "sync": cols[4],
                })
    # Pool-level latency (zpool iostat -l: avg read/write wait).
    io_out = _run(["zpool", "iostat", "-Hl", "1", "1"])
    if io_out:
        rows = [r for r in io_out.strip().splitlines() if r.strip()]
        if rows:
            c = rows[-1].split("\t")
            # cols: pool alloc free rops wops rbw wbw rwait wwait ...
            if len(c) >= 5:
                def num(v: str) -> float | None:
                    try:
                        return float(v)
                    except ValueError:
                        return None
                r_ops, w_ops = num(c[3]), num(c[4])
                if r_ops is not None and w_ops is not None:
                    result["iops"] = round(r_ops + w_ops)
    return result


# ------------------------------------------------------- backpressure ------

def collect_backpressure() -> dict[str, Any]:
    """Scheduler backpressure rule states (M058 R09823-R09825). Read from
    the runtime's published state file if present; otherwise each rule
    reports `idle` (the safe default — no backpressure asserted)."""
    state_path = Path(os.environ.get(
        "SOVEREIGN_OS_BACKPRESSURE_STATE",
        "/run/sovereign-os/scheduler-backpressure.json",
    ))
    rules = {
        "psi_cpu_high": "idle",
        "psi_mem_high": "idle",
        "psi_io_high": "idle",
        "gpu_vram_high": "idle",
        "zfs_latency_high": "idle",
    }
    if state_path.is_file():
        try:
            published = json.loads(state_path.read_text())
            for k, v in (published.get("rules") or {}).items():
                if k in rules and v in ("idle", "active", "tripped"):
                    rules[k] = v
        except (OSError, json.JSONDecodeError, ValueError):
            pass
    return {"rules": rules, "state_path": str(state_path)}


# ------------------------------------------------------------- snapshot ----

def snapshot() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "psi": collect_psi(),
        "ccd": collect_ccd(),
        "gpu": collect_gpu(),
        "zfs": collect_zfs(),
        "backpressure": collect_backpressure(),
    }


def _print(obj: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(obj, indent=2))
        return
    print(json.dumps(obj, indent=2))  # human view is the same readable JSON


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="unified hardware-pressure core (M060 D-09)")
    sub = p.add_subparsers(dest="cmd")
    for name in ("status", "psi", "zfs"):
        sp = sub.add_parser(name)
        sp.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    cmd = args.cmd or "status"
    as_json = getattr(args, "json", False)
    if cmd == "psi":
        _print(collect_psi(), as_json)
    elif cmd == "zfs":
        _print(collect_zfs(), as_json)
    else:
        _print(snapshot(), as_json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
