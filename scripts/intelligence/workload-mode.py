#!/usr/bin/env python3
"""scripts/intelligence/workload-mode.py — R338 (E2.M27).

Single source of truth for the operator's current workload mode.
Other advisors (R337 fan-advisor today + future mode-aware
surfaces) read THIS as canonical instead of each carrying their
own active_mode default.

The 4 modes mirror R337 fan-advisor catalog (the originating
shipped instance):
  idle              quiet host; minimal noise + power
  inference-ready   pre-warmed for first-prompt thermal spike avoidance
  training          sustained AI training; trades noise for margin
  oc-burst          short benchmark/render; max airflow

CLI:
  workload-mode.py status               [--config P] [--json|--human]
                                          current declared mode
  workload-mode.py modes                [--config P] [--json|--human]
                                          list all 4 modes
  workload-mode.py affected-advisors    [--config P] [--json|--human]
                                          which advisors should read
                                          this mode (registry)
  workload-mode.py set <mode>           [--apply --confirm-mode-set]
                                          [--config P] [--target P]
                                          [--json|--human]
                                          mutate active mode under
                                          triple-gate via R328 safe_apply

Operator-overlay (R283/SDD-030):
/etc/sovereign-os/workload-mode.toml
  - active_mode             current operator mode (default idle)
  - mode_overlay_path       /etc/sovereign-os/workload-mode.toml
                             (the file `set` writes to)

Exit codes:
  0  ok (status / modes / affected-advisors / set-applied)
  1  unknown mode (set / status verdict mismatch)
  2  apply blocked (triple-gate missing) OR write failure
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
    from safe_apply import run_apply_safe  # type: ignore
except Exception:  # pragma: no cover
    run_apply_safe = None


SCHEMA_VERSION = "1.0.0"
ROUND = "R338"
SDD_VECTOR = "E2.M27"


# Mode catalog — mirrors R337's mode shapes minus the fan-specific
# duty% (those stay per-advisor; this round is about the SHARED
# mode name + operator-readable use case).
MODES: list[dict[str, Any]] = [
    {
        "mode": "idle",
        "description": "Host is idle; minimize noise + power; fans at "
                        "floor RPM; CPU governor = powersave; OC stock.",
        "operator_use_case": "Overnight / weekend / battery-conserving "
                              "operator-away periods.",
    },
    {
        "mode": "inference-ready",
        "description": "Inference workload primed to fire at any moment; "
                        "fans pre-warmed; CPU governor balanced; OC stock.",
        "operator_use_case": "Default daytime operator-at-keyboard mode. "
                              "Trades a few extra W for zero first-prompt "
                              "thermal spike.",
    },
    {
        "mode": "training",
        "description": "Sustained AI training (hours-long); high fan duty; "
                        "CPU governor = performance; OC profile pinned to "
                        "operator's confirmed safe ceiling.",
        "operator_use_case": "Operator queues a fine-tune / pretraining "
                              "job + walks away. Cooling + OC + power all "
                              "pre-arranged for sustained burn.",
    },
    {
        "mode": "oc-burst",
        "description": "Short OC burst (benchmark / one-off render); max "
                        "everything for transient peak; NOT for sustained "
                        "use.",
        "operator_use_case": "Bench run / single-shot render / "
                              "competition-mode demo.",
    },
]


# Registry of advisors that SHOULD read the active mode. Future
# rounds add entries here as they adopt mode-awareness.
AFFECTED_ADVISORS: list[dict[str, Any]] = [
    {
        "advisor": "R337 fan-advisor",
        "script": "scripts/hardware/fan-advisor.py",
        "verb": "sovereign-osctl fan-advisor status",
        "consumes_mode_via": ("R338 canonical "
                                "(/etc/sovereign-os/workload-mode.toml) "
                                "since R339; falls back to fan-advisor "
                                "own overlay when R338 unset"),
        "future_adoption": False,
        "adopted_in_round": "R339",
        "operator_caveat": "First R338 adopter — proves the cross-advisor "
                            "mode-linking pattern. R296/R304/R293/R307 "
                            "follow the same shape in future rounds.",
    },
    {
        "advisor": "R296 thermal-oc-budget",
        "script": "scripts/hardware/thermal-oc-budget.py",
        "verb": "sovereign-osctl thermal-oc-budget status",
        "consumes_mode_via": ("R338 canonical "
                                "(/etc/sovereign-os/workload-mode.toml) "
                                "since R341; modulates cpu_tjmax_*_margin "
                                "+ gpu_temp_* thresholds per "
                                "WORKLOAD_MODE_TO_MARGIN_DELTA map; "
                                "explicit overlay margins still win"),
        "future_adoption": False,
        "adopted_in_round": "R341",
        "operator_caveat": "Third R338 adopter — pattern proven across 3 "
                            "advisor shapes (curves/governor/margins). "
                            "Training mode tightens margins; critical "
                            "thresholds always preserved.",
    },
    {
        "advisor": "R304 memory-pressure-damper",
        "script": "scripts/hardware/memory-pressure-oc-damper.py",
        "verb": "sovereign-osctl memory-pressure-damper status",
        "consumes_mode_via": ("R338 canonical "
                                "(/etc/sovereign-os/workload-mode.toml) "
                                "since R342; modulates "
                                "memory_pressure_warn/crit_avg10 + "
                                "dampen_step_mild per WORKLOAD_MODE_TO_"
                                "DAMPER_DELTA map; explicit overlay knobs "
                                "still win"),
        "future_adoption": False,
        "adopted_in_round": "R342",
        "operator_caveat": "Fourth R338 adopter — completes the original "
                            "4-advisor adoption registry. Training mode "
                            "raises thresholds (sustained memory pressure "
                            "expected during fine-tune); idle/oc-burst "
                            "lower thresholds (early warning).",
    },
    {
        "advisor": "R315 xmp-oc-room-advisor",
        "script": "scripts/hardware/xmp-oc-room-advisor.py",
        "verb": "sovereign-osctl xmp-oc-room status",
        "consumes_mode_via": ("R338 canonical "
                                "(/etc/sovereign-os/workload-mode.toml) "
                                "since R344; modulates 4 runtime knobs "
                                "(xmp_enabled, cpu_oc_multiplier, "
                                "gpu_oc_notch, dual_gpu_active) per "
                                "WORKLOAD_MODE_TO_RUNTIME_KNOBS map"),
        "future_adoption": False,
        "adopted_in_round": "R344",
        "operator_caveat": "Fifth R338 adopter — first post-SDD-035 "
                            "adopter, validates the formal contract "
                            "works for adopters not in the original "
                            "4-set. Idle = single-GPU only; training = "
                            "dual-GPU + 10% CPU/GPU OC; oc-burst = max.",
    },
    {
        "advisor": "R293 power-profiles",
        "script": "scripts/hardware/power-profiles.py",
        "verb": "sovereign-osctl power-profiles status",
        "consumes_mode_via": "(not yet)",
        "future_adoption": True,
        "operator_caveat": "Future-round candidate: training mode → "
                            "performance governor; idle mode → powersave.",
    },
    {
        "advisor": "R307 cpu-hotswap",
        "script": "scripts/hardware/cpu-hotswap.py",
        "verb": "sovereign-osctl cpu-hotswap status",
        "consumes_mode_via": ("R338 canonical "
                                "(/etc/sovereign-os/workload-mode.toml) "
                                "since R340; derives pinned_mode + "
                                "pinned_epp via WORKLOAD_MODE_TO_GOV_EPP "
                                "map (idle→powersave; training→"
                                "performance; etc.); explicit "
                                "pinned_mode/pinned_epp overlay knobs "
                                "still win"),
        "future_adoption": False,
        "adopted_in_round": "R340",
        "operator_caveat": "Second R338 adopter — proves the R339 "
                            "pattern replicates. Per-mode governor + EPP "
                            "map operator-readable in `cpu-hotswap status "
                            "--json | jq .workload_mode_to_gov_epp`.",
    },
]


DEFAULTS = {
    "active_mode": "idle",
    "mode_overlay_path": "/etc/sovereign-os/workload-mode.toml",
}


def load_state(overlay_path: Path | None) -> tuple[dict, dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    cfg = dict(DEFAULTS)
    if load_with_overlay is not None:
        loaded = load_with_overlay("workload-mode", DEFAULTS,
                                    explicit_path=overlay_path)
        for k in DEFAULTS:
            if k in loaded:
                cfg[k] = loaded[k]
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]
    return cfg, meta


def resolve_mode(name: str) -> dict | None:
    for m in MODES:
        if m["mode"] == name:
            return m
    return None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="workload-mode.py")
    sub = p.add_subparsers(dest="cmd", required=True)

    for verb in ("status", "modes", "affected-advisors"):
        sp = sub.add_parser(verb)
        sp.add_argument("--config", type=Path)
        fmt = sp.add_mutually_exclusive_group()
        fmt.add_argument("--json", dest="fmt", action="store_const", const="json")
        fmt.add_argument("--human", dest="fmt", action="store_const", const="human")
        sp.set_defaults(fmt="json")

    pset = sub.add_parser("set")
    pset.add_argument("mode")
    pset.add_argument("--apply", action="store_true",
                      help="gate 1/3 — declare apply intent")
    pset.add_argument("--confirm-mode-set", action="store_true",
                      help="gate 2/3 — per-verb confirmation")
    pset.add_argument("--target", type=Path,
                      help="override overlay write path")
    pset.add_argument("--config", type=Path)
    fset = pset.add_mutually_exclusive_group()
    fset.add_argument("--json", dest="fmt", action="store_const", const="json")
    fset.add_argument("--human", dest="fmt", action="store_const", const="human")
    pset.set_defaults(fmt="json")

    args = p.parse_args(argv)
    cfg, meta = load_state(args.config)

    if args.cmd == "status":
        active = cfg["active_mode"]
        mode = resolve_mode(active)
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "active_mode": active,
                "mode_details": mode,
                "valid_mode": mode is not None,
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R338 workload-mode status (E2.M27) ──")
            print(f"  active mode: {active}")
            if mode:
                print(f"  description: {mode['description']}")
                print(f"  use case:    {mode['operator_use_case']}")
            else:
                print(f"  WARNING: '{active}' is not in the catalog "
                      f"(known: {[m['mode'] for m in MODES]})")
        return 0 if mode else 1

    if args.cmd == "modes":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "mode_count": len(MODES),
                "modes": MODES,
                "active_mode": cfg["active_mode"],
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R338 workload modes (E2.M27) ──")
            for m in MODES:
                marker = "→" if m["mode"] == cfg["active_mode"] else " "
                print(f"  {marker} {m['mode']:20s}  {m['description'][:60]}")
                print(f"        use case: {m['operator_use_case'][:80]}")
        return 0

    if args.cmd == "affected-advisors":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "advisor_count": len(AFFECTED_ADVISORS),
                "advisors": AFFECTED_ADVISORS,
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R338 affected advisors (E2.M27) ──")
            for a in AFFECTED_ADVISORS:
                mark = "✓" if not a["future_adoption"] else "·"
                print(f"  [{mark}] {a['advisor']:30s}  {a['consumes_mode_via']}")
                if a.get("operator_caveat"):
                    print(f"        {a['operator_caveat'][:80]}")
        return 0

    # set
    mode = resolve_mode(args.mode)
    if mode is None:
        print(json.dumps({
            "error": f"unknown mode: {args.mode}",
            "known_modes": [m["mode"] for m in MODES],
            "round": ROUND,
            "rc": 1,
        }, indent=2), file=sys.stderr)
        return 1

    if run_apply_safe is None:
        print(json.dumps({
            "error": "safe_apply helper unavailable (R328)",
            "round": ROUND,
            "rc": 2,
        }, indent=2), file=sys.stderr)
        return 2

    target_path = args.target if args.target \
        else Path(cfg["mode_overlay_path"])
    new_body = (f"# R338 workload-mode (E2.M27) — operator-set\n"
                 f"active_mode = \"{args.mode}\"\n")

    def write_fn():
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(new_body, encoding="utf-8")

    result = run_apply_safe(
        verb="workload-mode set",
        round_origin="R338",
        apply_flag=args.apply,
        confirm_flag=args.confirm_mode_set,
        confirm_flag_label="--confirm-mode-set",
        write_fn=write_fn,
        what_was_written={"active_mode": args.mode,
                          "previous_mode": cfg["active_mode"]},
        target_path=str(target_path),
    )

    if args.fmt == "json":
        print(json.dumps({
            "schema_version": SCHEMA_VERSION,
            "round": ROUND,
            "sdd_vector": SDD_VECTOR,
            "requested_mode": args.mode,
            "previous_mode": cfg["active_mode"],
            "target_path": str(target_path),
            **result,
        }, indent=2))
    else:
        print(f"── R338 workload-mode set (E2.M27) ──")
        print(f"  requested: {args.mode}")
        print(f"  previous:  {cfg['active_mode']}")
        print(f"  gates:")
        for g, v in result["gates"].items():
            mark = "✓" if v else "✗"
            print(f"    [{mark}] {g}")
        print(f"  wrote:  {result['wrote']}")
        if result.get("write_error"):
            print(f"  error:  {result['write_error']}")
    return result["rc"]


if __name__ == "__main__":
    sys.exit(main())
