#!/usr/bin/env python3
"""scripts/intelligence/cot-registry.py — R309 (E2.M15).

Operator-named (§1b mandate row, verbatim): "Programming,
Proto-Programing, Proto-Proto-Programming and CoT and custom CoT,
integrated intelligence modules, features and options". Closes
E2.M15 — fills the stop-hook-flagged "no proto-programming / CoT /
integrated-intelligence module surface" gap on sovereign-os.

Selfdef ships SD-R98 @selfdef_macro (Tier 2 operator-pull macros on
the REPL). R309 ships the sovereign-os counterpart: a NAMED CoT
routine registry where each routine composes multiple
sovereign-osctl verbs into a single decision flow.

CLI:
  cot-registry.py list  [--axis X] [--config P] [--json|--human]
  cot-registry.py show  <cot> [--config P] [--json|--human]
  cot-registry.py run   <cot> [--config P] [--json|--human]

Default catalog of 6 operator-pull CoT routines:

  oc-go-no-go-cot           Compose R292 oc-headroom + R296 thermal-oc +
                            R304 mem-pressure-damper → GO / WAIT verdict
                            for raising OC profile.

  health-triage-cot         Compose R226 health-scan + R266 doctor +
                            R308 autohealth → ranked findings list.

  psu-budget-cot            Compose R252 power-status + R294 psu-oc +
                            R303 gpu-wattage → "can I add another GPU?"

  storage-cleanup-cot       Compose R298 storage-health + R234 insights
                            → ordered cleanup steps.

  pre-shutdown-cot          Compose R293 power-profiles + R302 battery-
                            ladder + R262 drain → orderly shutdown plan.

  boot-troubleshoot-cot     Compose R299 bios-directives + R305 kernel-
                            cmdline + R306 hardening-base → boot-time
                            posture verdict.

Operator-overlay (R283/SDD-030): /etc/sovereign-os/cot-registry.toml
adds/replaces catalog. Lists REPLACE.

Exit codes:
  0  ok / ran successfully
  1  attention finding from composed run
  2  critical finding from composed run / usage error
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
ROUND = "R309"
SDD_VECTOR = "E2.M15"


# Each routine: name + description + axes (list of [script_rel, args])
# + synthesis (a small rule the run verb interprets to combine the
# axes' verdicts into a single CoT verdict).
DEFAULT_CATALOG: list[dict[str, Any]] = [
    {
        "name": "oc-go-no-go-cot",
        "axis": "performance",
        "description": "Compose oc-headroom + thermal-oc + memory-pressure "
                       "damper → operator-readable GO / WAIT verdict for "
                       "raising the OC profile by one notch.",
        "axes_probes": [
            ["scripts/hardware/oc-headroom.py", ["status", "--json"]],
            ["scripts/hardware/thermal-oc-budget.py", ["status", "--json"]],
            ["scripts/hardware/memory-pressure-oc-damper.py", ["status", "--json"]],
        ],
        "go_when_all_verdicts_in": ["headroom-safe", "safe", "no-dampening"],
        "operator_caveat": "GO assumes operator-pull confirms via R294 "
                           "psu-oc and applies via oc-headroom overlay.",
    },
    {
        "name": "health-triage-cot",
        "axis": "diagnostics",
        "description": "Compose health-scan + doctor + autohealth → "
                       "ranked findings list; emits operator-pull triage "
                       "order.",
        "axes_probes": [
            ["scripts/hardware/health-scan.py", ["--json"]],
            ["scripts/diagnostics/doctor.py", ["run", "--json"]],
            ["scripts/diagnostics/autohealth.py", ["status", "--json"]],
        ],
        "go_when_all_verdicts_in": ["healthy", "ok", "all-clear", "no-pin"],
        "operator_caveat": "Triage order is informational; operator owns "
                           "the act step.",
    },
    {
        "name": "psu-budget-cot",
        "axis": "performance",
        "description": "Compose power-status + psu-oc + gpu-wattage → "
                       "can-I-add-another-GPU verdict + per-card budget "
                       "projection.",
        "axes_probes": [
            ["scripts/hardware/power-status.py", ["--json"]],
            ["scripts/hardware/psu-oc.py", ["status", "--json"]],
            ["scripts/hardware/gpu-wattage.py", ["budget", "--json"]],
        ],
        "go_when_all_verdicts_in": ["safe", "budget-safe", "headroom-safe"],
        "operator_caveat": "Verdict accounts for budget headroom but NOT "
                           "case airflow or PCIe lane bifurcation — see "
                           "R270 pcie-lanes.",
    },
    {
        "name": "storage-cleanup-cot",
        "axis": "storage",
        "description": "Compose storage-health-rollup + insights → ordered "
                       "cleanup steps the operator runs.",
        "axes_probes": [
            ["scripts/hardware/storage-health-rollup.py", ["status", "--json"]],
            ["scripts/storage/insights.py", ["--json"]],
        ],
        "go_when_all_verdicts_in": ["safe", "ok", "healthy"],
        "operator_caveat": "Cleanup steps are non-destructive list-only; "
                           "operator must actually run them.",
    },
    {
        "name": "pre-shutdown-cot",
        "axis": "lifecycle",
        "description": "Compose power-profiles + battery-ladder + drain → "
                       "orderly shutdown plan (which services to drain in "
                       "which order before poweroff).",
        "axes_probes": [
            ["scripts/hardware/power-profiles.py", ["status", "--json"]],
            ["scripts/hardware/battery-ladder.py", ["status", "--json"]],
            ["scripts/lifecycle/drain.py", ["plan", "--json"]],
        ],
        "go_when_all_verdicts_in": ["on-ac", "headroom-ok", "drainable"],
        "operator_caveat": "Drain ordering is operator-pull; this CoT "
                           "advises but never poweroffs.",
    },
    {
        "name": "boot-troubleshoot-cot",
        "axis": "boot",
        "description": "Compose bios-directives + kernel-cmdline + "
                       "hardening-base → boot-time posture verdict.",
        "axes_probes": [
            ["scripts/hardware/bios-directives.py", ["check", "--json"]],
            ["scripts/kernel/cmdline-advisor.py", ["status", "--json"]],
            ["scripts/hardening/base-catalog.py", ["check", "--json"]],
        ],
        "go_when_all_verdicts_in": ["matches", "matches-recommended",
                                    "matches-pin"],
        "operator_caveat": "Verifies posture only — does NOT mutate BIOS, "
                           "GRUB cmdline, or sysctl.",
    },
]


def load_catalog(overlay_path: Path | None) -> tuple[list[dict], dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    catalog = list(DEFAULT_CATALOG)
    if load_with_overlay is not None:
        cfg = load_with_overlay(
            "cot-registry", {"routines": []}, explicit_path=overlay_path,
        )
        meta["_source"] = cfg.get("_source", meta["_source"])
        meta["_overlay_keys"] = cfg.get("_overlay_keys", [])
        if cfg.get("_parse_error"):
            meta["_parse_error"] = cfg["_parse_error"]
        if cfg.get("routines"):
            catalog = list(cfg["routines"])
    return catalog, meta


def filter_axis(catalog: list[dict], axis: str | None) -> list[dict]:
    if axis is None:
        return list(catalog)
    return [d for d in catalog if isinstance(d, dict) and d.get("axis") == axis]


def resolve(catalog: list[dict], name: str) -> dict | None:
    for d in catalog:
        if isinstance(d, dict) and d.get("name") == name:
            return d
    return None


def _run_probe(rel: str, args: list[str]) -> dict[str, Any] | None:
    bin_path = REPO_ROOT / rel
    if not bin_path.is_file():
        return None
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), *args],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode not in (0, 1, 2):
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def run_cot(routine: dict) -> dict[str, Any]:
    probe_results: list[dict[str, Any]] = []
    verdicts: list[str | None] = []
    for spec in routine.get("axes_probes", []):
        if not isinstance(spec, (list, tuple)) or len(spec) != 2:
            continue
        rel, args = spec[0], list(spec[1])
        doc = _run_probe(rel, args)
        if doc is None:
            probe_results.append({
                "probe": rel,
                "verdict": None,
                "available": False,
            })
            verdicts.append(None)
            continue
        v = doc.get("verdict") or doc.get("status") or doc.get("posture")
        probe_results.append({
            "probe": rel,
            "verdict": v,
            "available": True,
            "rc": doc.get("rc"),
        })
        verdicts.append(v)

    go_set = set(routine.get("go_when_all_verdicts_in", []))
    available = [v for v in verdicts if v is not None]
    if not available:
        cot_verdict = "probes-unavailable"
        rc = 1
    elif all(v in go_set for v in available):
        cot_verdict = "GO"
        rc = 0
    elif any(v in {"critical", "degraded", "over-budget",
                    "pull-oc-now", "dampen-fully"}
              for v in available):
        cot_verdict = "WAIT (critical)"
        rc = 2
    else:
        cot_verdict = "WAIT"
        rc = 1
    return {
        "cot": routine.get("name"),
        "description": routine.get("description"),
        "operator_caveat": routine.get("operator_caveat"),
        "axes_results": probe_results,
        "verdicts_collected": verdicts,
        "verdict": cot_verdict,
        "rc": rc,
    }


def render_list_human(entries: list[dict]) -> str:
    lines = [f"── R309 sovereign-os CoT registry (E2.M15) ──",
             f"  routines: {len(entries)}", ""]
    axes = sorted({d.get("axis", "?") for d in entries if isinstance(d, dict)})
    for ax in axes:
        ax_items = [d for d in entries if d.get("axis") == ax]
        if not ax_items:
            continue
        lines.append(f"  ── {ax} ──")
        for d in ax_items:
            n = d.get("name", "?")
            lines.append(f"    {n}")
            desc = (d.get("description") or "").strip()
            if desc:
                lines.append(f"      {desc[:90]}")
        lines.append("")
    return "\n".join(lines)


def render_show_human(d: dict) -> str:
    lines = [f"── R309 CoT routine: {d.get('name')} (E2.M15) ──",
             f"  axis:            {d.get('axis')}", ""]
    desc = d.get("description") or ""
    lines.append(f"  description: {desc}")
    lines.append("")
    lines.append("  composed probes:")
    for spec in d.get("axes_probes", []) or []:
        if isinstance(spec, (list, tuple)) and len(spec) == 2:
            lines.append(f"    {spec[0]} {' '.join(spec[1])}")
    lines.append("")
    lines.append(f"  GO when verdicts ∈ {d.get('go_when_all_verdicts_in', [])}")
    if d.get("operator_caveat"):
        lines.append(f"  caveat: {d['operator_caveat']}")
    return "\n".join(lines) + "\n"


def render_run_human(result: dict) -> str:
    lines = [f"── R309 CoT run: {result.get('cot')} (E2.M15) ──",
             f"  verdict: {result['verdict']} (rc={result['rc']})", ""]
    lines.append("  axes:")
    for r in result.get("axes_results", []):
        mark = "??" if r.get("verdict") is None else "OK"
        lines.append(f"    [{mark}] {r['probe']:60s} verdict={r.get('verdict')}")
    if result.get("operator_caveat"):
        lines.append("")
        lines.append(f"  caveat: {result['operator_caveat']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="cot-registry.py")
    sub = p.add_subparsers(dest="verb", required=True)

    pl = sub.add_parser("list")
    pl.add_argument("--axis")
    pl.add_argument("--config", type=Path)
    fl = pl.add_mutually_exclusive_group()
    fl.add_argument("--json", dest="fmt", action="store_const", const="json")
    fl.add_argument("--human", dest="fmt", action="store_const", const="human")
    pl.set_defaults(fmt="json")

    ps = sub.add_parser("show")
    ps.add_argument("cot")
    ps.add_argument("--config", type=Path)
    fs = ps.add_mutually_exclusive_group()
    fs.add_argument("--json", dest="fmt", action="store_const", const="json")
    fs.add_argument("--human", dest="fmt", action="store_const", const="human")
    ps.set_defaults(fmt="json")

    pr = sub.add_parser("run")
    pr.add_argument("cot")
    pr.add_argument("--config", type=Path)
    fr = pr.add_mutually_exclusive_group()
    fr.add_argument("--json", dest="fmt", action="store_const", const="json")
    fr.add_argument("--human", dest="fmt", action="store_const", const="human")
    pr.set_defaults(fmt="json")

    args = p.parse_args(argv)
    catalog, meta = load_catalog(args.config)

    if args.verb == "list":
        entries = filter_axis(catalog, args.axis)
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "axis_filter": args.axis,
                "total_count": len(catalog),
                "filtered_count": len(entries),
                "routines": entries,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_list_human(entries), end="")
        return 0

    if args.verb == "show":
        d = resolve(catalog, args.cot)
        if d is None:
            print(json.dumps({
                "error": f"unknown CoT: {args.cot}",
                "known": [x.get("name") for x in catalog if isinstance(x, dict)],
                "round": ROUND,
            }, indent=2), file=sys.stderr)
            return 1
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "routine": d,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_show_human(d), end="")
        return 0

    if args.verb == "run":
        d = resolve(catalog, args.cot)
        if d is None:
            print(json.dumps({
                "error": f"unknown CoT: {args.cot}",
                "known": [x.get("name") for x in catalog if isinstance(x, dict)],
                "round": ROUND,
            }, indent=2), file=sys.stderr)
            return 2
        result = run_cot(d)
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                **result,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_run_human(result), end="")
        return result["rc"]

    return 2


if __name__ == "__main__":
    sys.exit(main())
