#!/usr/bin/env python3
"""scripts/hardware/memory-pressure-oc-damper.py — R304 (E1.M29).

Operator-named (§1b mandate row, verbatim — continuous compose of
"memory" with "OC profile and room for each"): when memory pressure
spikes, an OC-aggressive posture risks compounding the problem (CPU
+ GPU at peak draw while the OOM watcher fires). This advisor reads
R269 memory-pressure + R292 oc-headroom, and recommends:

  - dampen OC by N steps (lowers gpu_oc_multiplier in oc-headroom
    overlay) so the operator gets back PSU + thermal headroom AND
    drops contention for the AC-tap during high memory pressure
  - OR: no dampening when both readings are healthy

Closes E1.M29.

Operator-pull, read-only — emits a recommendation; never auto-mutates.

CLI:
  memory-pressure-oc-damper.py status   [--config P] [--json|--human]
  memory-pressure-oc-damper.py advisory [--config P] [--json|--human]

Operator-overlay (R283/SDD-030): /etc/sovereign-os/memory-pressure-oc-damper.toml

Exit codes:
  0  no dampening needed
  1  dampen-by-1 (mild OC pullback recommended)
  2  dampen-fully (revert to stock; severe memory pressure)
"""
from __future__ import annotations

import argparse
import json
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
ROUND = "R304"
SDD_VECTOR = "E1.M29"


DEFAULTS = {
    # Memory-pressure scoring thresholds (pressure_avg10 from /proc/pressure/memory).
    "memory_pressure_warn_avg10":   30.0,   # ≥30% memory stall window
    "memory_pressure_crit_avg10":   60.0,   # ≥60% sustained stall
    # OC dampening recommendations per severity level.
    "dampen_step_mild":   0.05,   # subtract 5% from gpu_oc_multiplier
    "dampen_step_full":   1.0,    # revert to stock (mult = 1.0)
}


def _run_json(rel: str, args: list[str]) -> dict[str, Any] | None:
    bin_path = REPO_ROOT / rel
    if not bin_path.is_file():
        return None
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), *args],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode not in (0, 1, 2):
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def probe_memory_pressure() -> dict[str, Any] | None:
    return _run_json("scripts/hardware/memory-pressure.py", ["status", "--json"])


def probe_oc_headroom() -> dict[str, Any] | None:
    return _run_json("scripts/hardware/oc-headroom.py", ["status", "--json"])


def derive_recommendation(memp: dict | None, oc: dict | None,
                          cfg: dict) -> dict[str, Any]:
    if memp is None:
        return {"verdict": "memory-probe-unavailable", "rc": 1,
                "current_avg10": None, "memory_pressure_verdict": None,
                "message": "Memory-pressure probe unavailable — operator "
                           "should run R269 memory-pressure to populate "
                           "the score before this advisor can advise."}
    # R269 emits its own verdict (ok/warn/critical) — use it directly.
    memp_verdict = memp.get("verdict")
    # PSI avg10 (when available) is the most precise signal; fall back to
    # mem_available_pct when PSI is unavailable.
    metrics = memp.get("metrics") or {}
    avg10_f = metrics.get("psi_full_avg10_pct")
    if avg10_f is None:
        # Fallback: derive a pseudo-pressure from mem_available_pct.
        mem_pct = metrics.get("mem_available_pct")
        if isinstance(mem_pct, (int, float)):
            avg10_f = max(0.0, 100.0 - float(mem_pct))

    current_oc_mult = None
    psu_verdict = None
    if oc is not None:
        current_oc_mult = oc.get("headroom", {}).get("gpu_oc_multiplier") \
            or oc.get("config", {}).get("gpu_oc_multiplier")
        psu_verdict = oc.get("verdict")

    # Use R269's own verdict as the primary driver — simpler + survives
    # PSI vs non-PSI hosts.
    if memp_verdict == "critical":
        rec_mult = 1.0
        return {
            "verdict": "dampen-fully",
            "rc": 2,
            "current_avg10": avg10_f,
            "memory_pressure_verdict": memp_verdict,
            "current_oc_multiplier": current_oc_mult,
            "recommended_oc_multiplier": rec_mult,
            "dampen_step": cfg["dampen_step_full"],
            "psu_headroom_verdict": psu_verdict,
            "message": ("R269 reports memory-pressure CRITICAL — revert "
                        "GPU OC multiplier to 1.0 (stock). Operator-pull "
                        "command: sovereign-osctl oc-headroom status with "
                        "overlay `gpu_oc_multiplier = 1.0`."),
        }
    if memp_verdict == "warn":
        try:
            mult = float(current_oc_mult) if current_oc_mult is not None else 1.0
        except (TypeError, ValueError):
            mult = 1.0
        rec_mult = max(1.0, round(mult - cfg["dampen_step_mild"], 2))
        return {
            "verdict": "dampen-by-1",
            "rc": 1,
            "current_avg10": avg10_f,
            "memory_pressure_verdict": memp_verdict,
            "current_oc_multiplier": current_oc_mult,
            "recommended_oc_multiplier": rec_mult,
            "dampen_step": cfg["dampen_step_mild"],
            "psu_headroom_verdict": psu_verdict,
            "message": (f"R269 reports memory-pressure WARN — back off "
                        f"GPU OC multiplier by {cfg['dampen_step_mild']} "
                        f"(toward {rec_mult}). Re-evaluate via R269 + R292."),
        }
    return {
        "verdict": "no-dampening",
        "rc": 0,
        "current_avg10": avg10_f,
        "memory_pressure_verdict": memp_verdict,
        "current_oc_multiplier": current_oc_mult,
        "recommended_oc_multiplier": current_oc_mult,
        "dampen_step": 0.0,
        "psu_headroom_verdict": psu_verdict,
        "message": ("R269 reports memory-pressure ok — operator may "
                    "sustain current OC posture."),
    }


def build_report(overlay_path: Path | None) -> dict[str, Any]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    cfg = dict(DEFAULTS)
    if load_with_overlay is not None:
        loaded = load_with_overlay("memory-pressure-oc-damper", DEFAULTS,
                                    explicit_path=overlay_path)
        cfg.update({k: v for k, v in loaded.items() if not k.startswith("_")})
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]

    memp = probe_memory_pressure()
    oc = probe_oc_headroom()
    rec = derive_recommendation(memp, oc, cfg)
    return {
        "schema_version": SCHEMA_VERSION,
        "round": ROUND,
        "sdd_vector": SDD_VECTOR,
        "config": cfg,
        "verdict": rec["verdict"],
        "rc": rec["rc"],
        "message": rec["message"],
        "current_avg10": rec.get("current_avg10"),
        "current_oc_multiplier": rec.get("current_oc_multiplier"),
        "recommended_oc_multiplier": rec.get("recommended_oc_multiplier"),
        "dampen_step": rec.get("dampen_step"),
        "psu_headroom_verdict": rec.get("psu_headroom_verdict"),
        "sources": {
            "memory_pressure": ("scripts/hardware/memory-pressure.py"
                                if memp is not None else "(unavailable)"),
            "oc_headroom": ("scripts/hardware/oc-headroom.py"
                            if oc is not None else "(unavailable)"),
        },
        "overlay": meta,
    }


def render_human(doc: dict) -> str:
    lines = ["── R304 sovereign-os memory-pressure → OC damper (E1.M29) ──"]
    lines.append(f"  verdict:                  {doc['verdict']} (rc={doc['rc']})")
    lines.append(f"  current memory avg10:     {doc.get('current_avg10')}")
    lines.append(f"  current OC multiplier:    {doc.get('current_oc_multiplier')}")
    lines.append(f"  recommended OC multiplier: {doc.get('recommended_oc_multiplier')}")
    lines.append(f"  PSU headroom verdict:     {doc.get('psu_headroom_verdict')}")
    lines.append("")
    lines.append(f"  {doc['message']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="memory-pressure-oc-damper.py")
    sub = p.add_subparsers(dest="verb", required=True)
    for verb in ("status", "advisory"):
        sp = sub.add_parser(verb)
        sp.add_argument("--config", type=Path)
        fmt = sp.add_mutually_exclusive_group()
        fmt.add_argument("--json", dest="fmt", action="store_const", const="json")
        fmt.add_argument("--human", dest="fmt", action="store_const", const="human")
        sp.set_defaults(fmt="json")

    args = p.parse_args(argv)
    doc = build_report(args.config)

    if args.verb == "advisory":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "verdict": doc["verdict"],
                "rc": doc["rc"],
                "message": doc["message"],
                "recommended_oc_multiplier": doc["recommended_oc_multiplier"],
            }, indent=2))
        else:
            print(f"verdict: {doc['verdict']}")
            print(f"  {doc['message']}")
        return doc["rc"]

    if args.fmt == "json":
        print(json.dumps(doc, indent=2))
    else:
        print(render_human(doc), end="")
    return doc["rc"]


if __name__ == "__main__":
    sys.exit(main())
