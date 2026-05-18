#!/usr/bin/env python3
"""scripts/hardware/ccd-pinning.py — R356 (E1.M41).

Operator-named (master spec §19.2 verbatim "Core Isolation Strategy"):

  | Execution Layer        | Physical Core Allocation | Thread Mask              |
  | ---                    | ---                      | ---                      |
  | The Pulse Core         | Cores 0–5 (CCD 0)        | 0-11    (0xfff)          |
  | The Weaver & Auditor   | Cores 6–9 (CCD 1)        | 12-19   (0xff000)        |
  | System Host / OS Base  | Cores 10–11 (CCD 1)      | 20-23   (0xf00000)       |

  "The Ryzen 9 9900X is an engineering masterpiece, but it contains
   a distinct structural boundary that will introduce severe 'Friction'
   if ignored: it utilizes a dual-CCD (Core Complex Die) design. CCD 0
   accesses its own local 32MB of L3 cache. CCD 1 accesses its own
   isolated 32MB of L3 cache. If the Conductor Agent running your
   state logic is executing on Core 2 (CCD 0), and it attempts to
   pipe a vector array to a compilation runtime executing on Core 8
   (CCD 1), the data must traverse the internal AMD Infinity Fabric.
   This introduces an immediate L3 cache miss and a massive
   cross-die latency penalty."

Until R356, the operator's intended mask appeared in console output
(trinity weaver brief) but no verb actually verified that the live
service processes were pinned correctly. R356 closes that gap:

  - reads /proc/<pid>/status Cpus_allowed_mask for known services
  - compares each PID against the operator's §19.2 intended mask
  - reports drift with the taskset --cpu-list command to remediate

CLI:
  ccd-pinning.py show                      [--config P] [--json|--human]
                                            print the operator's §19.2
                                            intended allocation table
  ccd-pinning.py verify                    [--config P] [--json|--human]
                                            probe live PIDs; report
                                            actual vs intended; rc=1
                                            if any drift; NEVER raise
  ccd-pinning.py recommend                 [--config P] [--json|--human]
                                            emit operator-runnable
                                            taskset commands for any
                                            drifted process

Operator-overlay (R283/SDD-030): /etc/sovereign-os/ccd-pinning.toml
  - override unit_to_mask map per host
  - override CCD core-range catalog (different Ryzen SKU)

Exit codes:
  0  no drift / show rendered
  1  ≥1 service drifted from intended mask
  2  usage error
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

REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
try:
    from operator_overlay import load_with_overlay  # type: ignore
except Exception:  # pragma: no cover
    load_with_overlay = None


SCHEMA_VERSION = "1.0.0"
ROUND = "R356"
SDD_VECTOR = "E1.M41"


# Operator's §19.2 intended allocation, verbatim mapping:
#   Pulse Core            → CCD 0 cores 0-5 → 12 threads 0-11 → mask 0xfff
#   Weaver & Auditor      → CCD 1 cores 6-9 → 8 threads 12-19 → mask 0xff000
#   System Host / OS Base → CCD 1 cores 10-11 → 4 threads 20-23 → mask 0xf00000
#
# Note: §19.2 names the layers; the systemd service unit names land them.
# Pulse = sovereign-pulse.service; Weaver = (state-fabric process; CPU thread)
# Auditor = sovereign-guardian-core; Host = anything else.
DEFAULT_LAYER_CATALOG: list[dict[str, Any]] = [
    {
        "layer": "Pulse Core",
        "ccd": 0,
        "core_range": "0-5",
        "thread_range": "0-11",
        "thread_mask_hex": "0xfff",
        "thread_mask_int": 0xfff,
        "responsibility": ("AVX-512 vector processing + 1-bit bitnet.cpp "
                            "matrix lookups + local runtime compilation"),
        "service_units": ["sovereign-pulse.service"],
    },
    {
        "layer": "Weaver & Auditor",
        "ccd": 1,
        "core_range": "6-9",
        "thread_range": "12-19",
        "thread_mask_hex": "0xff000",
        "thread_mask_int": 0xff000,
        "responsibility": ("state engine + parses CLAUDE.md + manages "
                            "gRPC streams from Tetragon + routes "
                            "network I/O"),
        "service_units": [
            "sovereign-guardian-core.service",
            # weaver atomic-state runs as a library invoked by callers;
            # no dedicated service yet. operator overlay can add when shipped.
        ],
    },
    {
        "layer": "System Host / OS Base",
        "ccd": 1,
        "core_range": "10-11",
        "thread_range": "20-23",
        "thread_mask_hex": "0xf00000",
        "thread_mask_int": 0xf00000,
        "responsibility": ("standard Debian kernel interrupts + Marvell "
                            "10GbE network drivers + background ZFS "
                            "compression threads"),
        "service_units": [
            # Host = default; everything not pulse/weaver/auditor lands here.
            # No explicit unit pinning by operator design.
        ],
    },
]


# ── Probing ────────────────────────────────────────────────────────
def _systemctl_mainpid(unit: str) -> int | None:
    """Get MainPID of a systemd unit. NEVER raises. Returns None when
    systemctl unavailable / unit not active / probe fails."""
    if not shutil.which("systemctl"):
        return None
    try:
        cp = subprocess.run(
            ["systemctl", "show", "-p", "MainPID", "--value", unit],
            capture_output=True, text=True, timeout=3,
        )
    except Exception:
        return None
    if cp.returncode != 0:
        return None
    val = cp.stdout.strip()
    if not val or val == "0":
        return None
    try:
        return int(val)
    except ValueError:
        return None


def _read_cpus_allowed_mask(pid: int) -> int | None:
    """Parse Cpus_allowed_mask from /proc/<pid>/status. NEVER raises."""
    try:
        body = Path(f"/proc/{pid}/status").read_text(encoding="utf-8")
    except OSError:
        return None
    for line in body.splitlines():
        if line.startswith("Cpus_allowed:"):
            # "Cpus_allowed:\tff000" (hex without 0x prefix; per-process)
            val = line.split("\t", 1)[1].replace(",", "").strip()
            try:
                return int(val, 16)
            except ValueError:
                return None
    return None


def _online_cpu_count() -> int:
    """Best-effort CPU count for sanity-checking declared masks."""
    try:
        return os.cpu_count() or 0
    except Exception:
        return 0


def derive_service_state(layer: dict, unit: str) -> dict[str, Any]:
    """For a single (layer, service unit) pair, derive its pinning state."""
    pid = _systemctl_mainpid(unit)
    actual_mask = _read_cpus_allowed_mask(pid) if pid else None
    intended_mask = int(layer.get("thread_mask_int", 0))
    drifted = (
        actual_mask is not None and actual_mask != intended_mask
    )
    return {
        "layer": layer.get("layer"),
        "service_unit": unit,
        "pid": pid,
        "intended_mask_hex": layer.get("thread_mask_hex"),
        "intended_mask_int": intended_mask,
        "actual_mask_int": actual_mask,
        "actual_mask_hex": (f"0x{actual_mask:x}"
                             if actual_mask is not None else None),
        "probed": pid is not None and actual_mask is not None,
        "drifted": bool(drifted),
        # remediation command (operator-runnable):
        "remediation": (
            f"systemctl set-property {unit} "
            f"AllowedCPUs={layer.get('thread_range')}"
            if intended_mask else None
        ),
    }


def verify_all(layers: list[dict]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for layer in layers:
        if not isinstance(layer, dict):
            continue
        units = layer.get("service_units") or []
        if not units:
            # Layer with no service unit (e.g. Host) — record an
            # informational row that says "unpinned by design".
            rows.append({
                "layer": layer.get("layer"),
                "service_unit": None,
                "pid": None,
                "intended_mask_hex": layer.get("thread_mask_hex"),
                "intended_mask_int": int(layer.get("thread_mask_int", 0)),
                "actual_mask_int": None,
                "actual_mask_hex": None,
                "probed": False,
                "drifted": False,
                "remediation": None,
                "note": ("layer has no service unit declared — operator "
                          "convention is 'everything not pulse/weaver/"
                          "auditor lands here'"),
            })
            continue
        for unit in units:
            rows.append(derive_service_state(layer, unit))
    drift_count = sum(1 for r in rows if r["drifted"])
    probed_count = sum(1 for r in rows if r["probed"])
    return {
        "rows": rows,
        "drift_count": drift_count,
        "probed_count": probed_count,
        "row_count": len(rows),
    }


# ── Loading ────────────────────────────────────────────────────────
def load_state(overlay_path: Path | None) -> tuple[list[dict], dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    layers = list(DEFAULT_LAYER_CATALOG)
    if load_with_overlay is not None:
        loaded = load_with_overlay(
            "ccd-pinning", {"layers": []}, explicit_path=overlay_path,
        )
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]
        if loaded.get("layers"):
            layers = list(loaded["layers"])
    return layers, meta


# ── Renderers ──────────────────────────────────────────────────────
def render_show_human(layers: list[dict]) -> str:
    lines = ["── R356 CCD pinning intended allocation (master spec §19.2) ──"]
    lines.append(f"  CPU count (this host): {_online_cpu_count()}")
    lines.append("")
    lines.append(f"  {'LAYER':<24}  {'CCD':<3}  {'CORES':<6}  "
                  f"{'THREADS':<8}  MASK")
    lines.append(f"  {'─'*24}  {'─'*3}  {'─'*6}  {'─'*8}  {'─'*10}")
    for layer in layers:
        lines.append(
            f"  {layer.get('layer', '?'):<24}  "
            f"{str(layer.get('ccd', '?')):<3}  "
            f"{layer.get('core_range', '?'):<6}  "
            f"{layer.get('thread_range', '?'):<8}  "
            f"{layer.get('thread_mask_hex', '?')}"
        )
    return "\n".join(lines) + "\n"


def render_verify_human(state: dict) -> str:
    lines = [f"── R356 CCD pinning verify (master spec §19.2) ──"]
    lines.append(f"  rows: {state['row_count']} | probed: {state['probed_count']} "
                  f"| drifted: {state['drift_count']}")
    lines.append("")
    for row in state["rows"]:
        unit = row.get("service_unit") or "(no unit)"
        if row.get("probed"):
            glyph = "✗" if row["drifted"] else "✓"
            lines.append(
                f"  {glyph} [{row['layer']}] {unit}: "
                f"actual={row['actual_mask_hex']} "
                f"intended={row['intended_mask_hex']}"
            )
            if row["drifted"]:
                lines.append(f"     → {row.get('remediation')}")
        elif row.get("note"):
            lines.append(f"  · [{row['layer']}] {unit}: {row['note'][:60]}…")
        else:
            lines.append(
                f"  · [{row['layer']}] {unit}: not running / un-probed "
                f"(intended={row['intended_mask_hex']})"
            )
    return "\n".join(lines) + "\n"


def render_recommend_human(state: dict) -> str:
    drifted = [r for r in state["rows"] if r["drifted"]]
    lines = [f"── R356 CCD pinning recommend "
             f"({len(drifted)} drifted service(s)) ──"]
    if not drifted:
        lines.append("  ✓ no drift detected — all probed services match "
                      "master spec §19.2")
        return "\n".join(lines) + "\n"
    for r in drifted:
        lines.append("")
        lines.append(f"  [{r['layer']}] {r['service_unit']} (pid {r['pid']})")
        lines.append(f"    drift:    actual={r['actual_mask_hex']} → "
                      f"intended={r['intended_mask_hex']}")
        lines.append(f"    fix:      $ {r['remediation']}")
        lines.append(f"    then:     $ systemctl daemon-reload && "
                      f"systemctl restart {r['service_unit']}")
    return "\n".join(lines) + "\n"


# ── Main ──────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ccd-pinning.py")
    sub = p.add_subparsers(dest="cmd", required=True)

    for verb in ("show", "verify", "recommend"):
        sp = sub.add_parser(verb)
        sp.add_argument("--config", type=Path)
        spg = sp.add_mutually_exclusive_group()
        spg.add_argument("--json", dest="fmt", action="store_const", const="json")
        spg.add_argument("--human", dest="fmt", action="store_const", const="human")
        sp.set_defaults(fmt="json")

    args = p.parse_args(argv)
    layers, meta = load_state(getattr(args, "config", None))

    if args.cmd == "show":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "cpu_count": _online_cpu_count(),
                "layer_count": len(layers),
                "layers": layers,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_show_human(layers), end="")
        return 0

    if args.cmd == "verify":
        state = verify_all(layers)
        out = {
            "schema_version": SCHEMA_VERSION,
            "round": ROUND,
            "sdd_vector": SDD_VECTOR,
            "cpu_count": _online_cpu_count(),
            **state,
            "overlay": meta,
        }
        if args.fmt == "json":
            print(json.dumps(out, indent=2))
        else:
            print(render_verify_human(state), end="")
        return 1 if state["drift_count"] > 0 else 0

    if args.cmd == "recommend":
        state = verify_all(layers)
        drifted = [r for r in state["rows"] if r["drifted"]]
        out = {
            "schema_version": SCHEMA_VERSION,
            "round": ROUND,
            "sdd_vector": SDD_VECTOR,
            "drift_count": len(drifted),
            "drifted_services": drifted,
            "remediation_commands": [r["remediation"] for r in drifted],
            "overlay": meta,
        }
        if args.fmt == "json":
            print(json.dumps(out, indent=2))
        else:
            print(render_recommend_human(state), end="")
        return 1 if drifted else 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
