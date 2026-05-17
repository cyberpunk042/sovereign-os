#!/usr/bin/env python3
"""scripts/hardware/ram-advisor.py — R279 (E1.M16).

Operator-named (§1a + master-spec §1.1, §3, §19, verbatim raw dump):
  - 256 GB DDR5 (initial 128 GB) baseline
  - ZFS ARC explicitly clamped at 128 GB of the system's 256 GB
  - "High-capacity system context for ZFS ARC and GGUF offloading"

R251 ships DIMM probe. R257 ships XMP/EXPO verdict. R269 ships memory-
pressure / OOM watcher. R279 closes E1.M16: 256-GB-class RAM advisor
that correlates the operator's declared total + ZFS ARC ceiling + GGUF
context budget + measured live consumption into ONE verdict surface.

Live probes (read-only):
  /proc/meminfo                MemTotal / MemAvailable / SwapTotal
  /sys/module/zfs/parameters/  zfs_arc_max (when ZFS module loaded)
  /proc/spl/kstat/zfs/arcstats ZFS ARC live size

Operator-declared facts in /etc/sovereign-os/ram.toml (env override
SOVEREIGN_OS_RAM_CONFIG). Mirrors master spec §19:
  expected_total_gib  = 256
  arc_max_gib         = 128       # clamped per spec
  gguf_context_max_gib = 64       # operator-set headroom for model context

Verdict ladder:
  ok           live total matches operator expected (±2%); ARC within
               configured ceiling; pressure low
  attention    live total < expected (DIMM missing OR firmware mis-
               reports); OR ARC over ceiling; OR GGUF context exceeds
               reservation
  critical     live total far below expected (failed DIMM) OR ARC
               exhausted system reserve

CLI:
  ram-advisor.py status [--json]      composite verdict
  ram-advisor.py budget [--json]      total / ARC / GGUF / available math
  ram-advisor.py advisory [--json]    actionable hints only
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = Path("/etc/sovereign-os/ram.toml")
DEV_CONFIG = REPO_ROOT / "config" / "ram.toml.example"


def resolve_config_path(explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit if explicit.exists() else None
    env = os.environ.get("SOVEREIGN_OS_RAM_CONFIG")
    if env:
        p = Path(env)
        return p if p.exists() else None
    if DEFAULT_CONFIG.exists():
        return DEFAULT_CONFIG
    if DEV_CONFIG.exists():
        return DEV_CONFIG
    return None


def load_config(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"_source": "(missing — using master-spec defaults)"}
    try:
        with path.open("rb") as fh:
            doc = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as e:
        return {"_source": str(path), "_parse_error": str(e)}
    doc["_source"] = str(path)
    return doc


def read_meminfo() -> dict[str, int]:
    p = Path("/proc/meminfo")
    out: dict[str, int] = {}
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


def read_zfs_arc() -> dict[str, Any]:
    """Returns {arc_max_bytes, arc_size_bytes, arc_module_loaded}.

    arc_max_bytes is the operator-set ceiling (zfs_arc_max).
    arc_size_bytes is the current ARC residency (from arcstats).
    """
    arc_max_path = Path("/sys/module/zfs/parameters/zfs_arc_max")
    arcstats_path = Path("/proc/spl/kstat/zfs/arcstats")
    arc_max = None
    arc_size = None
    arc_loaded = arc_max_path.exists()
    if arc_loaded:
        try:
            arc_max = int(arc_max_path.read_text().strip() or "0")
        except (OSError, ValueError):
            pass
    if arcstats_path.exists():
        try:
            for line in arcstats_path.read_text().splitlines():
                parts = line.split()
                if len(parts) == 3 and parts[0] == "size":
                    arc_size = int(parts[2])
                    break
        except OSError:
            pass
    return {
        "arc_module_loaded": arc_loaded,
        "arc_max_bytes": arc_max,
        "arc_size_bytes": arc_size,
    }


def derive_verdict(cfg: dict[str, Any], mi: dict[str, int], arc: dict[str, Any]) -> dict[str, Any]:
    GIB = 1024 * 1024 * 1024
    KB_PER_GIB = 1024 * 1024
    expected_total_gib = float(cfg.get("expected_total_gib", 256))
    arc_max_gib_cfg = float(cfg.get("arc_max_gib", 128))
    gguf_context_max_gib = float(cfg.get("gguf_context_max_gib", 64))

    live_total_gib = round(mi.get("MemTotal", 0) / KB_PER_GIB, 2) if mi else 0
    live_available_gib = round(mi.get("MemAvailable", 0) / KB_PER_GIB, 2) if mi else 0
    live_used_gib = round(live_total_gib - live_available_gib, 2)

    arc_max_live_gib = (arc.get("arc_max_bytes") or 0) / GIB if arc.get("arc_max_bytes") else None
    arc_size_live_gib = (arc.get("arc_size_bytes") or 0) / GIB if arc.get("arc_size_bytes") else None

    delta_total_pct = (
        (live_total_gib - expected_total_gib) / expected_total_gib * 100
        if expected_total_gib > 0
        else 0
    )

    advisories: list[str] = []
    verdict = "ok"

    if live_total_gib > 0 and delta_total_pct < -2.0:
        if delta_total_pct < -10.0:
            verdict = "critical"
            advisories.append(
                f"live MemTotal {live_total_gib} GiB is {abs(delta_total_pct):.0f}% "
                f"BELOW operator-expected {expected_total_gib} GiB — likely a failed "
                "DIMM. Cross-check with `bios-info memory --json` for unpopulated slots."
            )
        else:
            verdict = "attention"
            advisories.append(
                f"live MemTotal {live_total_gib} GiB is {abs(delta_total_pct):.0f}% "
                f"below expected {expected_total_gib} GiB. Inspect dmidecode -t memory."
            )

    # ZFS ARC vs configured ceiling.
    if arc["arc_module_loaded"]:
        if arc_max_live_gib is not None and arc_max_live_gib > arc_max_gib_cfg + 0.5:
            if verdict == "ok":
                verdict = "attention"
            advisories.append(
                f"zfs_arc_max = {arc_max_live_gib:.1f} GiB EXCEEDS the master-spec "
                f"ceiling of {arc_max_gib_cfg} GiB. Set in /etc/modprobe.d/zfs.conf: "
                f"`options zfs zfs_arc_max={int(arc_max_gib_cfg * GIB)}`."
            )
        if arc_size_live_gib is not None and arc_size_live_gib > arc_max_gib_cfg + 0.5:
            verdict = "critical"
            advisories.append(
                f"ZFS ARC live size = {arc_size_live_gib:.1f} GiB EXCEEDS ceiling "
                f"of {arc_max_gib_cfg} GiB. Inference + ARC are competing for RAM. "
                "Reset ARC: `echo 3 > /proc/sys/vm/drop_caches` (read-only side-effect)."
            )
    else:
        advisories.append(
            "ZFS module not loaded — master spec §19 calls for ZFS root + "
            "ARC clamp. Not critical if operator chose ext4 / btrfs intentionally."
        )

    # GGUF context budget vs available.
    # Available math: total - ARC ceiling - declared GGUF ceiling = headroom
    # for non-ARC, non-model-context workloads (SSH, dashboard, agents).
    if live_total_gib > 0:
        budget_for_ai_max = live_total_gib - arc_max_gib_cfg
        if gguf_context_max_gib > budget_for_ai_max:
            if verdict == "ok":
                verdict = "attention"
            advisories.append(
                f"gguf_context_max_gib = {gguf_context_max_gib} GiB exceeds "
                f"budget after ARC clamp (total {live_total_gib} - ARC "
                f"{arc_max_gib_cfg} = {budget_for_ai_max:.1f} GiB available). "
                "Reduce gguf_context_max_gib OR lower arc_max_gib OR add DIMMs."
            )

    return {
        "verdict": verdict,
        "advisories": advisories,
        "metrics": {
            "expected_total_gib": expected_total_gib,
            "live_total_gib": live_total_gib,
            "live_available_gib": live_available_gib,
            "live_used_gib": live_used_gib,
            "delta_total_pct": round(delta_total_pct, 2),
            "arc_max_gib_cfg": arc_max_gib_cfg,
            "arc_max_live_gib": round(arc_max_live_gib, 2) if arc_max_live_gib else None,
            "arc_size_live_gib": round(arc_size_live_gib, 2) if arc_size_live_gib else None,
            "arc_module_loaded": arc["arc_module_loaded"],
            "gguf_context_max_gib": gguf_context_max_gib,
            "non_ai_headroom_gib": round(
                max(0.0, live_total_gib - arc_max_gib_cfg - gguf_context_max_gib),
                2,
            ),
        },
    }


def cmd_status(args: argparse.Namespace) -> int:
    cfg = load_config(resolve_config_path(args.config))
    mi = read_meminfo()
    arc = read_zfs_arc()
    result = derive_verdict(cfg, mi, arc)
    out = {
        "round": "R279",
        "vector": "E1.M16 (256GB-DDR5-RAM-advisor)",
        "config_source": cfg.get("_source"),
        **result,
    }
    rc = 1 if result["verdict"] in {"attention", "critical"} else 0
    if args.json:
        print(json.dumps(out, indent=2))
        return rc
    print(f"── R279 sovereign-os ram-advisor status (E1.M16) ──")
    print(f"  config:                  {cfg.get('_source')}")
    m = result["metrics"]
    print(f"  expected total (cfg):    {m['expected_total_gib']} GiB")
    print(f"  live total:              {m['live_total_gib']} GiB  (Δ={m['delta_total_pct']}%)")
    print(f"  live used / available:   {m['live_used_gib']} / {m['live_available_gib']} GiB")
    print(f"  ZFS ARC ceiling (cfg):   {m['arc_max_gib_cfg']} GiB")
    print(f"  ZFS ARC live max:        {m['arc_max_live_gib']} GiB")
    print(f"  ZFS ARC live size:       {m['arc_size_live_gib']} GiB")
    print(f"  ZFS module loaded:       {m['arc_module_loaded']}")
    print(f"  GGUF context ceiling:    {m['gguf_context_max_gib']} GiB")
    print(f"  Non-AI headroom:         {m['non_ai_headroom_gib']} GiB")
    print()
    print(f"  verdict: {result['verdict']}")
    for a in result["advisories"]:
        print(f"    ⚠ {a}")
    return rc


def cmd_budget(args: argparse.Namespace) -> int:
    cfg = load_config(resolve_config_path(args.config))
    mi = read_meminfo()
    arc = read_zfs_arc()
    result = derive_verdict(cfg, mi, arc)
    out = {
        "round": "R279",
        "vector": "E1.M16 (ram-budget)",
        "config_source": cfg.get("_source"),
        "metrics": result["metrics"],
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"── R279 ram-advisor budget (E1.M16) ──")
    m = result["metrics"]
    print(f"  TOTAL                                {m['live_total_gib']} GiB")
    print(f"  - ZFS ARC ceiling                  − {m['arc_max_gib_cfg']} GiB")
    print(f"  - GGUF context ceiling             − {m['gguf_context_max_gib']} GiB")
    print(f"  = NON-AI HEADROOM                    {m['non_ai_headroom_gib']} GiB")
    return 0


def cmd_advisory(args: argparse.Namespace) -> int:
    cfg = load_config(resolve_config_path(args.config))
    mi = read_meminfo()
    arc = read_zfs_arc()
    result = derive_verdict(cfg, mi, arc)
    out = {
        "round": "R279",
        "vector": "E1.M16 (ram-advisory)",
        "verdict": result["verdict"],
        "advisories": result["advisories"],
    }
    rc = 1 if result["verdict"] in {"attention", "critical"} else 0
    if args.json:
        print(json.dumps(out, indent=2))
        return rc
    print(f"── R279 ram-advisor advisory (E1.M16) ──")
    print(f"  verdict: {result['verdict']}")
    if not result["advisories"]:
        print("  (no advisories — host RAM posture matches master-spec)")
        return rc
    for a in result["advisories"]:
        print(f"\n  • {a}")
    return rc


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ram-advisor.py",
        description="R279 (E1.M16) — 256 GB DDR5 RAM advisor: live total + ZFS ARC + GGUF ceiling.",
    )
    p.add_argument("--config", type=Path)
    sub = p.add_subparsers(dest="verb", required=True)
    for name, fn, helptxt in [
        ("status", cmd_status, "composite verdict + metrics"),
        ("budget", cmd_budget, "total / ARC / GGUF / non-AI headroom math"),
        ("advisory", cmd_advisory, "actionable hints only"),
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
