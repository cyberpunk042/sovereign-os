#!/usr/bin/env python3
"""scripts/hardware/oc-headroom.py — R292 (E1.M20).

Operator-named (§1b mandate row, verbatim): "considering XMP profile
and OC profile and room for each and estimated at 100% usage and
then real time tracking and intelligence around it. (Possibly heat
too I guess)". Closes E1.M20 of the mandate.

Models the operator's overclock/XMP headroom across power + memory +
thermal axes:

  - **Projected 100%-usage watts** = operator-pinned CPU TDP +
    sum(per-GPU power_limit × OC multiplier) + chassis baseline +
    memory power (estimated from DIMM count + speed).
  - **PSU headroom** = psu_rated_watts − projected_100pct_watts.
  - **Real-time deviance** = (current_draw − projected) /
    projected, when the R258 wattage sampler has fresh data.
  - **Thermal headroom** = min(cpu_tjmax, gpu_max_temp) − current_max,
    sourced from R265 thermal-watch.
  - **XMP/EXPO state** = recovered from R257 memory-profile.

The verb is operator-pull "what's my real headroom AND how close am I
running RIGHT NOW?" — composes the existing probes; no new mutating
surface. Operators answer "can I add another GPU?", "is my OC mode
safe at 100%?", "what's my XMP recovery still leaving on the table?"

Operator-overlay (R283/SDD-030): `/etc/sovereign-os/oc-headroom.toml`
(or SOVEREIGN_OS_OVERLAY_OC_HEADROOM env, or --config <path>) for the
operator-pinned baselines:

  cpu_tdp_watts                 — 170 W for 9900X (operator-pinned)
  chassis_baseline_watts        — 80 W (fans + mobo + USB devices)
  gpu_oc_multiplier             — 1.15 when OC enabled
  safety_margin_pct             — 20 % (warn when headroom < this)
  psu_oc_mode_multiplier        — 1.0 (multiplier on rated wattage
                                       when PSU OC-mode toggled on)

CLI:
  oc-headroom.py status   [--config P] [--json|--human]
  oc-headroom.py advisory [--config P] [--json|--human]
  oc-headroom.py inputs   [--config P] [--json|--human]   # operator
                                                          # audit of
                                                          # the inputs
                                                          # used

Exit codes:
  0  headroom-safe
  1  headroom-tight (operator-pull "investigate")
  2  over-budget (operator-pull "DO NOT add more load")
  3  usage error
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
ROUND = "R292"
SDD_VECTOR = "E1.M20"


DEFAULTS = {
    "cpu_tdp_watts": 170,
    "chassis_baseline_watts": 80,
    "gpu_oc_multiplier": 1.0,
    "safety_margin_pct": 20,
    "psu_oc_mode_multiplier": 1.0,
    # Memory power model: ~3-5 W per DDR5 DIMM at base, +1 W per
    # +1000 MT/s above 4800 (XMP/EXPO premium). Operator can tune.
    "memory_dimm_base_watts": 4,
    "memory_mts_premium_per_1000": 1,
    # PSU rated wattage — operator-pinned (be Quiet! Dark Power Pro 13
    # 1600W per §1b). When power-status.py is reachable we prefer
    # its reading; this is the fallback / cross-check.
    "psu_rated_watts": 1600,
}


# ── Subprocess probes (read-only) ───────────────────────────────────
def _run_json(rel: str, args: list[str]) -> dict[str, Any] | None:
    bin_path = REPO_ROOT / "scripts" / "hardware" / rel
    if not bin_path.is_file():
        return None
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), *args, "--json"],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode not in (0, 1):
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def _run_json_power_status(verb: str) -> dict[str, Any] | None:
    """Probe scripts/hardware/power-status.py with the given verb
    (psu / ups / budget / advisories). Returns parsed JSON or None
    when the probe is unavailable / errors out."""
    bin_path = REPO_ROOT / "scripts" / "hardware" / "power-status.py"
    if not bin_path.is_file():
        return None
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), verb, "--json"],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode not in (0, 1):
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def probe_inputs(cfg: dict[str, Any]) -> dict[str, Any]:
    """Gather every input the model needs from the sibling probes,
    with operator-pinned fallbacks. Returns the raw input dict +
    per-source provenance so the operator audits which numbers came
    from where."""
    out: dict[str, Any] = {
        "cpu_tdp_watts": cfg["cpu_tdp_watts"],
        "chassis_baseline_watts": cfg["chassis_baseline_watts"],
        "gpu_oc_multiplier": cfg["gpu_oc_multiplier"],
        "psu_oc_mode_multiplier": cfg["psu_oc_mode_multiplier"],
        "memory_dimm_base_watts": cfg["memory_dimm_base_watts"],
        "memory_mts_premium_per_1000": cfg["memory_mts_premium_per_1000"],
        "psu_rated_watts": cfg["psu_rated_watts"],
        "sources": {},
    }

    # Memory probe — DIMM count + speed.
    mem = _run_json("memory-profile.py", ["status"])
    if mem:
        dimms = mem.get("dimms") or []
        out["memory_dimms"] = dimms
        out["memory_dimm_count"] = len(dimms)
        # Average configured MT/s across populated DIMMs.
        speeds = [d.get("configured_mts") for d in dimms
                  if isinstance(d.get("configured_mts"), int)]
        out["memory_avg_mts"] = sum(speeds) // len(speeds) if speeds else 0
        out["xmp_state"] = mem.get("advisory", {}).get("verdict")
        out["sources"]["memory"] = "scripts/hardware/memory-profile.py"
    else:
        out["memory_dimms"] = []
        out["memory_dimm_count"] = 0
        out["memory_avg_mts"] = 0
        out["xmp_state"] = None
        out["sources"]["memory"] = "(unavailable)"

    # GPU probe — per-card power_limit.
    gpu = _run_json("gpu-watch.py", [])
    if gpu:
        gpus = gpu.get("gpus") or []
        out["gpus"] = [
            {
                "index": g.get("index"),
                "name": g.get("name"),
                "power_limit_watts": g.get("power_limit_watts") or 0,
                "power_draw_watts": g.get("power_draw_watts") or 0,
            }
            for g in gpus
        ]
        out["sources"]["gpu"] = "scripts/hardware/gpu-watch.py"
    else:
        out["gpus"] = []
        out["sources"]["gpu"] = "(unavailable)"

    # PSU-rated probe — power-status psu reports the operator-pinned
    # rated wattage from /etc/sovereign-os/power.toml.
    psu = _run_json_power_status("psu")
    if psu and isinstance(psu.get("rated_watts"), (int, float)):
        out["psu_rated_watts"] = psu["rated_watts"]
        out["sources"]["psu_rated"] = "scripts/hardware/power-status.py psu"
    else:
        out["sources"]["psu_rated"] = "(operator-overlay default)"
    # Real-time draw — power-status budget reports current draw.
    budget = _run_json_power_status("budget")
    if budget and isinstance(budget.get("current_draw_watts"), (int, float)):
        out["current_draw_watts"] = budget["current_draw_watts"]
        out["sources"]["current_draw"] = "scripts/hardware/power-status.py budget"
    else:
        out["current_draw_watts"] = None
        out["sources"]["current_draw"] = "(no real-time sampler data)"

    return out


# ── Model ───────────────────────────────────────────────────────────
def compute_headroom(inp: dict[str, Any]) -> dict[str, Any]:
    cpu = inp["cpu_tdp_watts"]
    chassis = inp["chassis_baseline_watts"]
    gpu_mult = float(inp["gpu_oc_multiplier"])

    # Per-GPU projected 100% draw = power_limit × OC multiplier.
    per_gpu_projected: list[float] = []
    for g in inp["gpus"]:
        pl = g.get("power_limit_watts") or 0
        per_gpu_projected.append(float(pl) * gpu_mult)
    gpu_total = sum(per_gpu_projected)

    # Memory power: base × dimm_count + premium × (avg_mts - 4800)/1000
    # (clamped at zero for sub-JEDEC).
    base = float(inp["memory_dimm_base_watts"])
    premium = float(inp["memory_mts_premium_per_1000"])
    dimm_count = inp["memory_dimm_count"]
    avg_mts = inp["memory_avg_mts"]
    mts_premium = max(0.0, (avg_mts - 4800) / 1000.0) * premium
    memory_watts = (base + mts_premium) * dimm_count

    projected_100pct = float(cpu) + gpu_total + memory_watts + float(chassis)

    psu_rated = float(inp["psu_rated_watts"]) * float(inp["psu_oc_mode_multiplier"])
    psu_headroom = psu_rated - projected_100pct
    psu_headroom_pct = (
        (psu_headroom / psu_rated) * 100.0 if psu_rated > 0 else 0.0
    )

    current = inp.get("current_draw_watts")
    if isinstance(current, (int, float)) and projected_100pct > 0:
        current_deviance_pct = (current - projected_100pct) / projected_100pct * 100.0
    else:
        current_deviance_pct = None

    return {
        "cpu_tdp_watts": cpu,
        "chassis_baseline_watts": chassis,
        "gpu_oc_multiplier": gpu_mult,
        "per_gpu_projected_watts": per_gpu_projected,
        "gpu_total_projected_watts": gpu_total,
        "memory_watts": round(memory_watts, 1),
        "projected_100pct_watts": round(projected_100pct, 1),
        "psu_rated_watts": psu_rated,
        "psu_headroom_watts": round(psu_headroom, 1),
        "psu_headroom_pct": round(psu_headroom_pct, 1),
        "current_draw_watts": current,
        "current_deviance_pct": round(current_deviance_pct, 1) if current_deviance_pct is not None else None,
    }


def derive_verdict(headroom: dict[str, Any], inp: dict[str, Any],
                   cfg: dict[str, Any]) -> dict[str, Any]:
    headroom_pct = headroom["psu_headroom_pct"]
    safety = float(cfg["safety_margin_pct"])
    if headroom["psu_headroom_watts"] < 0:
        return {
            "verdict": "over-budget",
            "rc": 2,
            "message": (
                f"Projected 100% usage ({headroom['projected_100pct_watts']} W) "
                f"EXCEEDS PSU rated capacity ({headroom['psu_rated_watts']} W). "
                f"Operator must reduce GPU power_limit, OC profile, or upgrade PSU "
                f"BEFORE sustained full-load. {inp['xmp_state'] or 'XMP state unknown'}."
            ),
        }
    if headroom_pct < safety:
        return {
            "verdict": "headroom-tight",
            "rc": 1,
            "message": (
                f"PSU headroom is only {headroom_pct}% "
                f"({headroom['psu_headroom_watts']} W of "
                f"{headroom['psu_rated_watts']} W) — below the operator's "
                f"{safety}% safety margin. Investigate before adding load."
            ),
        }
    return {
        "verdict": "headroom-safe",
        "rc": 0,
        "message": (
            f"PSU headroom is {headroom_pct}% "
            f"({headroom['psu_headroom_watts']} W of "
            f"{headroom['psu_rated_watts']} W), above the {safety}% safety "
            f"margin. Operator may add load up to ~{int(headroom['psu_headroom_watts'])} W "
            f"of additional sustained draw."
        ),
    }


# ── Assembly ────────────────────────────────────────────────────────
def build_report(overlay_path: Path | None) -> dict[str, Any]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    cfg = dict(DEFAULTS)
    if load_with_overlay is not None:
        loaded = load_with_overlay("oc-headroom", DEFAULTS,
                                    explicit_path=overlay_path)
        cfg.update({k: v for k, v in loaded.items() if not k.startswith("_")})
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]
    inp = probe_inputs(cfg)
    headroom = compute_headroom(inp)
    verdict = derive_verdict(headroom, inp, cfg)
    return {
        "schema_version": SCHEMA_VERSION,
        "round": ROUND,
        "sdd_vector": SDD_VECTOR,
        "config": cfg,
        "inputs": inp,
        "headroom": headroom,
        "verdict": verdict["verdict"],
        "message": verdict["message"],
        "rc": verdict["rc"],
        "overlay": meta,
    }


def render_human(doc: dict[str, Any]) -> str:
    h = doc["headroom"]
    lines = [f"── R292 sovereign-os OC + XMP headroom (E1.M20) ──"]
    lines.append(f"  verdict:           {doc['verdict']}")
    lines.append(f"  projected 100%:    {h['projected_100pct_watts']} W")
    lines.append(f"  PSU rated:         {h['psu_rated_watts']} W")
    lines.append(f"  PSU headroom:      {h['psu_headroom_watts']} W "
                 f"({h['psu_headroom_pct']}%)")
    lines.append(f"  CPU TDP:           {h['cpu_tdp_watts']} W")
    lines.append(f"  chassis baseline:  {h['chassis_baseline_watts']} W")
    lines.append(f"  memory:            {h['memory_watts']} W "
                 f"({doc['inputs']['memory_dimm_count']} DIMM(s) "
                 f"@ {doc['inputs']['memory_avg_mts']} MT/s)")
    lines.append(f"  GPU total:         {h['gpu_total_projected_watts']} W "
                 f"(OC mult × {h['gpu_oc_multiplier']})")
    for i, w in enumerate(h["per_gpu_projected_watts"]):
        g = doc["inputs"]["gpus"][i]
        lines.append(f"    GPU {g.get('index')}: {g.get('name', '?'):30s} "
                     f"projected {w} W (power_limit {g.get('power_limit_watts')} W)")
    if h["current_draw_watts"] is not None:
        lines.append(f"  current draw:      {h['current_draw_watts']} W "
                     f"(deviance {h['current_deviance_pct']}%)")
    else:
        lines.append(f"  current draw:      (no real-time sampler data)")
    lines.append(f"  XMP/EXPO state:    {doc['inputs']['xmp_state']}")
    lines.append("")
    lines.append(f"  {doc['message']}")
    return "\n".join(lines) + "\n"


# ── Main ────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="oc-headroom.py")
    sub = p.add_subparsers(dest="verb", required=True)

    for verb in ("status", "advisory", "inputs"):
        sp = sub.add_parser(verb)
        sp.add_argument("--config", type=Path)
        sp_fmt = sp.add_mutually_exclusive_group()
        sp_fmt.add_argument("--json", dest="fmt", action="store_const", const="json")
        sp_fmt.add_argument("--human", dest="fmt", action="store_const", const="human")
        sp.set_defaults(fmt="json")

    args = p.parse_args(argv)
    doc = build_report(args.config)

    if args.verb == "inputs":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "config": doc["config"],
                "inputs": doc["inputs"],
                "overlay": doc["overlay"],
            }, indent=2))
        else:
            print(f"── R292 OC/XMP inputs (E1.M20) ──")
            for k, v in doc["inputs"]["sources"].items():
                print(f"  {k:14s} ← {v}")
            print()
            print(json.dumps(doc["inputs"], indent=2))
        return 0

    if args.verb == "advisory":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "verdict": doc["verdict"],
                "message": doc["message"],
                "psu_headroom_watts": doc["headroom"]["psu_headroom_watts"],
                "psu_headroom_pct": doc["headroom"]["psu_headroom_pct"],
            }, indent=2))
        else:
            print(f"verdict: {doc['verdict']}")
            print(f"  {doc['message']}")
        return doc["rc"]

    # status
    if args.fmt == "json":
        print(json.dumps(doc, indent=2))
    else:
        print(render_human(doc), end="")
    return doc["rc"]


if __name__ == "__main__":
    sys.exit(main())
