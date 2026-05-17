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


def load_profiles(overlay_path: Path | None) -> tuple[list[dict], dict, dict]:
    """Returns (profiles, meta, cfg).
    cfg surfaces the R345-added knobs (follow_workload_mode_coordinator,
    workload_mode_overlay_path) so callers can read them.
    """
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    profiles = list(DEFAULT_PROFILES)
    # R345 (E2.M33, SDD-035): R338 workload-mode adoption knobs.
    cfg = {
        "follow_workload_mode_coordinator": True,
        "workload_mode_overlay_path": "/etc/sovereign-os/workload-mode.toml",
    }
    if load_with_overlay is not None:
        loaded = load_with_overlay(
            "power-profiles",
            {"profiles": [], **cfg},
            explicit_path=overlay_path,
        )
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]
        if loaded.get("profiles"):
            profiles = list(loaded["profiles"])
        for k in cfg:
            if k in loaded:
                cfg[k] = loaded[k]
    return profiles, meta, cfg


# R345 (E2.M33, SDD-035): workload-mode → recommended power-profile.
# Each entry maps a R338 canonical mode to which named profile R293
# should advise as active. Operator-readable rationale per mode.
WORKLOAD_MODE_TO_PROFILE_NAME: dict[str, dict[str, Any]] = {
    "idle": {
        "profile_name": "ac-loss-graceful-suspend",
        "rationale": ("Idle: operator away; suspend-on-AC-loss "
                       "preserves session state while drawing zero "
                       "wall-power between events."),
    },
    "inference-ready": {
        "profile_name": "battery-threshold-graceful-shutdown",
        "rationale": ("Inference-ready: default operator posture; "
                       "battery-threshold graceful shutdown is the "
                       "sane standard for daytime keyboard use."),
    },
    "training": {
        "profile_name": "thermal-budget-throttle",
        "rationale": ("Training: sustained workload risks thermal "
                       "incidents; thermal-budget-throttle profile "
                       "pre-arms automatic throttle when R296 verdict "
                       "crosses threshold."),
    },
    "oc-burst": {
        "profile_name": "psu-headroom-warn",
        "rationale": ("OC-burst: transient peak likely to approach "
                       "PSU rated W; psu-headroom-warn alerts operator "
                       "the moment R252 power-status reports headroom "
                       "deficit."),
    },
}


def _read_canonical_mode(cfg: dict) -> tuple[str | None, str]:
    """R345 (E2.M33): SDD-035 contract — same shape as R339-R344.
    NEVER raises."""
    if not cfg.get("follow_workload_mode_coordinator", True):
        return None, "power-profiles-overlay"
    path = Path(cfg.get("workload_mode_overlay_path",
                          "/etc/sovereign-os/workload-mode.toml"))
    if not path.is_file():
        return None, "power-profiles-overlay"
    try:
        body = path.read_text(encoding="utf-8")
    except OSError:
        return None, "power-profiles-overlay"
    import re
    m = re.search(r'^\s*active_mode\s*=\s*"([^"]+)"\s*$', body, re.M)
    if m:
        return m.group(1), "R338-canonical"
    return None, "power-profiles-overlay"


def _resolve_workload_recommended_profile(
    cfg: dict, profiles: list[dict],
) -> tuple[dict | None, str | None, str]:
    """Resolve which profile R338 canonical mode recommends.
    Returns (profile_dict_or_None, canonical_mode_or_None, source)."""
    canonical, source = _read_canonical_mode(cfg)
    if canonical is None:
        return None, None, source
    spec = WORKLOAD_MODE_TO_PROFILE_NAME.get(canonical)
    if spec is None:
        return None, canonical, f"{source}-unknown-mode"
    name = spec["profile_name"]
    target = resolve_profile(profiles, name)
    return target, canonical, source


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
    profiles, meta, cfg = load_profiles(getattr(args, "config", None))

    # R345 (E2.M33, SDD-035): R338 workload-mode adoption fields.
    wm_target, wm_canonical, wm_source = _resolve_workload_recommended_profile(
        cfg, profiles,
    )
    wm_fields = {
        "workload_mode_canonical": wm_canonical,
        "workload_mode_source": wm_source,
        "workload_mode_recommended_profile": (wm_target or {}).get("name"),
        "workload_mode_to_profile_name": WORKLOAD_MODE_TO_PROFILE_NAME,
    }

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
                **wm_fields,
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
                **wm_fields,
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
                **wm_fields,
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
                **wm_fields,
            }, indent=2))
        else:
            print(render_simulate_human(profile), end="")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
