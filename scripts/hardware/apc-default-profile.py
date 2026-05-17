#!/usr/bin/env python3
"""scripts/hardware/apc-default-profile.py — R314 (E1.M34).

Operator-named (§1b mandate row, verbatim): "PSU/APC integration with
the power management and the scheduled shutdown when battery reach a
certain point as one default profile. (schedule/planifest/graceful on
all levels, orderly)". Closes E1.M34.

R253 (E1.M6) ships graceful-shutdown timer + triple-gate. R302
(E1.M21) ships battery-ladder (multi-threshold escalation). R262
(E1.M8) ships drain manifest. R314 closes the umbrella: 3 curated
NAMED default profiles ready out-of-box that bundle ALL of the
above into operator-selectable bundles:

  conservative   safer/earlier shutdown — operator-pull when host
                 holds critical state that cannot replay
  balanced       sane defaults — operator-pull when host is mostly
                 stateless inference (default recommendation)
  aggressive     longer runtime on battery — operator-pull when
                 operator wants to drain battery further before
                 shutting down

Each profile bundles:
  - 4 battery_pct thresholds × per-threshold action
  - drain ordering (which services first)
  - notify dispatch severity per threshold
  - final shutdown commit point

CLI:
  apc-default-profile.py list   [--config P] [--json|--human]
  apc-default-profile.py show   <profile> [--config P] [--json|--human]
  apc-default-profile.py apply-hint <profile> [--config P] [--json|--human]
                                    emit operator-runnable commands
                                    that wire the profile into the
                                    R253 + R302 + R262 surfaces

Operator-overlay (R283/SDD-030): /etc/sovereign-os/apc-default-
profile.toml — sets active_profile + (optional) per-profile knob
override.

Exit codes:
  0  rendered
  1  unknown profile (show / apply-hint)
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
ROUND = "R314"
SDD_VECTOR = "E1.M34"


DEFAULTS = {
    "active_profile": "balanced",
}


DEFAULT_PROFILES: list[dict[str, Any]] = [
    {
        "name": "conservative",
        "axis": "lifecycle",
        "description": "Safer/earlier shutdown — operator-pull when host "
                       "holds critical state (training run, fine-tune "
                       "checkpoint) that cannot replay on next boot.",
        "thresholds": [
            {"battery_pct": 80, "severity": "informational",
             "action": "notify-only",
             "rationale": "Inform operator that AC is gone; nothing else."},
            {"battery_pct": 60, "severity": "attention",
             "action": "drain-inference-tier",
             "rationale": "Pre-drain inference workloads early — checkpoint "
                          "any active fine-tune; quiesce vllm/ollama."},
            {"battery_pct": 40, "severity": "attention",
             "action": "drain-observability-tier",
             "rationale": "Stop optional services (prometheus / grafana / "
                          "loki); keep core network + selfdef daemons."},
            {"battery_pct": 25, "severity": "critical",
             "action": "shutdown -h +2",
             "rationale": "Conservative shutdown commit with 2-min grace "
                          "window so operator can intervene if AC returns."},
        ],
        "operator_caveat": "Sacrifices ~30 min of battery runtime in "
                            "exchange for safer state preservation.",
    },
    {
        "name": "balanced",
        "axis": "lifecycle",
        "description": "Sane defaults — operator-pull when host is mostly "
                       "stateless inference. Operator's default "
                       "recommendation.",
        "thresholds": [
            {"battery_pct": 70, "severity": "informational",
             "action": "notify-only",
             "rationale": "AC-loss informational."},
            {"battery_pct": 45, "severity": "attention",
             "action": "drain-inference-tier",
             "rationale": "Quiesce vllm/ollama mid-battery."},
            {"battery_pct": 25, "severity": "attention",
             "action": "drain-observability-tier",
             "rationale": "Stop optional observability."},
            {"battery_pct": 10, "severity": "critical",
             "action": "shutdown -h +1",
             "rationale": "1-min grace shutdown commit."},
        ],
        "operator_caveat": "Balances battery runtime + safety. Most hosts "
                            "should use this.",
    },
    {
        "name": "aggressive",
        "axis": "lifecycle",
        "description": "Longer runtime on battery — operator-pull when "
                       "operator wants to drain battery further before "
                       "shutdown. Host loses more potential runtime to "
                       "graceful drain.",
        "thresholds": [
            {"battery_pct": 50, "severity": "informational",
             "action": "notify-only",
             "rationale": "Half-battery informational only."},
            {"battery_pct": 25, "severity": "attention",
             "action": "drain-inference-tier",
             "rationale": "Late drain — keeps inference up while battery "
                          "still has 25%."},
            {"battery_pct": 10, "severity": "critical",
             "action": "drain-observability-tier",
             "rationale": "Late observability drain at 10%."},
            {"battery_pct": 5, "severity": "critical",
             "action": "shutdown -h +0",
             "rationale": "Hard shutdown commit at 5% — no grace window."},
        ],
        "operator_caveat": "Aggressive — sacrifices safety window in "
                            "exchange for max runtime. NOT for hosts "
                            "holding critical state.",
    },
]


def load_state(overlay_path: Path | None) -> tuple[dict, list[dict], dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    cfg = dict(DEFAULTS)
    profiles = list(DEFAULT_PROFILES)
    if load_with_overlay is not None:
        loaded = load_with_overlay(
            "apc-default-profile",
            {**DEFAULTS, "profiles": []},
            explicit_path=overlay_path,
        )
        cfg["active_profile"] = loaded.get("active_profile", cfg["active_profile"])
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]
        if loaded.get("profiles"):
            profiles = list(loaded["profiles"])
    return cfg, profiles, meta


def resolve(profiles: list[dict], name: str) -> dict | None:
    for p in profiles:
        if isinstance(p, dict) and p.get("name") == name:
            return p
    return None


def render_list_human(profiles: list[dict], active: str) -> str:
    lines = [f"── R314 sovereign-os APC default profiles (E1.M34) ──"]
    lines.append(f"  profiles: {len(profiles)}    active: {active}")
    lines.append("")
    for p in profiles:
        marker = " (active)" if p.get("name") == active else ""
        lines.append(f"  {p.get('name')}{marker}")
        desc = (p.get("description") or "").strip()
        if desc:
            lines.append(f"    {desc[:90]}")
        lines.append(f"    thresholds: {len(p.get('thresholds', []))}")
        lines.append("")
    return "\n".join(lines)


def render_show_human(p: dict) -> str:
    lines = [f"── R314 APC default profile: {p.get('name')} (E1.M34) ──",
             f"  axis:       {p.get('axis')}", ""]
    if p.get("description"):
        lines.append(f"  description: {p['description']}")
        lines.append("")
    lines.append("  thresholds:")
    for t in p.get("thresholds", []):
        lines.append(f"    {t.get('battery_pct'):>3}%  {t.get('severity'):>15s}  → {t.get('action')}")
        if t.get("rationale"):
            lines.append(f"          {t['rationale']}")
    if p.get("operator_caveat"):
        lines.append("")
        lines.append(f"  caveat: {p['operator_caveat']}")
    return "\n".join(lines) + "\n"


def apply_hint(p: dict) -> dict[str, Any]:
    """Emit operator-runnable commands wiring this profile into
    R253/R302/R262 surfaces."""
    commands = []
    for t in p.get("thresholds", []):
        commands.append({
            "battery_pct": t.get("battery_pct"),
            "severity": t.get("severity"),
            "action": t.get("action"),
            "command": f"sovereign-osctl battery-ladder add-threshold "
                       f"--pct {t.get('battery_pct')} "
                       f"--severity {t.get('severity')} "
                       f"--action {t.get('action')!r}",
        })
    return {
        "profile": p.get("name"),
        "commands": commands,
        "note": "After running these, verify via "
                "`sovereign-osctl battery-ladder status` + restart "
                "the R253 graceful-shutdown timer.",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="apc-default-profile.py")
    sub = p.add_subparsers(dest="verb", required=True)

    pl = sub.add_parser("list")
    pl.add_argument("--config", type=Path)
    fl = pl.add_mutually_exclusive_group()
    fl.add_argument("--json", dest="fmt", action="store_const", const="json")
    fl.add_argument("--human", dest="fmt", action="store_const", const="human")
    pl.set_defaults(fmt="json")

    ps = sub.add_parser("show")
    ps.add_argument("profile")
    ps.add_argument("--config", type=Path)
    fs = ps.add_mutually_exclusive_group()
    fs.add_argument("--json", dest="fmt", action="store_const", const="json")
    fs.add_argument("--human", dest="fmt", action="store_const", const="human")
    ps.set_defaults(fmt="json")

    pah = sub.add_parser("apply-hint")
    pah.add_argument("profile")
    pah.add_argument("--config", type=Path)
    fah = pah.add_mutually_exclusive_group()
    fah.add_argument("--json", dest="fmt", action="store_const", const="json")
    fah.add_argument("--human", dest="fmt", action="store_const", const="human")
    pah.set_defaults(fmt="json")

    args = p.parse_args(argv)
    cfg, profiles, meta = load_state(args.config)

    if args.verb == "list":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "active_profile": cfg["active_profile"],
                "total_count": len(profiles),
                "profiles": profiles,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_list_human(profiles, cfg["active_profile"]), end="")
        return 0

    if args.verb == "show":
        target = resolve(profiles, args.profile)
        if target is None:
            print(json.dumps({
                "error": f"unknown profile: {args.profile}",
                "known": [p.get("name") for p in profiles if isinstance(p, dict)],
                "round": ROUND,
            }, indent=2), file=sys.stderr)
            return 1
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "profile": target,
                "is_active": target.get("name") == cfg["active_profile"],
                "overlay": meta,
            }, indent=2))
        else:
            print(render_show_human(target), end="")
        return 0

    if args.verb == "apply-hint":
        target = resolve(profiles, args.profile)
        if target is None:
            print(json.dumps({
                "error": f"unknown profile: {args.profile}",
                "known": [p.get("name") for p in profiles if isinstance(p, dict)],
                "round": ROUND,
            }, indent=2), file=sys.stderr)
            return 1
        hint = apply_hint(target)
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                **hint,
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R314 apply-hint: {hint['profile']} (E1.M34) ──")
            print()
            for c in hint["commands"]:
                print(f"  # battery {c['battery_pct']}%  → {c['action']}")
                print(f"  $ {c['command']}")
                print()
            print(f"  note: {hint['note']}")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
