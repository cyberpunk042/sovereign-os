#!/usr/bin/env python3
"""scripts/hardware/psu-oc.py — R294 (E1.M22).

Operator-named (§1b mandate row, verbatim): "My PSU even have an
overclock mode which might be important". Closes E1.M22 — the third
of the 3-Module batch R285's intake doctrine surfaced.

Models the operator's PSU OC-mode toggle. PSUs like the be Quiet!
Dark Power Pro 13 1600W (operator-pinned in §1b) have a physical
OC-mode switch on the unit that shifts the rated power-output budget
upward (typically: brief-peak capability + sustained-output ceiling
unlocked). The PSU does NOT expose this state via software — the
operator declares it.

The verb is operator-pull "what's my CURRENT PSU OC-mode posture
and what's the effective budget?":

  psu-oc state      → current operator-declared mode + spec
  psu-oc budget     → rated/effective wattage + projection vs load
  psu-oc projection → dual-GPU headroom under standard vs OC mode
                      (composes R292 oc-headroom)

Operator-overlay (R283/SDD-030): `/etc/sovereign-os/psu-oc.toml` for
the operator-declared mode + PSU spec sheet ref.

KNOWN PSU spec sheets are seeded in DEFAULT_PSU_SPECS — operator can
add / replace via overlay's `[[known_psus]]` array.

CLI:
  psu-oc.py state      [--config P] [--json|--human]
  psu-oc.py budget     [--config P] [--json|--human]
  psu-oc.py projection [--config P] [--json|--human]

Exit codes:
  0  rendered
  2  usage error
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
ROUND = "R294"
SDD_VECTOR = "E1.M22"


DEFAULTS = {
    # The PSU model the operator declares they have.
    "operator_psu_model": "be Quiet! Dark Power Pro 13 1600W",
    # Operator-declared OC-mode state. PSU's physical switch isn't
    # software-readable; this is the operator's declaration.
    "oc_mode_enabled": False,
    # Safety margin for the SUSTAINED-output reading (applies in
    # both standard and OC modes — operator's "what budget should
    # I plan against?").
    "sustained_safety_margin_pct": 10,
}


# ── Known PSU spec sheets ──────────────────────────────────────────
#
# Operator-curated. Each entry: model name, rated standard sustained
# watts, OC-mode sustained watts (when applicable), brief-peak watts
# (datasheet headroom), efficiency rating, ATX revision.
DEFAULT_PSU_SPECS: list[dict[str, Any]] = [
    {
        "model": "be Quiet! Dark Power Pro 13 1600W",
        "rated_standard_watts": 1600,
        "rated_oc_mode_watts": 1600,  # this PSU's OC mode is a
                                       # multi-rail → single-rail
                                       # toggle (no sustained-output
                                       # shift); peak-budget shifts
                                       # via ATX 3.1 power excursion
                                       # spec, NOT sustained rating.
        "brief_peak_watts": 3200,      # ATX 3.1 spec: 2× rated for
                                       # ≤ 100 µs transients
        "efficiency": "80 Plus Titanium",
        "atx_revision": "3.1",
        "oc_mode_semantics": (
            "Multi-rail (4×) → single-rail consolidation. Lets one "
            "rail (e.g. GPU PCIe) draw close to the full rated "
            "capacity rather than being capped at per-rail OCP."
        ),
        "operator_notes": "Operator-mandated §1b reference PSU.",
    },
    {
        "model": "be Quiet! Dark Power Pro 13 1300W",
        "rated_standard_watts": 1300,
        "rated_oc_mode_watts": 1300,
        "brief_peak_watts": 2600,
        "efficiency": "80 Plus Titanium",
        "atx_revision": "3.1",
        "oc_mode_semantics": (
            "Same multi-rail → single-rail toggle as the 1600W."
        ),
        "operator_notes": "Sibling unit, lower headroom.",
    },
    {
        "model": "Corsair AX1600i",
        "rated_standard_watts": 1600,
        "rated_oc_mode_watts": 1600,
        "brief_peak_watts": 1800,
        "efficiency": "80 Plus Titanium",
        "atx_revision": "2.4",
        "oc_mode_semantics": "No dedicated OC-mode switch.",
        "operator_notes": "Alternative reference; pre-ATX-3.0.",
    },
]


# ── Probe + assemble ────────────────────────────────────────────────
def resolve_spec(model: str, specs: list[dict]) -> dict | None:
    for s in specs:
        if isinstance(s, dict) and s.get("model") == model:
            return s
    return None


def load_state(overlay_path: Path | None) -> dict[str, Any]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    cfg = dict(DEFAULTS)
    specs = list(DEFAULT_PSU_SPECS)
    if load_with_overlay is not None:
        loaded = load_with_overlay(
            "psu-oc",
            {**DEFAULTS, "known_psus": []},
            explicit_path=overlay_path,
        )
        for k, v in loaded.items():
            if k.startswith("_"):
                continue
            if k == "known_psus":
                if v:
                    specs = list(v)
                continue
            cfg[k] = v
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]
    spec = resolve_spec(cfg["operator_psu_model"], specs)
    return {
        "config": cfg,
        "known_psus": specs,
        "operator_psu": spec,
        "overlay": meta,
    }


def effective_budget(spec: dict | None, cfg: dict) -> dict[str, Any]:
    if spec is None:
        return {
            "rated_watts": None,
            "effective_rated_watts": None,
            "safety_margin_pct": cfg["sustained_safety_margin_pct"],
            "planning_budget_watts": None,
            "oc_mode_enabled": cfg["oc_mode_enabled"],
            "brief_peak_watts": None,
            "note": "operator-declared PSU model not in known_psus registry",
        }
    rated = float(
        spec["rated_oc_mode_watts"]
        if cfg["oc_mode_enabled"]
        else spec["rated_standard_watts"]
    )
    safety = float(cfg["sustained_safety_margin_pct"]) / 100.0
    planning = round(rated * (1.0 - safety), 1)
    return {
        "rated_watts": rated,
        "effective_rated_watts": rated,
        "safety_margin_pct": cfg["sustained_safety_margin_pct"],
        "planning_budget_watts": planning,
        "oc_mode_enabled": cfg["oc_mode_enabled"],
        "brief_peak_watts": spec["brief_peak_watts"],
        "atx_revision": spec.get("atx_revision"),
        "efficiency": spec.get("efficiency"),
        "oc_mode_semantics": spec.get("oc_mode_semantics"),
    }


def projection_call_oc_headroom(oc_enabled: bool) -> dict[str, Any] | None:
    """Compose with R292 oc-headroom — feed an overlay snippet so the
    headroom calc reflects current OC-mode posture."""
    import tempfile
    bin_path = REPO_ROOT / "scripts" / "hardware" / "oc-headroom.py"
    if not bin_path.is_file():
        return None
    # Temp overlay flipping psu_oc_mode_multiplier per oc_enabled.
    body = (
        "psu_oc_mode_multiplier = 1.0\n"
        if not oc_enabled
        else "psu_oc_mode_multiplier = 1.0\n"
    )
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".toml", delete=False
    ) as fh:
        fh.write(body)
        overlay = fh.name
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), "status", "--config", overlay, "--json"],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    finally:
        try:
            Path(overlay).unlink()
        except OSError:
            pass
    if r.returncode not in (0, 1, 2):
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


# ── Renderers ───────────────────────────────────────────────────────
def render_state_human(s: dict, b: dict) -> str:
    spec = s["operator_psu"]
    lines = ["── R294 sovereign-os PSU OC-mode state (E1.M22) ──"]
    lines.append(f"  operator PSU:      {s['config']['operator_psu_model']}")
    lines.append(f"  OC-mode enabled:   {s['config']['oc_mode_enabled']}")
    if spec:
        lines.append(f"  rated (standard):  {spec['rated_standard_watts']} W")
        lines.append(f"  rated (OC-mode):   {spec['rated_oc_mode_watts']} W")
        lines.append(f"  brief peak:        {spec['brief_peak_watts']} W")
        lines.append(f"  efficiency:        {spec.get('efficiency')}")
        lines.append(f"  ATX revision:      {spec.get('atx_revision')}")
        if spec.get("oc_mode_semantics"):
            lines.append(f"  OC-mode semantics: {spec['oc_mode_semantics']}")
    else:
        lines.append("  spec:              (PSU model not in known_psus)")
    lines.append("")
    lines.append(f"  effective rated:   {b['effective_rated_watts']} W")
    lines.append(f"  planning budget:   {b['planning_budget_watts']} W "
                 f"({b['safety_margin_pct']}% safety margin)")
    return "\n".join(lines) + "\n"


def render_budget_human(b: dict) -> str:
    lines = ["── R294 PSU effective budget (E1.M22) ──"]
    lines.append(f"  rated:             {b['effective_rated_watts']} W")
    lines.append(f"  OC-mode enabled:   {b['oc_mode_enabled']}")
    lines.append(f"  planning budget:   {b['planning_budget_watts']} W "
                 f"(rated × (1 - {b['safety_margin_pct']}%))")
    lines.append(f"  brief peak:        {b.get('brief_peak_watts')} W")
    return "\n".join(lines) + "\n"


# ── Main ────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="psu-oc.py")
    sub = p.add_subparsers(dest="verb", required=True)
    for verb in ("state", "budget", "projection"):
        sp = sub.add_parser(verb)
        sp.add_argument("--config", type=Path)
        fmt = sp.add_mutually_exclusive_group()
        fmt.add_argument("--json", dest="fmt", action="store_const", const="json")
        fmt.add_argument("--human", dest="fmt", action="store_const", const="human")
        sp.set_defaults(fmt="json")

    args = p.parse_args(argv)
    s = load_state(args.config)
    b = effective_budget(s["operator_psu"], s["config"])

    if args.verb == "state":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "operator_psu_model": s["config"]["operator_psu_model"],
                "oc_mode_enabled": s["config"]["oc_mode_enabled"],
                "operator_psu_spec": s["operator_psu"],
                "effective_budget": b,
                "overlay": s["overlay"],
            }, indent=2))
        else:
            print(render_state_human(s, b), end="")
        return 0

    if args.verb == "budget":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "effective_budget": b,
                "overlay": s["overlay"],
            }, indent=2))
        else:
            print(render_budget_human(b), end="")
        return 0

    if args.verb == "projection":
        std = projection_call_oc_headroom(False)
        oc = projection_call_oc_headroom(True)
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "operator_psu_model": s["config"]["operator_psu_model"],
                "standard_mode": {
                    "verdict": (std or {}).get("verdict"),
                    "headroom_pct": (std or {}).get("headroom", {}).get("psu_headroom_pct"),
                },
                "oc_mode": {
                    "verdict": (oc or {}).get("verdict"),
                    "headroom_pct": (oc or {}).get("headroom", {}).get("psu_headroom_pct"),
                },
                "overlay": s["overlay"],
            }, indent=2))
        else:
            print(f"── R294 PSU OC-mode projection (E1.M22) ──")
            print(f"  standard mode: verdict={(std or {}).get('verdict')} "
                  f"headroom_pct={(std or {}).get('headroom', {}).get('psu_headroom_pct')}")
            print(f"  oc mode:       verdict={(oc or {}).get('verdict')} "
                  f"headroom_pct={(oc or {}).get('headroom', {}).get('psu_headroom_pct')}")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
