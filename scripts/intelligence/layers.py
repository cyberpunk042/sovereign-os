#!/usr/bin/env python3
"""scripts/intelligence/layers.py — R382 (E10.M26).

Operator-verbatim 'guide into' layer enumeration. From the 2026-05-17
hook drop opening sentence:

  "Its not only going to be an AI and an AI training station with an
  AI able system but only a guide into the experiece, into the field,
  into the kernel, into the hardware, into the OS, into the modules,
  into the features, the services, the configurations, the
  personalisations, the customizations."

The operator named 11 distinct layers. R349 guide.py covers some but
not all of them as topics. R382 catalogues all 11 operator-named
layers + maps each to the discoverable verb(s) that surface it.

CLI:
  layers.py list                  [--config P] [--json|--human]
                                   render the 11 operator-named layers
                                   with verbatim spelling preserved
                                   (operator typo "experiece" intact)
  layers.py show <layer>           [--config P] [--json|--human]
                                   drill into one layer with its
                                   implementing verbs + cross-refs
  layers.py search <substring>     [--config P] [--json|--human]

Operator-overlay (R283/SDD-030): /etc/sovereign-os/layers.toml
  - extend layers per operator's future hook drop additions

Exit codes:
  0  rendered
  1  unknown layer (show verb) / no matches (search verb)
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
ROUND = "R382"
SDD_VECTOR = "E10.M26"


# Operator-verbatim 11-layer enumeration from the 2026-05-17 hook drop.
# Spelling preserved EXACTLY including operator's typo "experiece"
# (operator typo for "experience" — per SDD-037 typo-preservation rule).
DEFAULT_LAYERS: list[dict[str, Any]] = [
    {
        "layer": "experiece",
        "layer_verbatim": "into the experiece",
        "operator_note": ("Operator typo for 'experience' — preserved "
                           "verbatim per SDD-037 typo-preservation rule. "
                           "The META layer: the operator's lived-in "
                           "experience of using sovereign-os."),
        "implementing_verbs": [
            "sovereign-osctl guide topics",
            "sovereign-osctl morning-brief rollup",
            "sovereign-osctl next-action top",
            "sovereign-osctl quarterly-review snapshot",
        ],
        "guide_topic_match": None,
        "spec_ref": "hook drop 2026-05-17 (operator-verbatim opening)",
    },
    {
        "layer": "field",
        "layer_verbatim": "into the field",
        "operator_note": ("The operational FIELD — runtime state of the "
                           "live workstation. Probed via observability "
                           "verbs."),
        "implementing_verbs": [
            "sovereign-osctl health",
            "sovereign-osctl insights",
            "sovereign-osctl events",
            "sovereign-osctl autohealth tick",
        ],
        "guide_topic_match": None,
        "spec_ref": "hook drop 2026-05-17",
    },
    {
        "layer": "kernel",
        "layer_verbatim": "into the kernel",
        "operator_note": ("The Linux kernel — boot-time cmdline + "
                           "compile-time CONFIG_* + runtime sysctl."),
        "implementing_verbs": [
            "sovereign-osctl kernel-cmdline",
            "sovereign-osctl guide show kernel",
            "sovereign-osctl architecture-qa show C-24",
            "sovereign-osctl architecture-qa show C-25",
        ],
        "guide_topic_match": "kernel",
        "spec_ref": "hook drop 2026-05-17",
    },
    {
        "layer": "hardware",
        "layer_verbatim": "into the hardware",
        "operator_note": ("Physical SAIN-01 inventory + per-component "
                           "advisors + heat / OC / wattage tracking."),
        "implementing_verbs": [
            "sovereign-osctl inventory",
            "sovereign-osctl guide show hardware",
            "sovereign-osctl ccd-pinning show",
            "sovereign-osctl architecture-qa show C-16",
            "sovereign-osctl bios-directives",
        ],
        "guide_topic_match": "hardware",
        "spec_ref": "hook drop 2026-05-17",
    },
    {
        "layer": "OS",
        "layer_verbatim": "into the OS",
        "operator_note": ("Sovereign OS itself — the Debian-13 base + "
                           "operator customizations. Vision + charter + "
                           "Debian-as-Ark framing."),
        "implementing_verbs": [
            "sovereign-osctl architecture-qa show C-22",
            "sovereign-osctl bootstrap phases",
            "sovereign-osctl bootstrap verify",
            "sovereign-osctl whitelabel render",
        ],
        "guide_topic_match": None,
        "spec_ref": "hook drop 2026-05-17",
    },
    {
        "layer": "modules",
        "layer_verbatim": "into the modules",
        "operator_note": ("Selfdef modules + sovereign-os runtime "
                           "modules + feature catalogs."),
        "implementing_verbs": [
            "sovereign-osctl module-state list",
            "sovereign-osctl guide show selfdef",
            "sovereign-osctl install paths",
        ],
        "guide_topic_match": "selfdef",
        "spec_ref": "hook drop 2026-05-17",
    },
    {
        "layer": "features",
        "layer_verbatim": "into the features",
        "operator_note": ("Per-module operator-pull features + "
                           "advanced features + enable/disable knobs."),
        "implementing_verbs": [
            "sovereign-osctl module-state show <module>",
            "sovereign-osctl coverage show <A-NN>",
            "sovereign-osctl architecture-qa search <topic>",
        ],
        "guide_topic_match": None,
        "spec_ref": "hook drop 2026-05-17",
    },
    {
        "layer": "services",
        "layer_verbatim": "the services",
        "operator_note": ("systemd service units + service dependency "
                           "graph + drain ordering."),
        "implementing_verbs": [
            "sovereign-osctl service-deps",
            "sovereign-osctl perimeter",
            "sovereign-osctl alerts",
        ],
        "guide_topic_match": None,
        "spec_ref": "hook drop 2026-05-17",
    },
    {
        "layer": "configurations",
        "layer_verbatim": "the configurations",
        "operator_note": ("Operator-overlay TOML configs at "
                           "/etc/sovereign-os/*.toml + drift detection."),
        "implementing_verbs": [
            "sovereign-osctl overlay-drift list",
            "sovereign-osctl install-mode",
            "sovereign-osctl state-fabric layout",
            "sovereign-osctl env",
        ],
        "guide_topic_match": None,
        "spec_ref": "hook drop 2026-05-17",
    },
    {
        "layer": "personalisations",
        "layer_verbatim": "the personalisations",
        "operator_note": ("Whitelabel surface — boot splash + GRUB "
                           "theme + motd + Plymouth theme + os-release. "
                           "Operator brand identity layer."),
        "implementing_verbs": [
            "sovereign-osctl whitelabel render",
            "sovereign-osctl architecture-qa show C-18",
        ],
        "guide_topic_match": None,
        "spec_ref": "hook drop 2026-05-17",
    },
    {
        "layer": "customizations",
        "layer_verbatim": "the customizations",
        "operator_note": ("Profiles — sain-01 / old-workstation / "
                           "minimal / developer / headless + runtime "
                           "profiles (Ultra-Sovereign / High-Concurrency / "
                           "Deep-Context)."),
        "implementing_verbs": [
            "sovereign-osctl profile",
            "sovereign-osctl trinity profile",
            "sovereign-osctl architecture-qa show C-13",
            "sovereign-osctl architecture-qa show C-26",
            "sovereign-osctl architecture-qa show C-27",
        ],
        "guide_topic_match": None,
        "spec_ref": "hook drop 2026-05-17",
    },
]


# ── Loading + filtering ───────────────────────────────────────────
def load_state(overlay_path: Path | None) -> tuple[list[dict], dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    layers = list(DEFAULT_LAYERS)
    if load_with_overlay is not None:
        loaded = load_with_overlay(
            "layers", {"layers": []}, explicit_path=overlay_path,
        )
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]
        if loaded.get("layers"):
            layers = list(loaded["layers"])
    return layers, meta


def resolve_layer(layers: list[dict], name: str) -> dict | None:
    for layer in layers:
        if isinstance(layer, dict) and layer.get("layer") == name:
            return layer
    return None


def search_layers(layers: list[dict], needle: str) -> list[dict]:
    n = needle.lower()
    return [layer for layer in layers if isinstance(layer, dict) and (
        n in (layer.get("layer") or "").lower()
        or n in (layer.get("layer_verbatim") or "").lower()
        or n in (layer.get("operator_note") or "").lower()
        or any(n in v.lower() for v in (layer.get("implementing_verbs") or []))
    )]


# ── Renderers ──────────────────────────────────────────────────────
def render_list_human(layers: list[dict]) -> str:
    lines = [f"── R382 operator-named layers ({len(layers)} from hook drop verbatim) ──"]
    lines.append("")
    lines.append("  Operator's verbatim 'guide into' enumeration "
                  "(2026-05-17 hook drop):")
    lines.append("    \"Its not only going to be an AI and an AI training")
    lines.append("     station with an AI able system but only a guide")
    lines.append("     into the experiece, into the field, into the")
    lines.append("     kernel, into the hardware, into the OS, into the")
    lines.append("     modules, into the features, the services, the")
    lines.append("     configurations, the personalisations, the")
    lines.append("     customizations.\"")
    lines.append("")
    for layer in layers:
        verbs = layer.get("implementing_verbs") or []
        topic = layer.get("guide_topic_match")
        topic_str = f"  [guide topic: {topic}]" if topic else ""
        lines.append(f"  {layer.get('layer'):<18}  "
                      f"{layer.get('layer_verbatim', ''):<30}{topic_str}")
        lines.append(f"      verbs: {len(verbs)} (1st: {verbs[0] if verbs else '?'})")
    return "\n".join(lines) + "\n"


def render_show_human(layer: dict) -> str:
    lines = [f"── R382 layer: {layer.get('layer')} ──"]
    lines.append("")
    lines.append(f"  operator-verbatim: \"{layer.get('layer_verbatim')}\"")
    lines.append(f"  guide topic match: {layer.get('guide_topic_match', '(none)')}")
    lines.append(f"  spec ref:          {layer.get('spec_ref')}")
    lines.append("")
    lines.append("  OPERATOR NOTE:")
    body = layer.get("operator_note") or ""
    cur = "    "
    for word in body.split():
        if len(cur) + len(word) > 76 and cur.strip():
            lines.append(cur.rstrip())
            cur = "    "
        cur += word + " "
    if cur.strip():
        lines.append(cur.rstrip())
    lines.append("")
    lines.append("  Implementing verbs (drill into this layer):")
    for v in (layer.get("implementing_verbs") or []):
        lines.append(f"    $ {v}")
    return "\n".join(lines) + "\n"


# ── Main ──────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="layers.py")
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("list")
    pl.add_argument("--config", type=Path)
    plg = pl.add_mutually_exclusive_group()
    plg.add_argument("--json", dest="fmt", action="store_const", const="json")
    plg.add_argument("--human", dest="fmt", action="store_const", const="human")
    pl.set_defaults(fmt="json")

    ps = sub.add_parser("show")
    ps.add_argument("layer_name")
    ps.add_argument("--config", type=Path)
    psg = ps.add_mutually_exclusive_group()
    psg.add_argument("--json", dest="fmt", action="store_const", const="json")
    psg.add_argument("--human", dest="fmt", action="store_const", const="human")
    ps.set_defaults(fmt="json")

    psr = sub.add_parser("search")
    psr.add_argument("needle")
    psr.add_argument("--config", type=Path)
    psrg = psr.add_mutually_exclusive_group()
    psrg.add_argument("--json", dest="fmt", action="store_const", const="json")
    psrg.add_argument("--human", dest="fmt", action="store_const", const="human")
    psr.set_defaults(fmt="json")

    args = p.parse_args(argv)
    layers, meta = load_state(getattr(args, "config", None))

    if args.cmd == "list":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "layer_count": len(layers),
                "layers": layers,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_list_human(layers), end="")
        return 0

    if args.cmd == "show":
        layer = resolve_layer(layers, args.layer_name)
        if layer is None:
            print(json.dumps({
                "error": f"unknown layer: {args.layer_name}",
                "known_layers": [l.get("layer") for l in layers if isinstance(l, dict)],
                "round": ROUND,
            }, indent=2), file=sys.stderr)
            return 1
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "layer_detail": layer,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_show_human(layer), end="")
        return 0

    if args.cmd == "search":
        matches = search_layers(layers, args.needle)
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "needle": args.needle,
                "match_count": len(matches),
                "matched_layers": matches,
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R382 layers search: '{args.needle}' ──")
            for layer in matches:
                print(f"  {layer.get('layer'):<18}  "
                       f"{layer.get('layer_verbatim', '')[:50]}")
        return 0 if matches else 1

    return 2


if __name__ == "__main__":
    sys.exit(main())
