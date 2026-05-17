#!/usr/bin/env python3
"""scripts/power/profiles.py — R293 (E1.M21).

Operator-named (§1b mandate row, verbatim): "the PSU/APC integration
with the power mangement and the scheduled shutdown when battery
reach a certain point as one default profile. (schedule/planifest/
graceful on all levels, orderly)". Closes E1.M21.

A registry of operator-pull power-management default profiles. Each
profile binds:
  - a trigger condition  (when does this profile fire?)
  - an escalation order  (which lifecycle verbs run, in which order?)
  - composed underlying scripts (R252 power-status, R253 battery
    shutdown guard, R258 wattage sampler, R262 drain manifest)

The verb is operator-pull: list / show / simulate / active. It NEVER
mutates — applying a profile is the operator running the composed
verbs in the order the profile names (the simulate verb prints them).

Operator-overlay (R283/SDD-030): /etc/sovereign-os/power-profiles.toml
(or SOVEREIGN_OS_OVERLAY_POWER_PROFILES, or --config <path>) for the
operator to add / replace / re-prioritize profiles. Lists REPLACE.

CLI:
  profiles.py list      [--config P] [--json|--human]
  profiles.py show      <profile> [--config P] [--json|--human]
  profiles.py simulate  <profile> [--config P] [--json|--human]
  profiles.py active    [--config P] [--json|--human]

Exit codes:
  0  rendered
  1  unknown profile
  2  usage
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
ROUND = "R293"
SDD_VECTOR = "E1.M21"


# ── Default profile registry (operator-overlay can replace) ────────
#
# Each profile is operator-readable: name, trigger, steps. Steps are
# resolved sovereign-osctl commands the operator runs in order. The
# simulate verb just prints them — apply is the operator's hand.
DEFAULT_PROFILES: list[dict[str, Any]] = [
    {
        "name": "battery-threshold-graceful-shutdown",
        "trigger": (
            "UPS battery charge ≤ shutdown_minutes_remaining threshold "
            "(operator-pinned in /etc/sovereign-os/power.toml; default "
            "10 min). The R253 graceful-shutdown timer fires this "
            "profile automatically when SOVEREIGN_OS_CONFIRM_DESTROY=YES "
            "is set on the systemd unit env."
        ),
        "default": True,
        "steps": [
            "sovereign-osctl power-status ups --json",
            "sovereign-osctl power-status advisories --json",
            "sovereign-osctl service-deps drain --json",
            "sovereign-osctl power-shutdown plan --json",
            "sovereign-osctl power-shutdown apply --confirm",
        ],
        "notes": (
            "Composes R252 (power-status) + R253 (battery shutdown "
            "guard) + R262 (drain manifest). The actual apply step "
            "requires --confirm AND SOVEREIGN_OS_CONFIRM_DESTROY=YES."
        ),
    },
    {
        "name": "scheduled-graceful-poweroff",
        "trigger": (
            "Operator-scheduled (cron / systemd timer) — typical use: "
            "nightly poweroff after training jobs complete."
        ),
        "default": False,
        "steps": [
            "sovereign-osctl service-deps drain --json",
            "sovereign-osctl power-shutdown plan --json",
            "sovereign-osctl power-shutdown apply --confirm",
        ],
        "notes": (
            "Same drain ordering as the battery profile but without "
            "the UPS probe — the operator owns the trigger schedule."
        ),
    },
    {
        "name": "ac-loss-graceful-suspend",
        "trigger": (
            "UPS reports OnBattery + battery_runtime_minutes ≥ "
            "shutdown_threshold + 5 min — there's time to suspend "
            "RAM-active workloads before a hard shutdown."
        ),
        "default": False,
        "steps": [
            "sovereign-osctl power-status ups --json",
            "sovereign-osctl service-deps drain --prefix slm- --json",
            "sovereign-osctl service-deps drain --prefix oracle- --json",
            "systemctl suspend",
        ],
        "notes": (
            "Drains inference workloads first (highest VRAM cost) "
            "before suspending. RAM-resident state preserved."
        ),
    },
    {
        "name": "thermal-budget-throttle",
        "trigger": (
            "CPU package temp ≥ tjmax − 10 °C OR any GPU temp ≥ "
            "max_temp − 10 °C — drop load BEFORE thermal throttling "
            "kicks in unconscious of operator intent."
        ),
        "default": False,
        "steps": [
            "sovereign-osctl hardware thermals --json",
            "sovereign-osctl gpu-mode --json",
            "sovereign-osctl gpu-remediate --dry-run --json",
        ],
        "notes": (
            "Read-only diagnosis profile. Operator decides whether "
            "to lower gpu power_limit / pause inference based on "
            "the thermal readout. R265 (heat integration) feeds this."
        ),
    },
    {
        "name": "psu-headroom-warn",
        "trigger": (
            "R292 oc-headroom reports verdict == headroom-tight or "
            "over-budget — operator needs to reduce GPU power_limit "
            "or OC profile before sustained 100% load."
        ),
        "default": False,
        "steps": [
            "sovereign-osctl oc-headroom advisory --json",
            "sovereign-osctl gpu-card-advisor --json",
            "sovereign-osctl power-status budget --json",
        ],
        "notes": (
            "Composes R292 (oc-headroom) + R271 (gpu-card-advisor) "
            "+ R252 (power-status). Read-only diagnosis."
        ),
    },
]


# ── Lookups + assembly ──────────────────────────────────────────────
def resolve_profile(profiles: list[dict], name: str) -> dict | None:
    for p in profiles:
        if isinstance(p, dict) and p.get("name") == name:
            return p
    return None


def load_profiles(overlay_path: Path | None) -> tuple[list[dict], dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    profiles = list(DEFAULT_PROFILES)
    if load_with_overlay is not None:
        cfg = load_with_overlay(
            "power-profiles",
            {"profiles": []},
            explicit_path=overlay_path,
        )
        meta["_source"] = cfg.get("_source", meta["_source"])
        meta["_overlay_keys"] = cfg.get("_overlay_keys", [])
        if cfg.get("_parse_error"):
            meta["_parse_error"] = cfg["_parse_error"]
        if cfg.get("profiles"):
            profiles = list(cfg["profiles"])
    return profiles, meta


def active_profile(profiles: list[dict]) -> dict | None:
    for p in profiles:
        if isinstance(p, dict) and p.get("default"):
            return p
    return None


# ── Renderers ───────────────────────────────────────────────────────
def render_list_human(profiles: list[dict], meta: dict) -> str:
    lines = ["── R293 sovereign-os power-management profiles (E1.M21) ──"]
    lines.append(f"  source:   {meta.get('_source')}")
    lines.append(f"  profiles: {len(profiles)}")
    act = active_profile(profiles)
    lines.append(f"  default:  {act.get('name') if act else '(none)'}")
    lines.append("")
    for p in profiles:
        if not isinstance(p, dict):
            continue
        marker = "DEFAULT" if p.get("default") else "       "
        lines.append(f"  [{marker}] {p.get('name', '<unnamed>')}")
        lines.append(f"            trigger: {p.get('trigger', '?')[:80]}")
    return "\n".join(lines) + "\n"


def render_show_human(p: dict) -> str:
    lines = [f"── R293 profile: {p.get('name')} (E1.M21) ──"]
    lines.append(f"  default:  {p.get('default', False)}")
    lines.append(f"  trigger:")
    for line in (p.get("trigger") or "").splitlines():
        lines.append(f"    {line}")
    lines.append(f"  steps:")
    for i, s in enumerate(p.get("steps") or [], 1):
        lines.append(f"    {i}. {s}")
    if p.get("notes"):
        lines.append(f"  notes:")
        for line in p["notes"].splitlines():
            lines.append(f"    {line}")
    return "\n".join(lines) + "\n"


def render_simulate_human(p: dict) -> str:
    lines = [f"── R293 SIMULATE: {p.get('name')} (E1.M21) ──"]
    lines.append(f"  Trigger: {p.get('trigger', '')[:120]}")
    lines.append(f"  When this profile fires, the operator runs (in order):")
    lines.append("")
    for i, s in enumerate(p.get("steps") or [], 1):
        lines.append(f"  {i}. {s}")
    lines.append("")
    lines.append(f"  NOTE: SIMULATE is print-only — the operator owns the apply.")
    return "\n".join(lines) + "\n"


# ── Main ────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="profiles.py")
    sub = p.add_subparsers(dest="verb", required=True)

    pl = sub.add_parser("list")
    pl.add_argument("--config", type=Path)
    fmt = pl.add_mutually_exclusive_group()
    fmt.add_argument("--json", dest="fmt", action="store_const", const="json")
    fmt.add_argument("--human", dest="fmt", action="store_const", const="human")
    pl.set_defaults(fmt="json")

    for verb in ("show", "simulate"):
        sp = sub.add_parser(verb)
        sp.add_argument("profile")
        sp.add_argument("--config", type=Path)
        sf = sp.add_mutually_exclusive_group()
        sf.add_argument("--json", dest="fmt", action="store_const", const="json")
        sf.add_argument("--human", dest="fmt", action="store_const", const="human")
        sp.set_defaults(fmt="json")

    pa = sub.add_parser("active")
    pa.add_argument("--config", type=Path)
    af = pa.add_mutually_exclusive_group()
    af.add_argument("--json", dest="fmt", action="store_const", const="json")
    af.add_argument("--human", dest="fmt", action="store_const", const="human")
    pa.set_defaults(fmt="json")

    args = p.parse_args(argv)
    profiles, meta = load_profiles(getattr(args, "config", None))

    if args.verb == "list":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "profile_count": len(profiles),
                "active_profile": (active_profile(profiles) or {}).get("name"),
                "profiles": profiles,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_list_human(profiles, meta), end="")
        return 0

    if args.verb == "active":
        act = active_profile(profiles)
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "active_profile": act,
                "overlay": meta,
            }, indent=2))
        else:
            if act is None:
                print("no default profile set (operator overlay: set default=true on one)")
            else:
                print(render_show_human(act), end="")
        return 0

    profile = resolve_profile(profiles, args.profile)
    if profile is None:
        print(json.dumps({
            "error": f"unknown profile: {args.profile}",
            "known": [p.get("name") for p in profiles if isinstance(p, dict)],
            "round": ROUND,
        }, indent=2), file=sys.stderr)
        return 1

    if args.verb == "show":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "profile": profile,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_show_human(profile), end="")
        return 0

    if args.verb == "simulate":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "profile_name": profile.get("name"),
                "trigger": profile.get("trigger"),
                "steps": profile.get("steps") or [],
                "simulate_mode": True,
                "note": "SIMULATE is print-only — operator owns the apply.",
            }, indent=2))
        else:
            print(render_simulate_human(profile), end="")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
