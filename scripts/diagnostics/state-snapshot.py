#!/usr/bin/env python3
"""scripts/diagnostics/state-snapshot.py — R322 (E2.M18).

Operator-pull umbrella that runs ALL the read-only advisors shipped
over the perpetual E9.M3 intake loop, IN PARALLEL via subprocess,
and emits ONE consolidated JSON document. Useful for:

  - fleet aggregation (one host → one snapshot → one timeseries row)
  - before-and-after change auditing
  - one-shot "what's the COMPLETE state of this host right now?"

The snapshot is READ-ONLY — never writes any overlay or mutates any
component. It composes the per-axis advisors that already ship; if
operator wants ACT, they pick the relevant per-axis verb.

CLI:
  state-snapshot.py snapshot [--config P] [--json|--human]
                              run every read-only advisor + emit
                              consolidated JSON
  state-snapshot.py audit    [--config P] [--json|--human]
                              list the per-axis advisors that would
                              run + their cmdline (dry-run catalog)

Operator-overlay (R283/SDD-030): /etc/sovereign-os/state-snapshot.toml
  - max_workers   (default 8 — concurrent subprocess pool)
  - per_probe_timeout_sec (default 10)
  - [[probes]]    operator can override or add probe entries

Exit codes:
  0  snapshot completed (some probes may have failed individually —
     captured in per-probe rc field)
  2  usage error
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
try:
    from operator_overlay import load_with_overlay  # type: ignore
except Exception:  # pragma: no cover
    load_with_overlay = None


SCHEMA_VERSION = "1.0.0"
ROUND = "R322"
SDD_VECTOR = "E2.M18"


DEFAULTS = {
    "max_workers": 8,
    "per_probe_timeout_sec": 10,
}


# Catalog of read-only advisor probes. Each entry: name, script,
# args, axis. NONE of these should mutate any state.
DEFAULT_PROBES: list[dict[str, Any]] = [
    # ── hardware ─────────────────────────────────────────
    {"name": "inventory",        "axis": "hardware",
     "script": "scripts/hardware/inventory-catalog.py", "args": ["audit", "--json"]},
    {"name": "board-advisor",    "axis": "hardware",
     "script": "scripts/hardware/board-advisor-x870e-creator.py", "args": ["status", "--json"]},
    {"name": "gpu-wattage",      "axis": "hardware",
     "script": "scripts/hardware/gpu-wattage-catalog.py", "args": ["budget", "--json"]},
    {"name": "cpu-hotswap",      "axis": "hardware",
     "script": "scripts/hardware/cpu-hotswap.py", "args": ["status", "--json"]},
    {"name": "xmp-oc-room",      "axis": "hardware",
     "script": "scripts/hardware/xmp-oc-room-advisor.py", "args": ["status", "--json"]},
    {"name": "psu-oc-mode",      "axis": "power",
     "script": "scripts/hardware/psu-oc-mode-orchestrator.py", "args": ["status", "--json"]},
    {"name": "thermal-oc",       "axis": "thermal",
     "script": "scripts/hardware/thermal-oc-budget.py", "args": ["status", "--json"]},
    {"name": "memory-pressure-damper", "axis": "memory",
     "script": "scripts/hardware/memory-pressure-oc-damper.py", "args": ["status", "--json"]},
    {"name": "heat-oc-throttle", "axis": "thermal",
     "script": "scripts/hardware/heat-oc-autothrottle.py", "args": ["status", "--json"]},

    # ── posture rollups ──────────────────────────────────
    {"name": "operator-posture", "axis": "posture",
     "script": "scripts/hardware/operator-posture.py", "args": ["status", "--json"]},
    {"name": "storage-health",   "axis": "storage",
     "script": "scripts/hardware/storage-health-rollup.py", "args": ["status", "--json"]},
    {"name": "autohealth",       "axis": "diagnostics",
     "script": "scripts/diagnostics/autohealth.py", "args": ["status", "--json"]},

    # ── lifecycle ────────────────────────────────────────
    {"name": "apc-profile",      "axis": "lifecycle",
     "script": "scripts/hardware/apc-default-profile.py", "args": ["list", "--json"]},
    {"name": "battery-ladder",   "axis": "lifecycle",
     "script": "scripts/power/battery-escalation-ladder.py", "args": ["simulate", "--json"]},

    # ── kernel + hardening ───────────────────────────────
    {"name": "kernel-cmdline",   "axis": "kernel",
     "script": "scripts/kernel/cmdline-advisor.py", "args": ["status", "--json"]},
    {"name": "hardening-base",   "axis": "hardening",
     "script": "scripts/hardening/base-catalog.py", "args": ["list", "--json"]},

    # ── network ──────────────────────────────────────────
    {"name": "network-stack",    "axis": "network",
     "script": "scripts/network/runtime-stack-advisor.py", "args": ["status", "--json"]},

    # ── install + model surfaces ────────────────────────
    {"name": "install-mode",     "axis": "install",
     "script": "scripts/install/install-mode-advisor.py", "args": ["recommend", "--json"]},
    {"name": "model-params",     "axis": "model",
     "script": "scripts/models/parametrization.py", "args": ["recommend", "--json"]},
]


def load_state(overlay_path: Path | None) -> tuple[dict, list[dict], dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    cfg = dict(DEFAULTS)
    probes = list(DEFAULT_PROBES)
    if load_with_overlay is not None:
        loaded = load_with_overlay(
            "state-snapshot", {**DEFAULTS, "probes": []},
            explicit_path=overlay_path,
        )
        for k in DEFAULTS:
            if k in loaded:
                cfg[k] = loaded[k]
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]
        if loaded.get("probes"):
            probes = list(loaded["probes"])
    return cfg, probes, meta


def run_one_probe(probe: dict, timeout: int) -> dict[str, Any]:
    name = probe.get("name", "?")
    script = probe.get("script", "")
    args = list(probe.get("args", []))
    full_path = REPO_ROOT / script
    started = time.time()
    if not full_path.is_file():
        return {
            "name": name,
            "axis": probe.get("axis"),
            "script": script,
            "rc": None,
            "duration_ms": 0,
            "available": False,
            "error": f"script not found: {full_path}",
            "output": None,
        }
    try:
        r = subprocess.run(
            [sys.executable, str(full_path), *args],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return {
            "name": name,
            "axis": probe.get("axis"),
            "script": script,
            "rc": None,
            "duration_ms": int((time.time() - started) * 1000),
            "available": True,
            "error": f"subprocess failed: {e}",
            "output": None,
        }
    duration_ms = int((time.time() - started) * 1000)
    output = None
    try:
        output = json.loads(r.stdout)
    except json.JSONDecodeError:
        output = {"raw_stdout": r.stdout[:500],
                  "raw_stderr": r.stderr[:500]}
    return {
        "name": name,
        "axis": probe.get("axis"),
        "script": script,
        "rc": r.returncode,
        "duration_ms": duration_ms,
        "available": True,
        "error": None if isinstance(output, dict) and "raw_stdout" not in output
                 else "non-JSON stdout",
        "output": output,
    }


def render_snapshot_human(doc: dict) -> str:
    lines = [f"── R322 sovereign-os state snapshot (E2.M18) ──",
             f"  snapshot_at:   {doc['snapshot_at']}",
             f"  probe count:   {doc['probe_count']}",
             f"  duration:      {doc['snapshot_duration_ms']}ms",
             f"  available:     {doc['available_count']}",
             f"  failed:        {doc['failed_count']}",
             ""]
    # Group probes by axis.
    by_axis: dict[str, list[dict]] = {}
    for p in doc["probes"]:
        by_axis.setdefault(p.get("axis", "?"), []).append(p)
    for axis in sorted(by_axis.keys()):
        items = by_axis[axis]
        lines.append(f"  ── {axis} ({len(items)}) ──")
        for p in items:
            mark = "OK" if p.get("rc") == 0 else (
                "!!" if p.get("rc") in (1, 2) else "??"
            )
            verdict = ""
            out = p.get("output") or {}
            if isinstance(out, dict):
                # autohealth `status` nests verdict under last_tick.
                verdict = (out.get("verdict")
                           or (out.get("last_tick") or {}).get("verdict")
                           or "")
            lines.append(f"    [{mark}] {p['name']:24s}  "
                          f"rc={p.get('rc')}  {p['duration_ms']:>4d}ms  "
                          f"verdict={verdict}")
        lines.append("")
    return "\n".join(lines)


def build_snapshot(overlay_path: Path | None) -> dict[str, Any]:
    cfg, probes, meta = load_state(overlay_path)
    now = time.time()
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
    timeout = int(cfg["per_probe_timeout_sec"])
    max_workers = int(cfg["max_workers"])
    results: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(run_one_probe, p, timeout): p for p in probes}
        for fut in concurrent.futures.as_completed(futures):
            results.append(fut.result())
    duration_ms = int((time.time() - now) * 1000)
    available = sum(1 for r in results if r.get("available"))
    failed = sum(1 for r in results if r.get("rc") not in (0, None))
    # Sort results to match probe definition order for stable JSON.
    order_by_name = {p.get("name"): i for i, p in enumerate(probes)}
    results.sort(key=lambda r: order_by_name.get(r.get("name"), 999))
    return {
        "schema_version": SCHEMA_VERSION,
        "round": ROUND,
        "sdd_vector": SDD_VECTOR,
        "snapshot_at": started_at,
        "snapshot_at_epoch": now,
        "snapshot_duration_ms": duration_ms,
        "max_workers": max_workers,
        "per_probe_timeout_sec": timeout,
        "probe_count": len(results),
        "available_count": available,
        "failed_count": failed,
        "probes": results,
        "overlay": meta,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="state-snapshot.py")
    sub = p.add_subparsers(dest="verb", required=True)

    ps = sub.add_parser("snapshot")
    ps.add_argument("--config", type=Path)
    fs = ps.add_mutually_exclusive_group()
    fs.add_argument("--json", dest="fmt", action="store_const", const="json")
    fs.add_argument("--human", dest="fmt", action="store_const", const="human")
    ps.set_defaults(fmt="json")

    pa = sub.add_parser("audit")
    pa.add_argument("--config", type=Path)
    fa = pa.add_mutually_exclusive_group()
    fa.add_argument("--json", dest="fmt", action="store_const", const="json")
    fa.add_argument("--human", dest="fmt", action="store_const", const="human")
    pa.set_defaults(fmt="json")

    args = p.parse_args(argv)
    cfg, probes, meta = load_state(args.config)

    if args.verb == "audit":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "probe_count": len(probes),
                "probes": probes,
                "config": cfg,
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R322 snapshot audit (E2.M18) ──")
            print(f"  probe count: {len(probes)}")
            print()
            for p in probes:
                print(f"  {p.get('name'):24s} axis={p.get('axis'):>10s}  "
                      f"{p.get('script')} {' '.join(p.get('args', []))}")
        return 0

    # snapshot
    doc = build_snapshot(args.config)
    if args.fmt == "json":
        print(json.dumps(doc, indent=2))
    else:
        print(render_snapshot_human(doc), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
