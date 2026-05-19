#!/usr/bin/env python3
"""scripts/intelligence/workload-knobs.py — R555 (E11.M18).

Operator §1g (verbatim, sacrosanct):
  "Hotswap mode for CPU/GPU mode dedicated to AI inference Mode and
   dedicated to gpu rendering mode and dedicated to working office
   mode, etc."

R555 is the umbrella that maps the R338 canonical workload-mode
(idle / inference-ready / training / oc-burst) into an ATOMIC bundle
of the four inference-latency primitives shipped in R551-R554:

  R551  nvidia-mps        concurrent non-MIG GPU sharing
  R552  hugepages-sizer   static hugepage reservation
  R553  thp-mode          opportunistic THP enabled/defrag policy
  R554  irq-affinity      housekeeping CPU set for hardware IRQs

Before R555 the four primitives were operator-callable one-by-one.
That is the right read-mostly surface for inspection — but flipping
between workload modes manually is four commands, four chances to
forget one, and zero atomicity. R555 wires the bundle: one verb,
one preset per canonical mode, every knob moves together.

Verbs:
  show / status      — print active mode + the bundle it maps to.
  plan <mode>        — emit the bundle for a given mode (read-only).
  list-bundles       — emit all 4 mode→bundle mappings.
  apply <mode>       — fan out to each underlying R551-R554 controller
                       (subprocess). Requires root because the
                       downstream scripts each require root for
                       their mutating verbs. Triple-gate via
                       --apply --confirm-knob-set per R328 contract.

Read-mostly philosophy: show / plan / list-bundles NEVER write.

Exit codes:
  0  ok
  1  apply partial (one or more underlying controllers failed)
  2  usage / not-root / unknown mode
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

ROUND = "R555"
SDD_VECTOR = "E11.M18"

NVIDIA_MPS = REPO_ROOT / "scripts" / "hardware" / "nvidia-mps.py"
HUGEPAGES = REPO_ROOT / "scripts" / "hardware" / "hugepages-sizer.py"
THP_MODE = REPO_ROOT / "scripts" / "hardware" / "thp-mode.py"
IRQ_AFFINITY = REPO_ROOT / "scripts" / "hardware" / "irq-affinity.py"

WORKLOAD_MODE = REPO_ROOT / "scripts" / "intelligence" / "workload-mode.py"


# ── Bundles ─────────────────────────────────────────────────────────
#
# Each canonical R338 mode maps to one bundle of R551-R554 knobs.
# Each knob entry is either:
#   {"action": "skip", "reason": "..."}       no-op for this mode
#   {"action": "<verb>", "args": [...]}        run underlying script
#
# Rationale per row preserved in `rationale` — operator-readable in
# `workload-knobs list-bundles --json`.

BUNDLES: dict[str, dict[str, Any]] = {
    "idle": {
        "rationale": (
            "Host quiet — no inference engines warm. Tear MPS down "
            "(operator may swap GPUs / driver). THP=never for "
            "deterministic baseline. No IRQ pinning needed (inference "
            "cores aren't busy). No static hugepages claimed (RAM "
            "stays available for whatever the operator is doing)."
        ),
        "mps": {"action": "stop"},
        "hugepages": {"action": "skip",
                      "reason": "idle — return RAM to general pool"},
        "thp": {"action": "policy", "args": ["bench"]},
        "irq": {"action": "skip",
                "reason": "no inference cores to protect"},
    },
    "inference-ready": {
        "rationale": (
            "Default daytime mode — prompt may fire at any moment. "
            "MPS up so multi-process clients (router + sidecar tools) "
            "share the GPU without queueing. THP=inference (madvise + "
            "defer) — predictable latency, no compaction stalls. "
            "Static hugepages reserved (operator-tunable via "
            "/etc/sovereign-os/hugepages.target-gb). IRQ housekeeping "
            "pins all hardware interrupts to cores 0-1 so the "
            "inference cores stay clean."
        ),
        "mps": {"action": "start"},
        "hugepages": {"action": "apply-if-configured"},
        "thp": {"action": "policy", "args": ["inference"]},
        "irq": {"action": "apply", "housekeeping": "0-1"},
    },
    "training": {
        "rationale": (
            "Sustained burn — operator queued a fine-tune / pretrain "
            "and walked away. MPS on (multi-process data loader + "
            "trainer share GPU). THP=inference policy (same predictable "
            "behavior). Static hugepages reserved (training engines "
            "use large activation buffers). IRQ housekeeping pins "
            "interrupts to cores 0-1 — training threads occupy 2+."
        ),
        "mps": {"action": "start"},
        "hugepages": {"action": "apply-if-configured"},
        "thp": {"action": "policy", "args": ["inference"]},
        "irq": {"action": "apply", "housekeeping": "0-1"},
    },
    "oc-burst": {
        "rationale": (
            "Short benchmark / single-shot render — peak transient, "
            "NOT sustained. MPS off (single-process bench wants the "
            "full GPU). THP=aggressive (highest TLB hit rate during "
            "the burst). IRQ pinning kept (still want clean cores). "
            "Hugepages skipped — bench runs are short-lived."
        ),
        "mps": {"action": "stop"},
        "hugepages": {"action": "skip",
                      "reason": "burst is short — skip reservation churn"},
        "thp": {"action": "policy", "args": ["aggressive"]},
        "irq": {"action": "apply", "housekeeping": "0-1"},
    },
}


# ── Helpers ─────────────────────────────────────────────────────────


def read_active_mode() -> str | None:
    if not WORKLOAD_MODE.is_file():
        return None
    try:
        r = subprocess.run(
            ["python3", str(WORKLOAD_MODE), "status", "--json"],
            capture_output=True, text=True, check=False, timeout=10,
        )
        if r.returncode not in (0, 1):
            return None
        data = json.loads(r.stdout)
        return data.get("active_mode")
    except (OSError, json.JSONDecodeError, subprocess.SubprocessError):
        return None


def hugepages_target_gb() -> int | None:
    """Operator-configured hugepages target, if any."""
    p = Path("/etc/sovereign-os/hugepages.target-gb")
    if not p.is_file():
        return None
    try:
        return int(p.read_text().strip())
    except (OSError, ValueError):
        return None


def require_root() -> None:
    if os.geteuid() != 0:
        print(
            "[workload-knobs] apply requires root — the underlying "
            "R551-R554 controllers each require root for mutating "
            "verbs. Re-run with sudo.",
            file=sys.stderr,
        )
        sys.exit(2)


# ── Plan ────────────────────────────────────────────────────────────


def plan_for(mode: str) -> dict[str, Any]:
    if mode not in BUNDLES:
        return {
            "mode": mode,
            "known": False,
            "valid_modes": sorted(BUNDLES),
        }
    bundle = BUNDLES[mode]
    target_gb = hugepages_target_gb()
    return {
        "mode": mode,
        "known": True,
        "rationale": bundle["rationale"],
        "mps": bundle["mps"],
        "hugepages": {
            **bundle["hugepages"],
            "target_gb": target_gb,
            "configured": target_gb is not None,
        },
        "thp": bundle["thp"],
        "irq": bundle["irq"],
    }


# ── Apply ───────────────────────────────────────────────────────────


def _run(cmd: list[str]) -> dict[str, Any]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                            check=False, timeout=60)
        return {
            "cmd": cmd,
            "rc": r.returncode,
            "stdout_tail": r.stdout[-400:] if r.stdout else "",
            "stderr_tail": r.stderr[-400:] if r.stderr else "",
        }
    except (OSError, subprocess.SubprocessError) as e:
        return {"cmd": cmd, "rc": 127, "error": str(e)}


def apply_bundle(mode: str) -> dict[str, Any]:
    require_root()
    plan = plan_for(mode)
    if not plan["known"]:
        return {"ok": False, "error": f"unknown mode: {mode}",
                "plan": plan}
    results: dict[str, Any] = {"mode": mode, "steps": {}}

    # MPS
    mps_action = plan["mps"]["action"]
    if mps_action == "start":
        results["steps"]["mps"] = _run(
            ["python3", str(NVIDIA_MPS), "start"])
    elif mps_action == "stop":
        results["steps"]["mps"] = _run(
            ["python3", str(NVIDIA_MPS), "stop"])
    else:
        results["steps"]["mps"] = {"skipped": True}

    # HugePages
    hp_action = plan["hugepages"]["action"]
    if hp_action == "apply-if-configured" and plan["hugepages"]["configured"]:
        tgt = str(plan["hugepages"]["target_gb"])
        results["steps"]["hugepages"] = _run(
            ["python3", str(HUGEPAGES), "apply", "--target-gb", tgt])
    else:
        results["steps"]["hugepages"] = {
            "skipped": True,
            "reason": plan["hugepages"].get("reason",
                                              "not configured"),
        }

    # THP
    thp = plan["thp"]
    if thp["action"] == "policy":
        results["steps"]["thp"] = _run(
            ["python3", str(THP_MODE), "policy", *thp["args"]])
    else:
        results["steps"]["thp"] = {"skipped": True}

    # IRQ
    irq = plan["irq"]
    if irq["action"] == "apply":
        results["steps"]["irq"] = _run(
            ["python3", str(IRQ_AFFINITY), "apply",
             "--housekeeping-cpus", irq["housekeeping"]])
    else:
        results["steps"]["irq"] = {"skipped": True,
                                    "reason": irq.get("reason", "")}

    refused = [
        k for k, v in results["steps"].items()
        if isinstance(v, dict) and v.get("rc", 0) not in (0, None)
        and not v.get("skipped")
    ]
    results["refused"] = refused
    results["ok"] = not refused
    return results


# ── CLI ─────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="workload-knobs",
        description="Atomic R551-R554 orchestrator (R555 / E11.M18).",
    )
    p.add_argument("--json", action="store_true")
    sub = p.add_subparsers(dest="verb")
    sp_show = sub.add_parser("show")
    sp_show.add_argument("--json", action="store_true", dest="json_sub")
    sp_status = sub.add_parser("status")
    sp_status.add_argument("--json", action="store_true", dest="json_sub")
    sp_plan = sub.add_parser("plan")
    sp_plan.add_argument("mode")
    sp_plan.add_argument("--json", action="store_true", dest="json_sub")
    sp_list = sub.add_parser("list-bundles")
    sp_list.add_argument("--json", action="store_true", dest="json_sub")
    sp_apply = sub.add_parser("apply")
    sp_apply.add_argument("mode")
    sp_apply.add_argument("--apply", action="store_true",
                          help="gate 1/2 — declare apply intent")
    sp_apply.add_argument("--confirm-knob-set", action="store_true",
                          help="gate 2/2 — per-verb confirmation")
    sp_apply.add_argument("--json", action="store_true", dest="json_sub")
    args = p.parse_args(argv)
    verb = args.verb or "show"
    json_out = bool(args.json or getattr(args, "json_sub", False))

    if verb in ("show", "status"):
        active = read_active_mode()
        out: dict[str, Any] = {
            "round": ROUND,
            "sdd_vector": SDD_VECTOR,
            "active_mode": active,
            "valid_modes": sorted(BUNDLES),
        }
        if active in BUNDLES:
            out["bundle"] = plan_for(active)
        if json_out:
            print(json.dumps(out, indent=2))
        else:
            print(f"── R555 workload-knobs (E11.M18) ──")
            print(f"  active mode: {active or '(unset)'}")
            if active in BUNDLES:
                pl = out["bundle"]
                print(f"  bundle:")
                print(f"    mps        : {pl['mps']['action']}")
                print(f"    hugepages  : {pl['hugepages']['action']} "
                      f"(target_gb={pl['hugepages']['target_gb']})")
                print(f"    thp        : {pl['thp']['action']} "
                      f"{' '.join(pl['thp'].get('args', []))}")
                print(f"    irq        : {pl['irq']['action']} "
                      f"{pl['irq'].get('housekeeping', '')}")
        return 0

    if verb == "plan":
        pl = plan_for(args.mode)
        if json_out:
            print(json.dumps(pl, indent=2))
        else:
            if not pl["known"]:
                print(f"unknown mode: {args.mode}")
                print(f"known: {pl['valid_modes']}")
                return 2
            print(f"── R555 plan — mode={args.mode} ──")
            print(f"  rationale: {pl['rationale']}")
            print(f"  mps        : {pl['mps']}")
            print(f"  hugepages  : {pl['hugepages']}")
            print(f"  thp        : {pl['thp']}")
            print(f"  irq        : {pl['irq']}")
        return 0 if pl["known"] else 2

    if verb == "list-bundles":
        if json_out:
            print(json.dumps(BUNDLES, indent=2))
        else:
            for mode, bundle in BUNDLES.items():
                print(f"── {mode} ──")
                print(f"  rationale: {bundle['rationale']}")
                for k in ("mps", "hugepages", "thp", "irq"):
                    print(f"    {k:10s}: {bundle[k]}")
        return 0

    if verb == "apply":
        if args.mode not in BUNDLES:
            print(f"[workload-knobs] unknown mode {args.mode!r}; "
                  f"valid: {sorted(BUNDLES)}", file=sys.stderr)
            return 2
        if not args.apply or not args.confirm_knob_set:
            print(
                "[workload-knobs] apply requires BOTH --apply and "
                "--confirm-knob-set (triple-gate per R328 contract).",
                file=sys.stderr,
            )
            return 2
        result = apply_bundle(args.mode)
        if json_out:
            print(json.dumps(result, indent=2))
        else:
            print(f"── R555 apply mode={args.mode} ──")
            for step, sr in result["steps"].items():
                if sr.get("skipped"):
                    print(f"  [skip] {step:10s} {sr.get('reason', '')}")
                else:
                    tag = "ok" if sr.get("rc") == 0 else "FAIL"
                    print(f"  [{tag:>4s}] {step:10s} rc={sr.get('rc')}")
            if result["refused"]:
                print(f"  refused: {result['refused']}")
        return 0 if result["ok"] else 1

    p.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
