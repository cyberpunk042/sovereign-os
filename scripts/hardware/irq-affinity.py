#!/usr/bin/env python3
"""scripts/hardware/irq-affinity.py — R554 (E11.M17) IRQ affinity.

Operator §1g (verbatim, sacrosanct):
  "Multi mode AI, multiple mode for the AI loadout and load-out switch"
  "sustained-burst / peak-inference"

Inference cores (the ones pinned by start-pulse.sh / start-logic-
engine.sh / start-oracle-core.sh via taskset) must NOT also be
servicing hardware interrupts — every NIC RX, NVMe completion, USB
poll, etc. preempts the inference thread and trashes its CPU caches.

The Linux knob /proc/irq/<N>/smp_affinity (or smp_affinity_list)
controls which CPUs each IRQ vector can land on. By default the
kernel + irqbalance distribute IRQs across ALL cores. R554 lets the
operator define a *housekeeping* CPU set and pin EVERY non-affinity-
locked IRQ to it, leaving the inference cores undisturbed.

Verbs:
  show              dump every /proc/irq/<N>/{smp_affinity_list,actions}.
  list-irqs         compact list: irq, driver/device, current cpu mask.
  recommend         given --housekeeping-cpus N,M,...  emit the per-IRQ
                    smp_affinity_list values that move all non-PCI-MSI-
                    locked IRQs onto housekeeping. Read-only — never
                    writes.
  apply             writes the recommendation. Requires root. Skips
                    IRQs flagged "no_balance" by the kernel (some
                    affinity-locked vectors refuse rebalance and would
                    error EIO).

Read-mostly philosophy: show/list-irqs/recommend NEVER write.

Exit codes:
  0  ok
  1  apply partial (some IRQs accepted, others refused — typical when
     a driver pins its own affinity)
  2  usage / not-root / /proc/irq absent (containerized? no kernel
     interrupts surface)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

PROC_IRQ = Path("/proc/irq")


# ── Probes ──────────────────────────────────────────────────────────


def list_irq_numbers() -> list[int]:
    if not PROC_IRQ.is_dir():
        return []
    out: list[int] = []
    for entry in PROC_IRQ.iterdir():
        if entry.name.isdigit() and entry.is_dir():
            out.append(int(entry.name))
    return sorted(out)


def read_field(irq: int, name: str) -> str | None:
    p = PROC_IRQ / str(irq) / name
    if not p.is_file():
        return None
    try:
        return p.read_text().strip()
    except OSError:
        return None


def irq_record(irq: int) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "irq": irq,
        "smp_affinity_list": read_field(irq, "smp_affinity_list"),
        "effective_affinity_list": read_field(irq, "effective_affinity_list"),
    }
    # Drivers/actions are exposed by the IRQ "actions" or by the
    # subdirectory containing device names.
    actions: list[str] = []
    base = PROC_IRQ / str(irq)
    try:
        for child in base.iterdir():
            if child.is_dir() and not child.name.isdigit():
                actions.append(child.name)
    except OSError:
        pass
    rec["actions"] = actions
    return rec


def gather_state() -> dict[str, Any]:
    if not PROC_IRQ.is_dir():
        return {"proc_irq_present": False, "irqs": []}
    irqs = [irq_record(n) for n in list_irq_numbers()]
    return {"proc_irq_present": True, "irqs": irqs, "count": len(irqs)}


# ── Parsing ─────────────────────────────────────────────────────────


def parse_cpu_list(spec: str) -> list[int]:
    """Parse '0,2-4,7' → [0,2,3,4,7]."""
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            out.update(range(int(lo), int(hi) + 1))
        else:
            out.add(int(part))
    return sorted(out)


def cpu_list_repr(cpus: list[int]) -> str:
    """Inverse of parse_cpu_list — compact range form."""
    if not cpus:
        return ""
    cpus = sorted(cpus)
    runs: list[tuple[int, int]] = []
    start = prev = cpus[0]
    for c in cpus[1:]:
        if c == prev + 1:
            prev = c
            continue
        runs.append((start, prev))
        start = prev = c
    runs.append((start, prev))
    return ",".join(
        (str(a) if a == b else f"{a}-{b}") for a, b in runs
    )


# ── Recommendation ──────────────────────────────────────────────────


def recommend(housekeeping_cpus: list[int]) -> dict[str, Any]:
    state = gather_state()
    if not state["proc_irq_present"]:
        return {"proc_irq_present": False, "plan": []}
    hk_repr = cpu_list_repr(housekeeping_cpus)
    plan: list[dict[str, Any]] = []
    for rec in state["irqs"]:
        cur = rec.get("smp_affinity_list") or ""
        # Skip IRQs whose smp_affinity refuses writes (kernel exposes
        # the file but writes EIO). We can't tell upfront — apply
        # handles the failure path.
        plan.append({
            "irq": rec["irq"],
            "actions": rec["actions"],
            "current": cur,
            "target": hk_repr,
            "noop": (cur == hk_repr),
        })
    return {
        "proc_irq_present": True,
        "housekeeping_cpus": housekeeping_cpus,
        "housekeeping_list": hk_repr,
        "plan": plan,
        "noop_count": sum(1 for x in plan if x["noop"]),
        "change_count": sum(1 for x in plan if not x["noop"]),
    }


# ── Apply ───────────────────────────────────────────────────────────


def require_root() -> None:
    if os.geteuid() != 0:
        print(
            "[irq-affinity] apply requires root. Re-run with sudo.",
            file=sys.stderr,
        )
        sys.exit(2)


def apply_plan(plan: list[dict[str, Any]]) -> dict[str, Any]:
    require_root()
    applied = 0
    skipped = 0
    refused: list[dict[str, Any]] = []
    for item in plan:
        if item["noop"]:
            skipped += 1
            continue
        p = PROC_IRQ / str(item["irq"]) / "smp_affinity_list"
        try:
            p.write_text(item["target"] + "\n")
            applied += 1
        except OSError as e:
            refused.append({"irq": item["irq"], "error": str(e)})
    return {
        "applied": applied,
        "skipped_noop": skipped,
        "refused_count": len(refused),
        "refused": refused,
    }


# ── CLI ─────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="irq-affinity",
        description="IRQ affinity controller (R554 / E11.M17).",
    )
    p.add_argument("--json", action="store_true")
    sub = p.add_subparsers(dest="verb")
    sp_show = sub.add_parser("show")
    sp_show.add_argument("--json", action="store_true", dest="json_sub")
    sp_status = sub.add_parser("status")
    sp_status.add_argument("--json", action="store_true", dest="json_sub")
    sp_list = sub.add_parser("list-irqs")
    sp_list.add_argument("--json", action="store_true", dest="json_sub")
    sp_rec = sub.add_parser("recommend")
    sp_rec.add_argument("--housekeeping-cpus", required=True,
                        help="comma/range CPU list (e.g. '0,1,30-31')")
    sp_rec.add_argument("--json", action="store_true", dest="json_sub")
    sp_apply = sub.add_parser("apply")
    sp_apply.add_argument("--housekeeping-cpus", required=True)
    args = p.parse_args(argv)
    verb = args.verb or "show"
    json_out = bool(args.json or getattr(args, "json_sub", False))

    if verb in ("show", "status", "list-irqs"):
        state = gather_state()
        if json_out:
            print(json.dumps(state, indent=2))
            return 0
        if not state["proc_irq_present"]:
            print("/proc/irq not present (containerized?)")
            return 0
        print(
            f"── sovereign-os IRQ affinity (R554 / E11.M17) — "
            f"{state['count']} IRQs ──"
        )
        for rec in state["irqs"]:
            acts = ",".join(rec["actions"]) if rec["actions"] else "-"
            print(
                f"  irq {rec['irq']:>4}  affinity={rec['smp_affinity_list']:>12}  "
                f"effective={rec['effective_affinity_list'] or '?':>12}  "
                f"actions={acts}"
            )
        return 0
    if verb == "recommend":
        try:
            cpus = parse_cpu_list(args.housekeeping_cpus)
        except ValueError as e:
            print(
                f"[irq-affinity] bad --housekeeping-cpus: {e}", file=sys.stderr,
            )
            return 2
        rec = recommend(cpus)
        if json_out:
            print(json.dumps(rec, indent=2))
        else:
            print(
                f"── plan — housekeeping={rec['housekeeping_list']}  "
                f"changes={rec['change_count']}  noop={rec['noop_count']} ──"
            )
            for item in rec["plan"][:20]:
                tag = "noop" if item["noop"] else "MOVE"
                print(
                    f"  {tag}  irq {item['irq']:>4}  {item['current']:>10} → "
                    f"{item['target']:>10}  {','.join(item['actions']) or '-'}"
                )
            if len(rec["plan"]) > 20:
                print(f"  ... (+{len(rec['plan']) - 20} more) ...")
        return 0
    if verb == "apply":
        try:
            cpus = parse_cpu_list(args.housekeeping_cpus)
        except ValueError as e:
            print(
                f"[irq-affinity] bad --housekeeping-cpus: {e}", file=sys.stderr,
            )
            return 2
        rec = recommend(cpus)
        if not rec["proc_irq_present"]:
            return 2
        result = apply_plan(rec["plan"])
        if json_out:
            print(json.dumps(result, indent=2))
        else:
            print(
                f"[irq-affinity] applied={result['applied']}  "
                f"noop={result['skipped_noop']}  "
                f"refused={result['refused_count']}"
            )
            for r in result["refused"][:10]:
                print(f"   refused irq {r['irq']}: {r['error']}")
        return 1 if result["refused_count"] > 0 else 0
    p.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
