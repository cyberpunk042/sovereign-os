#!/usr/bin/env python3
"""scripts/hardware/heat-oc-autothrottle.py — R318 (E1.M38).

Operator-flagged via stop-hook (verbatim): "no heat-tied OC auto-
throttle (R296 combines but operator must apply manually)". Closes
E1.M38 — fills the gap by adding the apply-side with a triple-gate
preservation of the "NEVER auto-mutates without explicit operator
authorization" doctrine.

R296 thermal-oc-budget recommends a damped gpu_oc_multiplier. R304
memory-pressure damper recommends a damped multiplier under memory
pressure. R315 xmp-oc-room computes safe ceiling. This script
composes all three → picks the MINIMUM of the three damped values
(operator-key-conservative) + offers an `apply` verb that writes
the result to /etc/sovereign-os/oc-headroom.toml.

Triple-gate per operator's `SOVEREIGN_OS_CONFIRM_DESTROY=YES`
convention. The apply verb requires ALL THREE:
  1. `--apply` flag (CLI intent declaration)
  2. `--confirm-throttle` flag (explicit per-verb confirmation)
  3. `SOVEREIGN_OS_CONFIRM_DESTROY=YES` env var (host-level gate)

Without ALL THREE, apply is a DRY-RUN: prints the would-write TOML
to stdout + returns rc=0 without mutating anything.

CLI:
  heat-oc-autothrottle.py status     [--config P] [--json|--human]
                            current host damping recommendation
  heat-oc-autothrottle.py recommend  [--config P] [--json|--human]
                            same as status — read-only
  heat-oc-autothrottle.py apply      [--apply --confirm-throttle]
                                       [--config P] [--json|--human]
                            mutate /etc/sovereign-os/oc-headroom.toml
                            (or --target P) when triple-gate satisfied;
                            otherwise dry-run

Operator-overlay (R283/SDD-030): /etc/sovereign-os/heat-oc-
autothrottle.toml — knobs:
  oc_headroom_overlay_path  /etc/sovereign-os/oc-headroom.toml
  damping_floor             1.0   (don't damp below stock)

Exit codes:
  0  no damping needed (current = recommended) OR dry-run rendered
  1  damping recommended (read-only verbs report this)
  2  apply blocked (triple-gate missing) OR write error
"""
from __future__ import annotations

import argparse
import json
import os
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

try:
    import apply_audit  # type: ignore  # R327 audit-log helper
except Exception:  # pragma: no cover
    apply_audit = None


SCHEMA_VERSION = "1.0.0"
ROUND = "R318"
SDD_VECTOR = "E1.M38"


DEFAULTS = {
    "oc_headroom_overlay_path": "/etc/sovereign-os/oc-headroom.toml",
    "damping_floor": 1.0,        # never damp below stock
}


def _run_json(rel: str, args: list[str]) -> dict[str, Any] | None:
    p = REPO_ROOT / rel
    if not p.is_file():
        return None
    try:
        r = subprocess.run(
            [sys.executable, str(p), *args],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode not in (0, 1, 2):
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def probe_thermal_oc() -> dict[str, Any] | None:
    return _run_json("scripts/hardware/thermal-oc-budget.py",
                      ["status", "--json"])


def probe_mem_damper() -> dict[str, Any] | None:
    return _run_json("scripts/hardware/memory-pressure-oc-damper.py",
                      ["status", "--json"])


def probe_xmp_oc_room() -> dict[str, Any] | None:
    return _run_json("scripts/hardware/xmp-oc-room-advisor.py",
                      ["status", "--json"])


def probe_oc_headroom_current() -> float:
    """Read current gpu_oc_multiplier from R292 oc-headroom (best-effort)."""
    doc = _run_json("scripts/hardware/oc-headroom.py", ["status", "--json"])
    if doc is None:
        return 1.0
    v = (doc.get("headroom") or {}).get("gpu_oc_multiplier") \
        or (doc.get("config") or {}).get("gpu_oc_multiplier")
    try:
        return float(v) if v is not None else 1.0
    except (TypeError, ValueError):
        return 1.0


def derive_target(cfg: dict) -> dict[str, Any]:
    thermal = probe_thermal_oc()
    mem = probe_mem_damper()
    room = probe_xmp_oc_room()
    current = probe_oc_headroom_current()

    # Each probe's RECOMMENDED multiplier ceiling (None when unavailable).
    candidates: list[float] = []
    sources: list[dict[str, Any]] = []

    if thermal is not None:
        # thermal-oc-budget may suggest gpu_oc_multiplier in its
        # `recommended` block.
        v = (thermal.get("recommended") or {}).get("gpu_oc_multiplier")
        if isinstance(v, (int, float)):
            candidates.append(float(v))
            sources.append({"probe": "R296 thermal-oc-budget",
                             "recommendation": float(v)})

    if mem is not None:
        v = mem.get("recommended_oc_multiplier")
        if isinstance(v, (int, float)):
            candidates.append(float(v))
            sources.append({"probe": "R304 memory-pressure-damper",
                             "recommendation": float(v)})

    if room is not None:
        # xmp-oc-room budget verdict — if over-budget, target 1.0;
        # if tight, target 1.05; otherwise keep current.
        v = room.get("verdict")
        if v == "over-budget":
            candidates.append(1.0)
            sources.append({"probe": "R315 xmp-oc-room",
                             "recommendation": 1.0,
                             "reason": "over-budget"})
        elif v == "tight":
            candidates.append(min(current, 1.05))
            sources.append({"probe": "R315 xmp-oc-room",
                             "recommendation": min(current, 1.05),
                             "reason": "tight"})

    if not candidates:
        return {
            "current": current,
            "target": current,
            "damping_pct": 0.0,
            "sources": sources,
            "verdict": "no-recommendations",
            "rc": 0,
            "message": "No probe recommended a damped multiplier — "
                       "thermal + memory + room all healthy or "
                       "unavailable.",
        }

    floor = float(cfg["damping_floor"])
    target = max(floor, min(candidates))
    if abs(target - current) < 0.001:
        return {
            "current": current,
            "target": target,
            "damping_pct": 0.0,
            "sources": sources,
            "verdict": "no-damping-needed",
            "rc": 0,
            "message": (f"Current OC multiplier {current} already matches "
                        f"the min-recommended {target}; nothing to apply."),
        }
    if target >= current:
        return {
            "current": current,
            "target": target,
            "damping_pct": 0.0,
            "sources": sources,
            "verdict": "no-damping-needed",
            "rc": 0,
            "message": (f"Min-recommended {target} ≥ current {current}; "
                        f"no damping needed."),
        }
    damp_pct = (current - target) / current * 100.0
    return {
        "current": current,
        "target": target,
        "damping_pct": damp_pct,
        "sources": sources,
        "verdict": "damping-recommended",
        "rc": 1,
        "message": (f"Recommend damping from {current} → {target} "
                    f"(−{damp_pct:.1f}%). Min of {len(candidates)} "
                    f"probe recommendations."),
    }


def render_human(doc: dict) -> str:
    lines = [f"── R318 sovereign-os heat-tied OC auto-throttle (E1.M38) ──"]
    lines.append(f"  current gpu_oc_multiplier:     {doc['current']}")
    lines.append(f"  target gpu_oc_multiplier:      {doc['target']}")
    lines.append(f"  damping pct:                   {doc['damping_pct']:.1f}%")
    lines.append(f"  verdict:                       {doc['verdict']} "
                 f"(rc={doc['rc']})")
    lines.append(f"  message:                       {doc['message']}")
    if doc.get("sources"):
        lines.append("")
        lines.append("  sources:")
        for s in doc["sources"]:
            lines.append(f"    {s['probe']}  recommendation={s['recommendation']}"
                          + (f"  reason={s['reason']}" if s.get('reason') else ""))
    return "\n".join(lines) + "\n"


def apply_target(cfg: dict, target_path: Path,
                  result: dict, apply_flag: bool,
                  confirm_flag: bool,
                  env_gate: str | None) -> dict[str, Any]:
    """Apply the new target to the oc-headroom overlay file IF the
    triple-gate is satisfied; otherwise dry-run."""
    gates = {
        "--apply": bool(apply_flag),
        "--confirm-throttle": bool(confirm_flag),
        "SOVEREIGN_OS_CONFIRM_DESTROY=YES": env_gate == "YES",
    }
    triple_gate_ok = all(gates.values())
    target_val = result["target"]
    new_toml = f"# R318 heat-oc-autothrottle (E1.M38) — auto-written\n" \
                f"gpu_oc_multiplier = {target_val}\n"

    if result["verdict"] == "no-damping-needed":
        return {
            "gates": gates,
            "triple_gate_ok": triple_gate_ok,
            "would_write_path": str(target_path),
            "would_write_body": new_toml,
            "wrote": False,
            "reason": "no-damping-needed; nothing to apply",
            "rc": 0,
        }

    if not triple_gate_ok:
        return {
            "gates": gates,
            "triple_gate_ok": False,
            "would_write_path": str(target_path),
            "would_write_body": new_toml,
            "wrote": False,
            "reason": ("Triple-gate not satisfied; dry-run only. "
                       "All 3 must be present: --apply + "
                       "--confirm-throttle + "
                       "SOVEREIGN_OS_CONFIRM_DESTROY=YES."),
            "rc": 0,  # dry-run is rc=0 (no error)
        }

    # All gates satisfied → write.
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(new_toml, encoding="utf-8")
        return {
            "gates": gates,
            "triple_gate_ok": True,
            "would_write_path": str(target_path),
            "would_write_body": new_toml,
            "wrote": True,
            "reason": (f"Wrote gpu_oc_multiplier = {target_val} to "
                        f"{target_path}"),
            "rc": 0,
        }
    except OSError as e:
        return {
            "gates": gates,
            "triple_gate_ok": True,
            "would_write_path": str(target_path),
            "would_write_body": new_toml,
            "wrote": False,
            "reason": f"Write failed: {e}",
            "rc": 2,
        }


def load_state(overlay_path: Path | None) -> tuple[dict, dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    cfg = dict(DEFAULTS)
    if load_with_overlay is not None:
        loaded = load_with_overlay("heat-oc-autothrottle", DEFAULTS,
                                    explicit_path=overlay_path)
        cfg.update({k: v for k, v in loaded.items() if not k.startswith("_")})
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]
    return cfg, meta


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="heat-oc-autothrottle.py")
    sub = p.add_subparsers(dest="verb", required=True)
    for verb in ("status", "recommend"):
        sp = sub.add_parser(verb)
        sp.add_argument("--config", type=Path)
        fmt = sp.add_mutually_exclusive_group()
        fmt.add_argument("--json", dest="fmt", action="store_const", const="json")
        fmt.add_argument("--human", dest="fmt", action="store_const", const="human")
        sp.set_defaults(fmt="json")

    pa = sub.add_parser("apply")
    pa.add_argument("--apply", action="store_true",
                    help="gate 1/3 — declare apply intent")
    pa.add_argument("--confirm-throttle", action="store_true",
                    help="gate 2/3 — per-verb confirmation")
    pa.add_argument("--target", type=Path,
                    help="override overlay write target path "
                         "(default: oc_headroom_overlay_path from config)")
    pa.add_argument("--config", type=Path)
    fa = pa.add_mutually_exclusive_group()
    fa.add_argument("--json", dest="fmt", action="store_const", const="json")
    fa.add_argument("--human", dest="fmt", action="store_const", const="human")
    pa.set_defaults(fmt="json")

    args = p.parse_args(argv)
    cfg, meta = load_state(args.config)
    result = derive_target(cfg)

    if args.verb in ("status", "recommend"):
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                **result,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_human(result), end="")
        return result["rc"]

    # apply
    target_path = args.target if args.target \
        else Path(cfg["oc_headroom_overlay_path"])
    env_gate = os.environ.get("SOVEREIGN_OS_CONFIRM_DESTROY")
    apply_doc = apply_target(cfg, target_path, result,
                              args.apply, args.confirm_throttle, env_gate)
    # R327 (E9.M11): record this apply invocation to central audit
    # log (NEVER raises — audit failure cannot take down apply).
    if apply_audit is not None:
        apply_audit.record_apply(
            verb="heat-oc-throttle apply",
            round_origin="R318",
            gates_satisfied=bool(apply_doc.get("triple_gate_ok")),
            gates_detail=apply_doc.get("gates", {}),
            what_was_written={
                "gpu_oc_multiplier": result.get("target"),
                "previous_value": result.get("current"),
                "damping_pct": result.get("damping_pct"),
            },
            target_path=str(target_path),
            wrote=bool(apply_doc.get("wrote")),
            rc=int(apply_doc.get("rc", 0)),
        )
    if args.fmt == "json":
        print(json.dumps({
            "schema_version": SCHEMA_VERSION,
            "round": ROUND,
            "sdd_vector": SDD_VECTOR,
            "recommendation": result,
            "apply": apply_doc,
            "overlay": meta,
        }, indent=2))
    else:
        print(render_human(result), end="")
        print()
        print(f"  apply triple-gate:")
        for gate, ok in apply_doc["gates"].items():
            mark = "✓" if ok else "✗"
            print(f"    [{mark}] {gate}")
        print(f"  wrote:  {apply_doc['wrote']}")
        print(f"  reason: {apply_doc['reason']}")
    return apply_doc["rc"]


if __name__ == "__main__":
    sys.exit(main())
