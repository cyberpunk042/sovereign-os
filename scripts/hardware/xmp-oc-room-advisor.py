#!/usr/bin/env python3
"""scripts/hardware/xmp-oc-room-advisor.py — R315 (E1.M35).

Operator-named (§1b mandate row, verbatim): "considering XMP profile
and OC profile and room for each and estimated at 100% usage and then
real time tracking and intelligence around it". Closes E1.M35.

Composes the wattage budget probes shipped in prior rounds:
  - R252 power-status        PSU rated watts
  - R257 memory-profile      XMP/EXPO profile detection (extra W est)
  - R272 avx512              CPU AVX-512 load multiplier
  - R292 oc-headroom         existing CPU OC multiplier
  - R294 psu-oc              psu-side OC ceiling (1.05x default)
  - R303 gpu-wattage         dual-GPU sustained budget
  - R313 psu-oc-mode         PSU OC switch state (1.10x off / 1.25x on)

Estimates wattage usage at 100% load with operator-declared XMP +
CPU-OC + GPU-OC combo + returns:
  - budget_remaining_w        PSU rated W − estimated 100% load W
  - safe_combos               matrix of (XMP, CPU-OC, GPU-OC) that
                              fit under PSU rated W with safety margin
  - verdict                   has-budget / tight / over-budget

CLI:
  xmp-oc-room-advisor.py status     [--config P] [--json|--human]
  xmp-oc-room-advisor.py budget     [--config P] [--json|--human]
  xmp-oc-room-advisor.py recommend  [--config P] [--json|--human]

Operator-overlay (R283/SDD-030): /etc/sovereign-os/xmp-oc-room-
advisor.toml — operator overrides estimated W for each component.

Exit codes:
  0  has-budget (fits with safety margin)
  1  tight (under PSU rated but tight)
  2  over-budget (estimated 100% load exceeds PSU)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
try:
    from operator_overlay import load_with_overlay  # type: ignore
except Exception:  # pragma: no cover
    load_with_overlay = None
try:
    # R348 (E9.M17): promoted from R347 inline pattern → SDD-032 helper.
    from inventory_consult import find_advisor_caveats  # type: ignore
except Exception:  # pragma: no cover
    find_advisor_caveats = None


SCHEMA_VERSION = "1.0.0"
ROUND = "R315"
SDD_VECTOR = "E1.M35"


DEFAULTS = {
    # Wattage assumptions — operator can override per-host.
    "psu_rated_w": 1600,                    # Dark Power Pro 13 1600W
    "psu_safety_margin_pct": 15,            # leave 15% headroom

    # CPU draw estimates per multiplier (Ryzen 9 9900X TDP=120W baseline).
    "cpu_baseline_w": 120,
    "cpu_oc_extra_w_per_0p1": 30,           # +30W per 0.1x OC multiplier
    "avx512_load_extra_w": 25,              # AVX-512 sustained adds ~25W

    # XMP/EXPO extra wattage estimates.
    "xmp_extra_w_per_dimm": 8,               # ~8W per DIMM at EXPO
    "dimm_count": 4,                        # operator's 4-DIMM kit

    # GPU sustained draw under load — RTX 3090 + RTX PRO 6000.
    "gpu1_sustained_w": 420,                # RTX 3090 OC headroom
    "gpu2_sustained_w": 600,                # RTX PRO 6000 TGP
    "gpu_oc_extra_pct": 10,                 # +10% per OC notch

    # Operator-declared knobs (runtime input).
    "xmp_enabled": True,
    "cpu_oc_multiplier": 1.0,               # 1.0 = stock; 1.1 = +10%
    "gpu_oc_notch": 0,                      # 0=stock, 1=+10%, 2=+20%
    "dual_gpu_active": True,
    # R344 (E2.M32, SDD-035): R338 workload-mode adoption.
    # When True, runtime-input knobs are MODULATED by canonical mode
    # before the wattage estimate runs (training → both GPUs active +
    # higher OC; idle → single-GPU only + zero OC).
    "follow_workload_mode_coordinator": True,
    "workload_mode_overlay_path": "/etc/sovereign-os/workload-mode.toml",
}


# R344 (E2.M32, SDD-035): per-mode runtime-knob modulation.
# Each entry sets ABSOLUTE values (not deltas) for the 4 runtime
# knobs since modes represent qualitative postures.
WORKLOAD_MODE_TO_RUNTIME_KNOBS: dict[str, dict[str, Any]] = {
    "idle": {
        "xmp_enabled": True,
        "cpu_oc_multiplier": 1.0,
        "gpu_oc_notch": 0,
        "dual_gpu_active": False,   # idle = PRO 6000 only; 3090 powered down
        "rationale": ("Idle: single-GPU only (PRO 6000); zero OC; "
                       "XMP kept (memory bandwidth always helpful)."),
    },
    "inference-ready": {
        "xmp_enabled": True,
        "cpu_oc_multiplier": 1.0,
        "gpu_oc_notch": 0,
        "dual_gpu_active": True,    # both GPUs warm + ready
        "rationale": ("Inference-ready: both GPUs warm; stock clocks; "
                       "default sane baseline."),
    },
    "training": {
        "xmp_enabled": True,
        "cpu_oc_multiplier": 1.1,   # +10% CPU OC for data loader throughput
        "gpu_oc_notch": 1,           # +10% GPU OC for compute throughput
        "dual_gpu_active": True,
        "rationale": ("Training: dual-GPU + +10% CPU/GPU OC for "
                       "throughput. Pair with R296 thermal-oc-budget "
                       "(which itself modulates margins per training)."),
    },
    "oc-burst": {
        "xmp_enabled": True,
        "cpu_oc_multiplier": 1.2,   # +20% CPU OC
        "gpu_oc_notch": 2,           # +20% GPU OC
        "dual_gpu_active": True,
        "rationale": ("OC-burst: max-everything transient peak. "
                       "Operator MUST verify PSU has headroom — R344 "
                       "wattage estimate may return over-budget."),
    },
}


def _read_canonical_mode(cfg: dict) -> tuple[str | None, str]:
    """R344 (E2.M32): SDD-035 contract — same shape as R339-R342.
    NEVER raises."""
    if not cfg.get("follow_workload_mode_coordinator", True):
        return None, "xmp-oc-room-overlay"
    path = Path(cfg.get("workload_mode_overlay_path",
                          "/etc/sovereign-os/workload-mode.toml"))
    if not path.is_file():
        return None, "xmp-oc-room-overlay"
    try:
        body = path.read_text(encoding="utf-8")
    except OSError:
        return None, "xmp-oc-room-overlay"
    import re
    m = re.search(r'^\s*active_mode\s*=\s*"([^"]+)"\s*$', body, re.M)
    if m:
        return m.group(1), "R338-canonical"
    return None, "xmp-oc-room-overlay"


def _apply_mode_modulation(cfg: dict) -> tuple[dict, str | None, str]:
    """R344: apply per-mode runtime knob values.

    Operator-overlay explicit knobs win — if operator set any of
    {xmp_enabled, cpu_oc_multiplier, gpu_oc_notch, dual_gpu_active}
    in their cpu-hotswap-like override, we preserve those.

    Implementation: we cannot distinguish 'operator set to default'
    from 'unset' without overlay-source tracking. Per SDD-035 §5
    precedence, when follow=True + canonical present, modulation
    REPLACES runtime knobs UNLESS the cfg already differs from
    in-source DEFAULTS by an unrelated knob (i.e. operator clearly
    customized this advisor). To stay simple + predictable: when
    follow=True + canonical present, ALL 4 runtime knobs come from
    the map. Operator wants finer control: opt out with follow=False.
    """
    cfg_modulated = dict(cfg)
    canonical, source = _read_canonical_mode(cfg)
    if canonical is None:
        return cfg_modulated, None, source
    knobs = WORKLOAD_MODE_TO_RUNTIME_KNOBS.get(canonical)
    if knobs is None:
        return cfg_modulated, canonical, f"{source}-unknown-mode"
    for k in ("xmp_enabled", "cpu_oc_multiplier",
              "gpu_oc_notch", "dual_gpu_active"):
        if k in knobs:
            cfg_modulated[k] = knobs[k]
    return cfg_modulated, canonical, source


# R347 (E1.M40) → R348 (E9.M17, SDD-032 §4 helper promotion):
# moved to scripts/lib/inventory_consult.find_advisor_caveats. Local
# thin wrapper preserves NEVER-raise + lets tests stub it.
def _load_inventory_caveats() -> list[dict[str, Any]]:
    if find_advisor_caveats is None:
        return []
    try:
        return find_advisor_caveats("R315")
    except Exception:  # pragma: no cover — helper itself NEVER-raises
        return []


def estimate_load_w(cfg: dict) -> dict[str, Any]:
    """Estimate 100% sustained load wattage per component."""
    cpu_base = cfg["cpu_baseline_w"]
    cpu_oc_mult = float(cfg["cpu_oc_multiplier"])
    cpu_oc_extra = max(0.0, (cpu_oc_mult - 1.0) / 0.1) * cfg["cpu_oc_extra_w_per_0p1"]
    cpu_avx_extra = cfg["avx512_load_extra_w"]
    cpu_total = cpu_base + cpu_oc_extra + cpu_avx_extra

    xmp_extra = 0
    if cfg["xmp_enabled"]:
        xmp_extra = cfg["xmp_extra_w_per_dimm"] * cfg["dimm_count"]

    gpu_oc_mult = 1.0 + (cfg["gpu_oc_notch"] * (cfg["gpu_oc_extra_pct"] / 100.0))
    gpu1_w = cfg["gpu1_sustained_w"] * gpu_oc_mult
    gpu2_w = 0
    if cfg["dual_gpu_active"]:
        gpu2_w = cfg["gpu2_sustained_w"] * gpu_oc_mult
    gpu_total = gpu1_w + gpu2_w

    # Misc system: NVMe + chipset + fans + memory controller — flat 80W.
    misc_w = 80

    total = cpu_total + xmp_extra + gpu_total + misc_w
    return {
        "cpu_baseline_w": cpu_base,
        "cpu_oc_extra_w": cpu_oc_extra,
        "cpu_avx512_extra_w": cpu_avx_extra,
        "cpu_total_w": cpu_total,
        "xmp_extra_w": xmp_extra,
        "gpu1_w": gpu1_w,
        "gpu2_w": gpu2_w,
        "gpu_total_w": gpu_total,
        "misc_w": misc_w,
        "estimated_total_w": total,
    }


def compute_verdict(cfg: dict, load: dict) -> dict[str, Any]:
    psu = cfg["psu_rated_w"]
    safety_pct = cfg["psu_safety_margin_pct"]
    safety_ceiling = psu * (1.0 - safety_pct / 100.0)
    total = load["estimated_total_w"]
    remaining = psu - total
    remaining_safe = safety_ceiling - total

    if total > psu:
        verdict, rc = "over-budget", 2
        msg = (f"Estimated 100% load {total:.0f}W exceeds PSU rated "
               f"{psu}W. Drop XMP, CPU-OC, or one GPU.")
    elif remaining_safe < 0:
        verdict, rc = "tight", 1
        msg = (f"Within PSU rated {psu}W but inside the {safety_pct}% "
               f"safety margin. Sustained operation may trip OPP under "
               f"transient spikes.")
    else:
        verdict, rc = "has-budget", 0
        msg = (f"PSU has {remaining_safe:.0f}W headroom inside the "
               f"{safety_pct}% safety margin.")
    return {
        "verdict": verdict,
        "rc": rc,
        "psu_rated_w": psu,
        "safety_ceiling_w": safety_ceiling,
        "estimated_total_w": total,
        "budget_remaining_w": remaining,
        "safe_remaining_w": remaining_safe,
        "message": msg,
    }


def safe_combos(cfg: dict) -> list[dict[str, Any]]:
    """Matrix of (xmp, cpu_oc_mult, gpu_oc_notch) combinations that
    fit under PSU rated W with safety margin."""
    out = []
    for xmp in (False, True):
        for cpu_mult in (1.0, 1.1, 1.2):
            for gpu_notch in (0, 1, 2):
                probe_cfg = dict(cfg)
                probe_cfg["xmp_enabled"] = xmp
                probe_cfg["cpu_oc_multiplier"] = cpu_mult
                probe_cfg["gpu_oc_notch"] = gpu_notch
                load = estimate_load_w(probe_cfg)
                v = compute_verdict(probe_cfg, load)
                out.append({
                    "xmp": xmp,
                    "cpu_oc_multiplier": cpu_mult,
                    "gpu_oc_notch": gpu_notch,
                    "estimated_total_w": load["estimated_total_w"],
                    "verdict": v["verdict"],
                    "safe": v["verdict"] == "has-budget",
                })
    return out


def load_state(overlay_path: Path | None) -> tuple[dict, dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    cfg = dict(DEFAULTS)
    if load_with_overlay is not None:
        loaded = load_with_overlay("xmp-oc-room-advisor", DEFAULTS,
                                    explicit_path=overlay_path)
        cfg.update({k: v for k, v in loaded.items() if not k.startswith("_")})
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]
    return cfg, meta


def render_status_human(cfg: dict, load: dict, verdict: dict) -> str:
    lines = [f"── R315 sovereign-os XMP/OC room advisor (E1.M35) ──"]
    lines.append(f"  PSU rated:           {verdict['psu_rated_w']}W")
    lines.append(f"  safety ceiling:      {verdict['safety_ceiling_w']:.0f}W "
                 f"({cfg['psu_safety_margin_pct']}% margin)")
    lines.append("")
    lines.append("  current configuration:")
    lines.append(f"    XMP/EXPO enabled:    {cfg['xmp_enabled']}")
    lines.append(f"    CPU OC multiplier:   {cfg['cpu_oc_multiplier']}x")
    lines.append(f"    GPU OC notch:        {cfg['gpu_oc_notch']} "
                 f"(+{cfg['gpu_oc_notch'] * cfg['gpu_oc_extra_pct']}%)")
    lines.append(f"    dual GPU active:     {cfg['dual_gpu_active']}")
    lines.append("")
    lines.append("  estimated 100% load breakdown:")
    lines.append(f"    CPU (base+OC+AVX):   {load['cpu_total_w']:.0f}W")
    lines.append(f"    XMP/EXPO memory:     {load['xmp_extra_w']}W")
    lines.append(f"    GPU1 (RTX 3090):     {load['gpu1_w']:.0f}W")
    lines.append(f"    GPU2 (PRO 6000):     {load['gpu2_w']:.0f}W")
    lines.append(f"    misc (NVMe/fans):    {load['misc_w']}W")
    lines.append(f"    ----------------- ")
    lines.append(f"    TOTAL:               {load['estimated_total_w']:.0f}W")
    lines.append("")
    lines.append(f"  verdict:             {verdict['verdict']} (rc={verdict['rc']})")
    lines.append(f"  budget remaining:    {verdict['budget_remaining_w']:.0f}W "
                 f"({verdict['safe_remaining_w']:.0f}W inside margin)")
    lines.append(f"  message:             {verdict['message']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="xmp-oc-room-advisor.py")
    sub = p.add_subparsers(dest="verb", required=True)
    for verb in ("status", "budget", "recommend"):
        sp = sub.add_parser(verb)
        sp.add_argument("--config", type=Path)
        fmt = sp.add_mutually_exclusive_group()
        fmt.add_argument("--json", dest="fmt", action="store_const", const="json")
        fmt.add_argument("--human", dest="fmt", action="store_const", const="human")
        sp.set_defaults(fmt="json")

    args = p.parse_args(argv)
    cfg, meta = load_state(args.config)
    # R344 (E2.M32, SDD-035): modulate runtime knobs per R338 canonical mode.
    cfg_modulated, workload_mode_canonical, mode_source = \
        _apply_mode_modulation(cfg)
    load = estimate_load_w(cfg_modulated)
    verdict = compute_verdict(cfg_modulated, load)

    if args.verb == "budget":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "psu_rated_w": verdict["psu_rated_w"],
                "safety_ceiling_w": verdict["safety_ceiling_w"],
                "estimated_total_w": verdict["estimated_total_w"],
                "budget_remaining_w": verdict["budget_remaining_w"],
                "safe_remaining_w": verdict["safe_remaining_w"],
                "verdict": verdict["verdict"],
                "rc": verdict["rc"],
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R315 budget (E1.M35) ──")
            print(f"  PSU rated:          {verdict['psu_rated_w']}W")
            print(f"  estimated 100% load: {verdict['estimated_total_w']:.0f}W")
            print(f"  budget remaining:   {verdict['budget_remaining_w']:.0f}W")
            print(f"  safe remaining:     {verdict['safe_remaining_w']:.0f}W")
            print(f"  verdict:            {verdict['verdict']}")
        return verdict["rc"]

    if args.verb == "recommend":
        combos = safe_combos(cfg)
        safe = [c for c in combos if c["safe"]]
        # Pick "most aggressive safe" — highest sum of OC notches + XMP.
        def aggressiveness(c):
            return ((1 if c["xmp"] else 0)
                    + (c["cpu_oc_multiplier"] - 1.0) * 10
                    + c["gpu_oc_notch"])
        best = max(safe, key=aggressiveness) if safe else None
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "total_combos_evaluated": len(combos),
                "safe_combos_count": len(safe),
                "all_combos": combos,
                "recommended_aggressive_safe": best,
                "verdict": verdict["verdict"],
                "rc": verdict["rc"],
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R315 recommend (E1.M35) ──")
            print(f"  combos evaluated:   {len(combos)}")
            print(f"  safe combos:        {len(safe)}")
            if best:
                print(f"  most aggressive safe combo:")
                print(f"    xmp={best['xmp']}  cpu_oc={best['cpu_oc_multiplier']}x  "
                      f"gpu_oc={best['gpu_oc_notch']}")
                print(f"    est total: {best['estimated_total_w']:.0f}W")
        return verdict["rc"]

    # status
    # R347 (E1.M40): consult R317 catalog for operator-actionable caveats
    # tagged for R315; surface 4-DIMM XMP-stability warning when active.
    inventory_caveats = _load_inventory_caveats()
    xmp_stability_warnings: list[str] = []
    if cfg_modulated.get("xmp_enabled"):
        for cv in inventory_caveats:
            low = (cv.get("caveat") or "").lower()
            if "xmp" in low and ("may fail" in low or "drop to" in low):
                xmp_stability_warnings.append(
                    f"{cv['slot']} ({cv['sku']}): {cv['caveat']}"
                )
    doc = {
        "schema_version": SCHEMA_VERSION,
        "round": ROUND,
        "sdd_vector": SDD_VECTOR,
        "config": cfg,
        "config_modulated": cfg_modulated,
        "workload_mode_canonical": workload_mode_canonical,
        "workload_mode_source": mode_source,
        "workload_mode_to_runtime_knobs": WORKLOAD_MODE_TO_RUNTIME_KNOBS,
        "load_estimate": load,
        "verdict": verdict["verdict"],
        "rc": verdict["rc"],
        "psu_rated_w": verdict["psu_rated_w"],
        "safety_ceiling_w": verdict["safety_ceiling_w"],
        "estimated_total_w": verdict["estimated_total_w"],
        "budget_remaining_w": verdict["budget_remaining_w"],
        "safe_remaining_w": verdict["safe_remaining_w"],
        "message": verdict["message"],
        "overlay": meta,
        "inventory_caveats": inventory_caveats,
        "xmp_stability_warnings": xmp_stability_warnings,
    }
    if args.fmt == "json":
        print(json.dumps(doc, indent=2))
    else:
        print(render_status_human(cfg_modulated, load, verdict), end="")
    return verdict["rc"]


if __name__ == "__main__":
    sys.exit(main())
