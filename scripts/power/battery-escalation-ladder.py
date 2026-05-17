#!/usr/bin/env python3
"""scripts/power/battery-escalation-ladder.py — R302 (E1.M27).

Operator-named (§1b mandate row, verbatim): "the PSU/APC integration
with the power mangement and the scheduled shutdown when battery
reach a certain point as one default profile. (schedule/planifest/
graceful on all levels, orderly)". Closes E1.M27.

R253 ships the single-threshold battery-shutdown guard. R293 ships
the power-profile REGISTRY. R302 fills the gap in between:
multi-threshold ESCALATION LADDER — a cascade of operator-pull
actions tied to battery_minutes_remaining bands.

Default ladder (each step has remaining_minutes_min, severity,
action, commands):

  remaining ≥ 30   → step "pre-alert"     severity=info       (notify only)
  20 ≤ rem < 30    → step "warn-watch"    severity=warn       (operator awareness)
  10 ≤ rem < 20    → step "drain-infer"   severity=action     (stop inference)
  5  ≤ rem < 10    → step "drain-all"     severity=urgent     (drain ALL services)
  rem < 5          → step "hard-shutdown" severity=critical   (forced poweroff)

Composed underlying scripts (operator-pull — script PRINTS the
commands, operator runs them OR a confirmed automation drives the
ladder):

  - sovereign-osctl power-status ups --json
  - sovereign-osctl service-deps drain [--prefix ...]
  - sovereign-osctl power-shutdown plan / apply --confirm
  - sovereign-osctl notify send --channel "operator"

CLI:
  battery-escalation-ladder.py list      [--config P] [--json|--human]
  battery-escalation-ladder.py show      <step> [--config P] [--json|--human]
  battery-escalation-ladder.py simulate  [--remaining-minutes N]
                                          [--config P] [--json|--human]
                            given a UPS state (probed OR --remaining
                            -minutes), emit the matching step + its
                            ordered commands.

Operator-overlay (R283/SDD-030): /etc/sovereign-os/battery-escalation-
ladder.toml. Lists REPLACE entirely.

Exit codes:
  0  rendered
  1  unknown step
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
ROUND = "R302"
SDD_VECTOR = "E1.M27"


# ── Default escalation ladder ───────────────────────────────────────
DEFAULT_LADDER: list[dict[str, Any]] = [
    {
        "step": "pre-alert",
        "remaining_minutes_min": 30,
        "remaining_minutes_max": 999999,
        "severity": "info",
        "summary": "AC loss detected; battery has ≥ 30 min runtime.",
        "commands": [
            "sovereign-osctl power-status ups --json",
            "sovereign-osctl notify send --severity info "
            "--message 'AC loss; battery has ≥ 30 min'",
        ],
        "operator_note": "Operator is alerted; no workloads paused yet. "
                         "Plenty of runway for AC recovery.",
    },
    {
        "step": "warn-watch",
        "remaining_minutes_min": 20,
        "remaining_minutes_max": 30,
        "severity": "warn",
        "summary": "Battery 20-30 min remaining; AC still down.",
        "commands": [
            "sovereign-osctl power-status ups --json",
            "sovereign-osctl power-status budget --json",
            "sovereign-osctl notify send --severity warn "
            "--message 'Battery 20-30 min; consider drain-on-AC-loss'",
        ],
        "operator_note": "Heightened awareness; if power doesn't return "
                         "in 5 min the next step fires.",
    },
    {
        "step": "drain-infer",
        "remaining_minutes_min": 10,
        "remaining_minutes_max": 20,
        "severity": "action",
        "summary": "Battery 10-20 min; pause inference workloads (slm-/oracle-).",
        "commands": [
            "sovereign-osctl service-deps drain --prefix slm- --json",
            "sovereign-osctl service-deps drain --prefix oracle- --json",
            "sovereign-osctl service-deps drain --prefix pulse- --json",
            "sovereign-osctl notify send --severity warn "
            "--message 'Battery 10-20 min — inference drained'",
        ],
        "operator_note": "GPU-hungry inference workloads release VRAM. "
                         "Other services keep running.",
    },
    {
        "step": "drain-all",
        "remaining_minutes_min": 5,
        "remaining_minutes_max": 10,
        "severity": "urgent",
        "summary": "Battery 5-10 min; drain ALL services in dependency order.",
        "commands": [
            "sovereign-osctl service-deps drain --json",
            "sovereign-osctl power-shutdown plan --json",
            "sovereign-osctl notify send --severity critical "
            "--message 'Battery 5-10 min — drain ALL; shutdown imminent'",
        ],
        "operator_note": "Last graceful drain. Operator can still intervene "
                         "if AC recovers within minutes.",
    },
    {
        "step": "hard-shutdown",
        "remaining_minutes_min": 0,
        "remaining_minutes_max": 5,
        "severity": "critical",
        "summary": "Battery < 5 min; forced graceful shutdown.",
        "commands": [
            "sovereign-osctl power-shutdown apply --confirm",
        ],
        "operator_note": "Last-ditch graceful shutdown. R253 timer drives "
                         "this when SOVEREIGN_OS_CONFIRM_DESTROY=YES is on "
                         "the systemd unit env.",
    },
]


# ── Probes (read-only) ──────────────────────────────────────────────
def probe_ups_remaining_minutes() -> tuple[int | None, str | None]:
    """Probe `sovereign-osctl power-status ups --json` for the
    current battery_runtime_minutes field. Returns (minutes, error)."""
    bin_path = REPO_ROOT / "scripts" / "hardware" / "power-status.py"
    if not bin_path.is_file():
        return None, f"power-status.py not at {bin_path}"
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), "ups", "--json"],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, f"power-status invocation: {e}"
    if r.returncode not in (0, 1):
        return None, f"power-status rc={r.returncode}"
    try:
        doc = json.loads(r.stdout)
    except json.JSONDecodeError as e:
        return None, f"json parse: {e}"
    # Try several possible field names — operator's apcupsd output varies.
    for key in ("battery_runtime_minutes", "runtime_minutes",
                "battery_minutes_remaining", "minutes_remaining"):
        if key in doc and isinstance(doc[key], (int, float)):
            return int(doc[key]), None
    return None, "power-status ups JSON has no runtime-minutes field"


# ── Ladder resolution ───────────────────────────────────────────────
def resolve_step(ladder: list[dict], remaining_minutes: int) -> dict | None:
    for step in ladder:
        if not isinstance(step, dict):
            continue
        lo = step.get("remaining_minutes_min", 0)
        hi = step.get("remaining_minutes_max", 999999)
        if lo <= remaining_minutes < hi:
            return step
    return None


def step_by_name(ladder: list[dict], name: str) -> dict | None:
    for step in ladder:
        if isinstance(step, dict) and step.get("step") == name:
            return step
    return None


def load_ladder(overlay_path: Path | None) -> tuple[list[dict], dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    ladder = list(DEFAULT_LADDER)
    if load_with_overlay is not None:
        cfg = load_with_overlay(
            "battery-escalation-ladder",
            {"steps": []},
            explicit_path=overlay_path,
        )
        meta["_source"] = cfg.get("_source", meta["_source"])
        meta["_overlay_keys"] = cfg.get("_overlay_keys", [])
        if cfg.get("_parse_error"):
            meta["_parse_error"] = cfg["_parse_error"]
        if cfg.get("steps"):
            ladder = list(cfg["steps"])
    return ladder, meta


# ── Renderers ───────────────────────────────────────────────────────
def render_list_human(ladder: list[dict], meta: dict) -> str:
    lines = ["── R302 sovereign-os UPS battery escalation ladder (E1.M27) ──"]
    lines.append(f"  source: {meta.get('_source')}")
    lines.append(f"  steps:  {len(ladder)}")
    lines.append("")
    for step in ladder:
        if not isinstance(step, dict):
            continue
        lo = step.get("remaining_minutes_min", "?")
        hi = step.get("remaining_minutes_max", "?")
        sev = step.get("severity", "?")
        rng = f"[{lo:>3}m … {hi:>3}m)" if hi != 999999 else f"[{lo:>3}m+      )"
        lines.append(f"  • {step.get('step', '<unnamed>'):16s} "
                     f"{rng}  severity={sev}")
        if step.get("summary"):
            lines.append(f"      {step['summary']}")
    return "\n".join(lines) + "\n"


def render_step_human(step: dict) -> str:
    lines = [f"── R302 step: {step.get('step')} (E1.M27) ──"]
    lo = step.get("remaining_minutes_min", "?")
    hi = step.get("remaining_minutes_max", "?")
    lines.append(f"  remaining range: [{lo} min, {hi} min)")
    lines.append(f"  severity:        {step.get('severity')}")
    lines.append(f"  summary:         {step.get('summary')}")
    lines.append(f"  commands:")
    for c in (step.get("commands") or []):
        lines.append(f"    $ {c}")
    if step.get("operator_note"):
        lines.append(f"  operator note:   {step['operator_note']}")
    return "\n".join(lines) + "\n"


# ── Main ────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="battery-escalation-ladder.py")
    sub = p.add_subparsers(dest="verb", required=True)

    pl = sub.add_parser("list")
    pl.add_argument("--config", type=Path)
    fl = pl.add_mutually_exclusive_group()
    fl.add_argument("--json", dest="fmt", action="store_const", const="json")
    fl.add_argument("--human", dest="fmt", action="store_const", const="human")
    pl.set_defaults(fmt="json")

    ps = sub.add_parser("show")
    ps.add_argument("step")
    ps.add_argument("--config", type=Path)
    fs = ps.add_mutually_exclusive_group()
    fs.add_argument("--json", dest="fmt", action="store_const", const="json")
    fs.add_argument("--human", dest="fmt", action="store_const", const="human")
    ps.set_defaults(fmt="json")

    psim = sub.add_parser("simulate")
    psim.add_argument("--remaining-minutes", type=int,
                       help="override probed UPS state with explicit value")
    psim.add_argument("--config", type=Path)
    fsim = psim.add_mutually_exclusive_group()
    fsim.add_argument("--json", dest="fmt", action="store_const", const="json")
    fsim.add_argument("--human", dest="fmt", action="store_const", const="human")
    psim.set_defaults(fmt="json")

    args = p.parse_args(argv)
    ladder, meta = load_ladder(args.config)

    if args.verb == "list":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "step_count": len(ladder),
                "steps": ladder,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_list_human(ladder, meta), end="")
        return 0

    if args.verb == "show":
        step = step_by_name(ladder, args.step)
        if step is None:
            print(json.dumps({
                "error": f"unknown step: {args.step}",
                "known": [s.get("step") for s in ladder if isinstance(s, dict)],
                "round": ROUND,
            }, indent=2), file=sys.stderr)
            return 1
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "step": step,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_step_human(step), end="")
        return 0

    if args.verb == "simulate":
        if args.remaining_minutes is not None:
            remaining = args.remaining_minutes
            source = "operator-override"
        else:
            remaining, err = probe_ups_remaining_minutes()
            source = "power-status ups" if remaining is not None else f"unavailable ({err})"
        step = resolve_step(ladder, remaining) if remaining is not None else None
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "remaining_minutes": remaining,
                "source": source,
                "resolved_step": step,
                "simulate_mode": True,
                "note": "SIMULATE prints — operator owns the apply.",
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R302 SIMULATE escalation (E1.M27) ──")
            print(f"  battery remaining: {remaining} min  (source: {source})")
            if step is None:
                print(f"  resolved step:     (none — outside any ladder range)")
            else:
                print(f"  resolved step:     {step.get('step')}  "
                      f"severity={step.get('severity')}")
                print(f"  steps to run (operator copy + paste):")
                for c in step.get("commands") or []:
                    print(f"    $ {c}")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
