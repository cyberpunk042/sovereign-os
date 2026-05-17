#!/usr/bin/env python3
"""scripts/hardware/psu-oc-mode-orchestrator.py — R313 (E1.M33).

Operator-named (§1b mandate row, verbatim): "be Quiet! Dark Power
Pro 13 1600W Power Supply | ATX 3.1 Compliant | 80 Plus Titanium ...
My PSU even have an overclock mode which might be important".
Closes E1.M33 — fills the stop-hook-flagged "no PSU overclock-mode
orchestration" gap.

The Dark Power Pro 13 1600W has a physical OC-switch (mode switch on
the PSU) that combines its multiple +12V rails into one stronger
single-rail mode. Multi-rail (OFF) = safer for legacy hardware via
OCP per-rail; single-rail (ON) = full 1600W on one rail (no per-rail
ceiling).

OS CAN'T detect the physical switch state — operator declares the
state via overlay. This script then provides per-state safe-ceiling
recommendations for R292/R294 OC orchestration.

CLI:
  psu-oc-mode-orchestrator.py status    [--config P] [--json|--human]
  psu-oc-mode-orchestrator.py recipe    [--config P] [--json|--human]
  psu-oc-mode-orchestrator.py recommend [--config P] [--json|--human]

Operator-overlay (R283/SDD-030): /etc/sovereign-os/psu-oc-mode-
orchestrator.toml — operator declares oc_mode (on / off / unknown)
+ psu_model (default dark-power-pro-13-1600w) + dual_gpu (bool).

Exit codes:
  0  rendered
  1  oc_mode = unknown (operator needs to declare)
  2  usage error
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


SCHEMA_VERSION = "1.0.0"
ROUND = "R313"
SDD_VECTOR = "E1.M33"


DEFAULTS = {
    "oc_mode": "unknown",      # on / off / unknown
    "psu_model": "dark-power-pro-13-1600w",
    "dual_gpu": True,           # operator's stated SAIN-01 posture
}


PSU_CATALOG: dict[str, dict[str, Any]] = {
    "dark-power-pro-13-1600w": {
        "display_name": "be Quiet! Dark Power Pro 13 1600W",
        "form_factor": "ATX 3.1",
        "efficiency_rating": "80 Plus Titanium",
        "wattage_rated_w": 1600,
        "rails_multi_rail_w_each": 35.0 * 12,  # 35A × 12V per rail
        "rail_count": 6,
        "rail_topology": "Multi-rail (OCP per rail) OR single-rail (OC switch ON)",
        "oc_switch_present": True,
        "oc_switch_location": "Rear face of PSU near AC inlet — slide "
                              "switch with 'OC' marking",
        "oc_mode_off_max_safe_w_per_rail": 35 * 12,
        "oc_mode_on_max_single_rail_w": 1600,
        "max_safe_oc_multiplier_oc_off": 1.10,
        "max_safe_oc_multiplier_oc_on": 1.25,
        "dual_gpu_dual_rail_assignment": (
            "When OC OFF: route GPU1 to PCIe Cable 1 (rail group A) "
            "and GPU2 to PCIe Cable 3 (rail group B) so transient "
            "spikes don't trip per-rail OCP."
        ),
        "operator_caveats": [
            "OC mode ON disables per-rail OCP — a short on ONE rail "
            "won't be caught by per-rail; system relies on OPP/OCP "
            "of the whole PSU. Safer for sustained dual-GPU draw.",
            "ATX 3.1 already handles GPU transient spikes (up to 3x "
            "rated TGP for 100µs) so OC mode is mostly about per-"
            "rail vs whole-PSU OCP topology, not headroom expansion.",
            "Operator MUST power-off + unplug AC before flipping the "
            "physical OC switch.",
        ],
        "recipe_steps": [
            "1. shutdown -h now (graceful poweroff)",
            "2. Unplug AC cable from PSU",
            "3. Wait 60s for capacitor drain",
            "4. Slide OC switch on rear face of PSU to desired position",
            "5. Reconnect AC + power on",
            "6. Boot OK → re-declare oc_mode in overlay: "
            "sudo tee /etc/sovereign-os/psu-oc-mode-orchestrator.toml <<<'oc_mode = \"on\"'",
        ],
    },
    "generic-multi-rail": {
        "display_name": "Generic multi-rail ATX PSU (fallback)",
        "form_factor": "Unknown",
        "efficiency_rating": "Unknown",
        "wattage_rated_w": 0,
        "rails_multi_rail_w_each": 0,
        "rail_count": 0,
        "rail_topology": "Unknown",
        "oc_switch_present": False,
        "oc_switch_location": None,
        "oc_mode_off_max_safe_w_per_rail": 0,
        "oc_mode_on_max_single_rail_w": 0,
        "max_safe_oc_multiplier_oc_off": 1.05,
        "max_safe_oc_multiplier_oc_on": 1.05,
        "dual_gpu_dual_rail_assignment": (
            "Unknown PSU — operator should use the PSU's spec sheet "
            "to identify rail groupings + cable assignments."
        ),
        "operator_caveats": [
            "Generic fallback — no OC switch assumed; conservative "
            "ceiling = 1.05x. Operator should declare an exact PSU "
            "via overlay psu_model = '<name>' to unlock the full "
            "per-PSU catalog.",
        ],
        "recipe_steps": [],
    },
}


def load_state(overlay_path: Path | None) -> tuple[dict, dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    cfg = dict(DEFAULTS)
    if load_with_overlay is not None:
        loaded = load_with_overlay("psu-oc-mode-orchestrator", DEFAULTS,
                                    explicit_path=overlay_path)
        cfg.update({k: v for k, v in loaded.items() if not k.startswith("_")})
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]
    return cfg, meta


def resolve_psu(cfg: dict) -> dict:
    name = cfg.get("psu_model", "dark-power-pro-13-1600w")
    return PSU_CATALOG.get(name, PSU_CATALOG["generic-multi-rail"])


def derive_recommendation(cfg: dict, psu: dict) -> dict[str, Any]:
    oc_mode = cfg.get("oc_mode", "unknown")
    dual_gpu = bool(cfg.get("dual_gpu", False))
    if oc_mode == "unknown":
        return {
            "verdict": "oc-mode-undeclared",
            "rc": 1,
            "max_safe_oc_multiplier": psu.get("max_safe_oc_multiplier_oc_off", 1.05),
            "message": "Operator MUST declare oc_mode in overlay "
                       "(on / off). Until then, using OFF-mode "
                       "conservative ceiling.",
            "operator_action": "Edit /etc/sovereign-os/psu-oc-mode-"
                                "orchestrator.toml: set oc_mode = "
                                "\"on\" or \"off\" depending on the "
                                "physical PSU switch position.",
        }
    if oc_mode == "on":
        max_mult = psu.get("max_safe_oc_multiplier_oc_on", 1.05)
        msg = (f"PSU OC mode ON — single-rail topology gives full "
               f"{psu.get('oc_mode_on_max_single_rail_w', 0)}W "
               f"available; safe OC multiplier ceiling = {max_mult}x.")
        verdict = "oc-mode-on-headroom-unlocked"
    else:  # off
        max_mult = psu.get("max_safe_oc_multiplier_oc_off", 1.05)
        msg = (f"PSU OC mode OFF — multi-rail (per-rail OCP active); "
               f"safe OC multiplier ceiling = {max_mult}x. For dual-"
               f"GPU operator must spread cables across rail groups.")
        verdict = "oc-mode-off-per-rail-active"

    extra = []
    if dual_gpu and oc_mode == "off":
        extra.append(psu.get("dual_gpu_dual_rail_assignment", ""))

    return {
        "verdict": verdict,
        "rc": 0,
        "max_safe_oc_multiplier": max_mult,
        "message": msg,
        "additional_notes": extra,
    }


def render_status_human(cfg: dict, psu: dict, rec: dict) -> str:
    lines = [f"── R313 sovereign-os PSU OC-mode orchestrator (E1.M33) ──"]
    lines.append(f"  PSU model:           {psu.get('display_name')}")
    lines.append(f"  form factor:         {psu.get('form_factor')}")
    lines.append(f"  efficiency rating:   {psu.get('efficiency_rating')}")
    lines.append(f"  rated wattage:       {psu.get('wattage_rated_w')}W")
    lines.append(f"  rail topology:       {psu.get('rail_topology')}")
    lines.append("")
    lines.append(f"  operator-declared OC mode:  {cfg.get('oc_mode')}")
    lines.append(f"  operator-declared dual GPU: {cfg.get('dual_gpu')}")
    lines.append("")
    lines.append(f"  verdict:                    {rec['verdict']} (rc={rec['rc']})")
    lines.append(f"  max safe OC multiplier:     {rec['max_safe_oc_multiplier']}x")
    lines.append(f"  message:                    {rec['message']}")
    if rec.get("additional_notes"):
        lines.append("")
        for n in rec["additional_notes"]:
            if n:
                lines.append(f"    • {n}")
    if rec.get("operator_action"):
        lines.append("")
        lines.append(f"  operator action: {rec['operator_action']}")
    return "\n".join(lines) + "\n"


def render_recipe_human(psu: dict) -> str:
    lines = [f"── R313 PSU OC-mode switch recipe (E1.M33) ──",
             f"  PSU: {psu.get('display_name')}",
             ""]
    if not psu.get("oc_switch_present"):
        lines.append("  This PSU has no OC switch — recipe N/A.")
        return "\n".join(lines) + "\n"
    lines.append(f"  switch location: {psu.get('oc_switch_location')}")
    lines.append("")
    lines.append("  steps:")
    for s in psu.get("recipe_steps", []):
        lines.append(f"    {s}")
    if psu.get("operator_caveats"):
        lines.append("")
        lines.append("  caveats:")
        for c in psu["operator_caveats"]:
            lines.append(f"    • {c}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="psu-oc-mode-orchestrator.py")
    sub = p.add_subparsers(dest="verb", required=True)
    for verb in ("status", "recipe", "recommend"):
        sp = sub.add_parser(verb)
        sp.add_argument("--config", type=Path)
        fmt = sp.add_mutually_exclusive_group()
        fmt.add_argument("--json", dest="fmt", action="store_const", const="json")
        fmt.add_argument("--human", dest="fmt", action="store_const", const="human")
        sp.set_defaults(fmt="json")

    args = p.parse_args(argv)
    cfg, meta = load_state(args.config)
    psu = resolve_psu(cfg)
    rec = derive_recommendation(cfg, psu)

    if args.verb == "recipe":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "psu_model": cfg.get("psu_model"),
                "oc_switch_present": psu.get("oc_switch_present"),
                "oc_switch_location": psu.get("oc_switch_location"),
                "recipe_steps": psu.get("recipe_steps", []),
                "operator_caveats": psu.get("operator_caveats", []),
                "overlay": meta,
            }, indent=2))
        else:
            print(render_recipe_human(psu), end="")
        return 0

    if args.verb == "recommend":
        # recommend = the recommendation core only.
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "oc_mode_declared": cfg.get("oc_mode"),
                "psu_model": cfg.get("psu_model"),
                "dual_gpu_declared": cfg.get("dual_gpu"),
                "verdict": rec["verdict"],
                "rc": rec["rc"],
                "max_safe_oc_multiplier": rec["max_safe_oc_multiplier"],
                "message": rec["message"],
                "additional_notes": rec.get("additional_notes", []),
                "operator_action": rec.get("operator_action"),
                "overlay": meta,
            }, indent=2))
        else:
            print(render_status_human(cfg, psu, rec), end="")
        return rec["rc"]

    # status
    doc = {
        "schema_version": SCHEMA_VERSION,
        "round": ROUND,
        "sdd_vector": SDD_VECTOR,
        "config": cfg,
        "psu": psu,
        "recommendation": rec,
        "overlay": meta,
    }
    if args.fmt == "json":
        print(json.dumps(doc, indent=2))
    else:
        print(render_status_human(cfg, psu, rec), end="")
    return rec["rc"]


if __name__ == "__main__":
    sys.exit(main())
