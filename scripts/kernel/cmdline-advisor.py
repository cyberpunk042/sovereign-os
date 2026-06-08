#!/usr/bin/env python3
"""scripts/kernel/cmdline-advisor.py — R305 (E1.M30).

Operator-named (§1b mandate row, verbatim): "Kernel optimisation, OS,
Services, Modules, Tools, Dashboards, Configurations, Options".
Closes E1.M30 — kernel cmdline parameter advisor.

R239 (kernel/tuning.py) ships sysctl tuning presets + a `cmdline-hints`
verb that EMITS recommended kernel cmdline. R305 closes the loop: it
PARSES the actual `/proc/cmdline` + DIFFS against an operator-pinned
AI-workload recommended set, then emits per-param verdict +
operator-readable rationale + the add/remove operator must run via
`grubby --update-kernel=ALL --args=...` or equivalent.

The catalog is operator-curated for the SAIN-01 workload (Zen5
9900X + dual-GPU + AI inference). Operator-overlay (R283/SDD-030)
adds/removes params; defaults are a sensible starting point.

CLI:
  cmdline-advisor.py status [--config P] [--json|--human]
                        full per-param state + verdict
  cmdline-advisor.py diff   [--config P] [--json|--human]
                        ONLY mismatching params (to-add + to-remove)
  cmdline-advisor.py apply-hint [--config P] [--json|--human]
                        emit grubby command operator runs to align

Exit codes:
  0  cmdline matches recommended (no diff)
  1  ≥1 param mismatch (operator action recommended)
  2  /proc/cmdline unreadable
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
ROUND = "R305"
SDD_VECTOR = "E1.M30"


# ── Default operator-pinned cmdline catalog ────────────────────────
#
# Each entry: name, value (None = bare flag), rationale, axis,
# operator_caveat. The "recommended" knob is per-param — operator-pull
# means catalog ships sensible defaults but operator REPLACES via
# overlay when their workload differs.
DEFAULT_RECOMMENDED: list[dict[str, Any]] = [
    {
        "name": "iommu",
        "value": "pt",
        "axis": "virt",
        "rationale": "Pass-through IOMMU mode — required for VFIO GPU "
                     "passthrough (Stage-3+ virt workloads) and DMA "
                     "protection.",
        "operator_caveat": "Pair with amd_iommu=on; verify with "
                           "`ls /sys/kernel/iommu_groups/`.",
    },
    {
        "name": "amd_iommu",
        "value": "on",
        "axis": "virt",
        "rationale": "Enable AMD IOMMU at boot (BIOS must also have "
                     "IOMMU=Enabled per R299 BIOS directives).",
        "operator_caveat": "On Zen5 9900X this is the AMD-side counterpart "
                           "to the BIOS IOMMU toggle.",
    },
    {
        "name": "transparent_hugepage",
        "value": "madvise",
        "axis": "memory",
        "rationale": "Transparent hugepages on madvise() — process opts in. "
                     "Avoids the latency spikes from always=on while still "
                     "letting CUDA / vllm grab 2 MiB pages when they ask.",
        "operator_caveat": "always=on can mask memory pressure problems "
                           "by inflating reclaim cost.",
    },
    {
        "name": "mitigations",
        "value": "off",
        "axis": "cpu",
        "rationale": "Disable Spectre/Meltdown/etc microcode mitigations. "
                     "Operator-trusted SAIN-01 (single-tenant, no untrusted "
                     "workloads); recovers ~5-15% perf for AI inference.",
        "operator_caveat": "ONLY apply on single-tenant operator-trusted "
                           "hosts. Multi-tenant / cloud = NEVER use this.",
    },
    {
        "name": "nvme.poll_queues",
        "value": "4",
        "axis": "storage",
        "rationale": "Per-CPU NVMe polling queues — bypass interrupt path "
                     "for hot model-loading workloads from local NVMe.",
        "operator_caveat": "Each polling queue burns a CPU when active; "
                           "operator picks N ≤ logical CPU count.",
    },
    {
        "name": "transparent_hugepage_defrag",
        "value": "defer+madvise",
        "axis": "memory",
        "rationale": "Lazy hugepage defrag — defers compaction to kswapd, "
                     "doesn't block allocations.",
        "operator_caveat": "Some kernels expose this as a /sys knob, not "
                           "cmdline. Verify via /sys/kernel/mm/transparent_"
                           "hugepage/defrag.",
    },
    {
        "name": "rcu_nocbs",
        "value": "0-N",  # operator-pinned; default to all
        "axis": "cpu",
        "rationale": "Offload RCU callbacks to dedicated thread — lowers "
                     "latency variance on operator's inference loop.",
        "operator_caveat": "Set explicit CPU range matching isolcpus when "
                           "operator pins inference workloads.",
    },
    {
        "name": "isolcpus",
        "value": "2-N",  # operator-pinned; reserve a housekeeping CPU set
        "axis": "cpu",
        "rationale": "Isolate a CPU set from the general scheduler so the "
                     "inference loop owns those cores without timeslice "
                     "competition — the other half of the rcu_nocbs/nohz_full "
                     "CPU-isolation triad for deterministic latency.",
        "operator_caveat": "Leave CPU 0-1 for housekeeping; isolated CPUs "
                           "won't run normal tasks, so size the set to the "
                           "actual inference thread count. Pair with "
                           "rcu_nocbs + nohz_full over the SAME range.",
    },
    {
        "name": "nohz_full",
        "value": "2-N",  # operator-pinned; match the isolcpus range
        "axis": "cpu",
        "rationale": "Full dynticks (tickless) on the isolated CPUs — removes "
                     "the periodic scheduler-tick interrupt from cores running "
                     "the inference loop, cutting jitter to near-zero.",
        "operator_caveat": "Only effective on CPUs also in isolcpus + "
                           "rcu_nocbs; one housekeeping CPU must stay "
                           "ticked. Verify with `cat /sys/devices/system/cpu/"
                           "nohz_full`.",
    },
    {
        "name": "preempt",
        "value": "voluntary",
        "axis": "cpu",
        "rationale": "Voluntary preemption — balanced throughput / latency "
                     "for mixed inference + training workloads.",
        "operator_caveat": "preempt=full = lower latency but lower thr.put. "
                           "preempt=none = max thr.put for pure training.",
    },
]


def parse_proc_cmdline(path: Path | str = "/proc/cmdline") -> dict[str, Any]:
    """Parse /proc/cmdline into {param: value or None} dict.

    Values like `iommu=pt` → {"iommu": "pt"}.
    Bare flags like `quiet` → {"quiet": None}.
    Returns empty dict + error when unreadable.
    """
    p = Path(path) if not isinstance(path, Path) else path
    if not p.is_file():
        return {"_error": f"{p} not found"}
    try:
        body = p.read_text().strip()
    except OSError as e:
        return {"_error": f"{p} read: {e}"}
    result: dict[str, Any] = {}
    for tok in body.split():
        if "=" in tok:
            k, v = tok.split("=", 1)
            result[k] = v
        else:
            result[tok] = None
    return result


def diff_cmdline(actual: dict[str, Any],
                 recommended: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute add/remove diff between actual and recommended."""
    actual_clean = {k: v for k, v in actual.items() if not k.startswith("_")}
    rec_by_name = {r["name"]: r for r in recommended if isinstance(r, dict)}
    to_add: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []
    for name, rec in rec_by_name.items():
        rec_v = rec.get("value")
        if name not in actual_clean:
            to_add.append({**rec, "current": "(absent)"})
        elif actual_clean[name] != rec_v:
            to_add.append({**rec, "current": actual_clean[name]})
        else:
            matches.append({**rec, "current": actual_clean[name]})
    # Recommended-list never says "remove" by default (operator's existing
    # params are theirs); only flagging the rec set's deltas keeps this
    # advisory non-destructive.
    return {
        "to_add": to_add,
        "matches": matches,
        "actual_param_count": len(actual_clean),
    }


def render_human(doc: dict) -> str:
    lines = ["── R305 sovereign-os kernel cmdline advisor (E1.M30) ──"]
    lines.append(f"  /proc/cmdline params: {doc['actual_param_count']}")
    lines.append(f"  recommended params:   {len(doc.get('recommended', []))}")
    lines.append(f"  to-add / mismatched:  {len(doc.get('to_add', []))}")
    lines.append(f"  matches:              {len(doc.get('matches', []))}")
    lines.append(f"  verdict:              {doc['verdict']} (rc={doc['rc']})")
    lines.append("")
    if doc.get("to_add"):
        lines.append("  to-add / mismatched:")
        for r in doc["to_add"]:
            v = r.get("value")
            cur = r.get("current")
            param = f"{r['name']}={v}" if v is not None else r["name"]
            lines.append(f"    [DIFF] {param:40s}  current: {cur}")
            if r.get("rationale"):
                lines.append(f"           {r['rationale']}")
    if doc.get("matches"):
        lines.append("")
        lines.append("  matches:")
        for r in doc["matches"]:
            v = r.get("value")
            param = f"{r['name']}={v}" if v is not None else r["name"]
            lines.append(f"    [OK  ] {param}")
    return "\n".join(lines) + "\n"


def grubby_hint(to_add: list[dict[str, Any]]) -> str:
    parts = []
    for r in to_add:
        v = r.get("value")
        parts.append(f"{r['name']}={v}" if v is not None else r["name"])
    if not parts:
        return "(no diff — nothing to add)"
    return f"sudo grubby --update-kernel=ALL --args='{' '.join(parts)}'"


def build_report(overlay_path: Path | None,
                 actual_override: dict[str, Any] | None = None) -> dict[str, Any]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    catalog = list(DEFAULT_RECOMMENDED)
    if load_with_overlay is not None:
        loaded = load_with_overlay("kernel-cmdline-advisor",
                                    {"recommended": []},
                                    explicit_path=overlay_path)
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]
        if loaded.get("recommended"):
            catalog = list(loaded["recommended"])

    if actual_override is not None:
        actual = dict(actual_override)
    else:
        actual = parse_proc_cmdline()
    if "_error" in actual:
        return {
            "schema_version": SCHEMA_VERSION,
            "round": ROUND,
            "sdd_vector": SDD_VECTOR,
            "actual_param_count": 0,
            "actual_error": actual["_error"],
            "recommended": catalog,
            "to_add": [],
            "matches": [],
            "verdict": "cmdline-unreadable",
            "rc": 2,
            "overlay": meta,
        }
    diff = diff_cmdline(actual, catalog)
    if diff["to_add"]:
        verdict, rc = "diff", 1
    else:
        verdict, rc = "matches-recommended", 0
    return {
        "schema_version": SCHEMA_VERSION,
        "round": ROUND,
        "sdd_vector": SDD_VECTOR,
        "actual": actual,
        "actual_param_count": diff["actual_param_count"],
        "recommended": catalog,
        "to_add": diff["to_add"],
        "matches": diff["matches"],
        "verdict": verdict,
        "rc": rc,
        "overlay": meta,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="cmdline-advisor.py")
    sub = p.add_subparsers(dest="verb", required=True)
    for verb in ("status", "diff", "apply-hint"):
        sp = sub.add_parser(verb)
        sp.add_argument("--config", type=Path)
        fmt = sp.add_mutually_exclusive_group()
        fmt.add_argument("--json", dest="fmt", action="store_const", const="json")
        fmt.add_argument("--human", dest="fmt", action="store_const", const="human")
        sp.set_defaults(fmt="json")

    args = p.parse_args(argv)
    doc = build_report(args.config)

    if args.verb == "apply-hint":
        hint = grubby_hint(doc["to_add"])
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "apply_command": hint,
                "to_add_count": len(doc["to_add"]),
                "verdict": doc["verdict"],
                "rc": doc["rc"],
            }, indent=2))
        else:
            print(f"── R305 apply-hint (E1.M30) ──")
            print(f"  diff count: {len(doc['to_add'])}")
            print(f"  $ {hint}")
        return doc["rc"]

    if args.verb == "diff":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "to_add": doc["to_add"],
                "to_add_count": len(doc["to_add"]),
                "verdict": doc["verdict"],
                "rc": doc["rc"],
            }, indent=2))
        else:
            if not doc["to_add"]:
                print("(no diff — cmdline matches operator-recommended set)")
            else:
                print(f"── R305 cmdline diff (E1.M30) — {len(doc['to_add'])} mismatch(es) ──")
                for r in doc["to_add"]:
                    v = r.get("value")
                    param = f"{r['name']}={v}" if v is not None else r["name"]
                    print(f"  • {param}  current={r.get('current')}")
                    if r.get("rationale"):
                        print(f"      {r['rationale']}")
        return doc["rc"]

    # status
    if args.fmt == "json":
        print(json.dumps(doc, indent=2))
    else:
        print(render_human(doc), end="")
    return doc["rc"]


if __name__ == "__main__":
    sys.exit(main())
