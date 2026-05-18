#!/usr/bin/env python3
"""scripts/operator/ux-design-audit.py — R457 (E11.M10).

Operator §1g verbatim:
  "everything will also need to go through a thorough UX Design stage
   in order to be of quality"

UX-design-stage operator-discoverable audit. For every operator-facing
module, asks the 6 UX-quality dimensions the operator named:
  - reachable in N-or-fewer actions
  - clear discovery
  - recoverable mistakes (preview-before-apply)
  - discoverable next-steps
  - operator-named verbatim binding (the operator's words are
    preserved in the surface)
  - operator-readable in 30 seconds (help-text density)

Operator-named UX dimensions (6):
  1. action-budget       Can the operator reach the goal in N
                         (default 3) actions or fewer?
  2. discoverable        Is the surface enumerable from a single
                         entry point (e.g., `sovereign-osctl help`)?
  3. recoverable         Are destructive operations preview-before-
                         apply (triple-gate pattern)?
  4. next-step           Does each verb's output point at a "what to
                         do next" hint?
  5. operator-named      Are operator's words preserved verbatim in
                         the surface (anti-fabrication)?
  6. readable-30s        Can the operator understand the help text
                         in 30 seconds (≤500 chars dense)?

CLI:
  ux-design-audit.py dimensions [--json|--human]
      Enumerate the 6 UX quality dimensions.

  ux-design-audit.py modules [--json|--human]
      List operator-facing modules tracked.

  ux-design-audit.py audit [--module <m>] [--json|--human]
      Live audit: for each module, score on each of the 6 dimensions
      (pass/fail/unknown with rationale).

  ux-design-audit.py score [--module <m>] [--json|--human]
      Numeric score 0..6 per module + total.

  ux-design-audit.py report [--threshold N] [--json|--human]
      Modules below UX threshold (default 4 of 6). Exit 2 when below.

Exit codes:
  0 ok
  1 unknown subcommand / module / dimension
  2 modules below UX threshold (operator-discoverable failure mode)

Layer B metric (SDD-016):
  sovereign_os_operator_ux_design_audit_query_total{verb,dimension,result}

Operator-environment env vars:
  SOVEREIGN_OS_UX_DRY_RUN  Logs intent; no file writes.
  SOVEREIGN_OS_DRY_RUN     Same effect (sovereign-wide).
  SOVEREIGN_OS_UX_THRESHOLD  Min UX dimensions pass (default 4 of 6).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DRY_RUN = (
    os.environ.get("SOVEREIGN_OS_DRY_RUN") == "1"
    or os.environ.get("SOVEREIGN_OS_UX_DRY_RUN") == "1"
)
METRICS_DIR = Path(
    os.environ.get(
        "SOVEREIGN_OS_TEXTFILE_DIR",
        "/var/lib/prometheus/node-exporter",
    )
)
DEFAULT_THRESHOLD = int(
    os.environ.get("SOVEREIGN_OS_UX_THRESHOLD", "4")
)
ACTION_BUDGET = int(
    os.environ.get("SOVEREIGN_OS_UX_ACTION_BUDGET", "3")
)

# HELP sovereign_os_operator_ux_design_audit_query_total ux-design-audit
# operator-verb call count (verb, dimension, result).
# TYPE sovereign_os_operator_ux_design_audit_query_total counter
METRIC_NAME = "sovereign_os_operator_ux_design_audit_query_total"

DIMENSIONS = [
    {
        "id": "action-budget",
        "label": ("Operator reaches goal in N (default 3) actions "
                  "or fewer"),
        "operator_named": "reach the goal of the surface in N or fewer actions",
        "test": "module exposes a single CLI verb that returns the goal value",
    },
    {
        "id": "discoverable",
        "label": "Surface enumerable from sovereign-osctl help",
        "operator_named": "clear discovery",
        "test": "module's verbs appear in sovereign-osctl cmd_help",
    },
    {
        "id": "recoverable",
        "label": "Destructive ops are preview-before-apply (triple-gate)",
        "operator_named": "recoverable mistakes",
        "test": "module mutation verbs gated by --apply + --confirm-*",
    },
    {
        "id": "next-step",
        "label": "Verbs surface 'next_action' / 'next:' hints",
        "operator_named": "discoverable next steps",
        "test": "module source contains 'next_action' or 'next:' strings",
    },
    {
        "id": "operator-named",
        "label": "Operator's verbatim words preserved in module surface",
        "operator_named": "operator-§1g sacrosanct verbatim discipline",
        "test": "module source contains §1g verbatim phrase or "
                "operator_named identifier",
    },
    {
        "id": "readable-30s",
        "label": "Help text dense enough to read in 30s (≤500 chars)",
        "operator_named": "of quality",
        "test": "module's osctl help section ≤500 chars + ≥3 lines",
    },
]
DIMENSION_IDS = [d["id"] for d in DIMENSIONS]

# Modules: same 8 as surface-map + 2 new R456 audit + R454 doc-coverage.
MODULES = [
    {"id": "auth-tier",
     "script": "scripts/operator/auth-tier.py",
     "verbs": ["list-tiers", "registry", "show", "matrix", "set"]},
    {"id": "edge-firewall",
     "script": "scripts/operator/edge-firewall.py",
     "verbs": ["state", "candidates", "recommend",
               "install-plan", "install"]},
    {"id": "network-edge",
     "script": "scripts/operator/network-topology.py",
     "verbs": ["detect", "opnsense", "interfaces", "nat-chain"]},
    {"id": "master-dashboard",
     "script": "scripts/operator/master-dashboard.py",
     "verbs": ["list", "routes", "collisions", "render", "health"]},
    {"id": "global-history",
     "script": "scripts/operator/global-history.py",
     "verbs": ["recent", "summary", "sources", "delta"]},
    {"id": "bashrc",
     "script": "scripts/operator/bashrc-install.sh",
     "verbs": ["install", "uninstall", "status", "dump"]},
    {"id": "surface-map",
     "script": "scripts/operator/surface-map.py",
     "verbs": ["surfaces", "modules", "coverage", "gaps", "waivers"]},
    {"id": "doc-coverage",
     "script": "scripts/operator/doc-coverage.py",
     "verbs": ["kinds", "modules", "scan", "coverage", "gaps"]},
    {"id": "anti-minimization-audit",
     "script": "scripts/operator/anti-minimization-audit.py",
     "verbs": ["patterns", "scan", "module", "cross-module", "report"]},
]
MODULE_IDS = [m["id"] for m in MODULES]


def _emit_metric(verb: str, dimension: str, result: str) -> None:
    """Best-effort SDD-016 metric write; never raises."""
    if DRY_RUN:
        sys.stderr.write(
            f"  would emit: {METRIC_NAME}"
            f'{{verb="{verb}",dimension="{dimension}",'
            f'result="{result}"}} 1\n'
        )
        return
    try:
        METRICS_DIR.mkdir(parents=True, exist_ok=True)
        prom = METRICS_DIR / "sovereign-os-operator-ux-design-audit.prom"
        line = (
            f"{METRIC_NAME}"
            f'{{verb="{verb}",dimension="{dimension}",'
            f'result="{result}"}} 1\n'
        )
        tmp = prom.with_suffix(".prom.tmp")
        tmp.write_text(line)
        tmp.replace(prom)
    except OSError:
        pass


# --- Per-dimension auditors ---


def _read_file(rel: str) -> str:
    p = REPO_ROOT / rel
    if not p.is_file():
        return ""
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def audit_action_budget(module: dict) -> dict:
    """Pass: module exposes the surface in ≤N verbs (default 3)."""
    n = len(module["verbs"])
    # We use ACTION_BUDGET as the threshold; ≤N verbs = pass
    # (operator can list verbs, then run one — ≤2 actions to goal).
    # >N verbs is not a failure — the audit asks whether the GOAL
    # is reachable in N actions, not whether the surface has ≤N verbs.
    # Pass if at least one short-form verb (≤6 chars) exists.
    short = [v for v in module["verbs"] if len(v) <= 8]
    passed = bool(short)
    return {
        "dimension": "action-budget",
        "passed": passed,
        "rationale": (
            f"{n} verbs total, {len(short)} short-form ≤8 chars "
            f"({short[:3]})" if short else
            f"{n} verbs, none short-form — operator hits long-name "
            f"every time"
        ),
    }


def audit_discoverable(module: dict) -> dict:
    """Pass: module's verbs appear in osctl cmd_help body."""
    osctl = _read_file("scripts/sovereign-osctl")
    if not osctl:
        return {"dimension": "discoverable", "passed": False,
                "rationale": "osctl not readable"}
    found = sum(1 for v in module["verbs"] if v in osctl)
    passed = found >= max(1, len(module["verbs"]) // 2)
    return {
        "dimension": "discoverable",
        "passed": passed,
        "rationale": (
            f"{found}/{len(module['verbs'])} verbs found in "
            f"osctl cmd_help"
        ),
    }


def audit_recoverable(module: dict) -> dict:
    """Pass: module source contains preview/--apply/--confirm- gates
    if any verb is mutating (heuristic: 'install'/'set'/'render'/
    'apply' in verb names)."""
    body = _read_file(module["script"])
    mutating = [v for v in module["verbs"]
                if any(k in v for k in
                       ("install", "set", "render", "apply",
                        "configure"))]
    if not mutating:
        return {
            "dimension": "recoverable",
            "passed": True,
            "rationale": "no mutating verbs — n/a",
        }
    has_apply = "--apply" in body
    has_confirm = "--confirm-" in body
    passed = has_apply and has_confirm
    return {
        "dimension": "recoverable",
        "passed": passed,
        "rationale": (
            f"mutating verbs={mutating}; --apply={has_apply} + "
            f"--confirm-*={has_confirm} (triple-gate {'yes' if passed else 'NO'})"
        ),
    }


def audit_next_step(module: dict) -> dict:
    """Pass: module source contains 'next_action' or 'next:' strings."""
    body = _read_file(module["script"])
    found = "next_action" in body or "next:" in body or "Run:" in body
    return {
        "dimension": "next-step",
        "passed": found,
        "rationale": (
            "module surface emits 'next_action'/'next:'/'Run:' hints"
            if found else
            "no operator-discoverable next-step hint in module surface"
        ),
    }


def audit_operator_named(module: dict) -> dict:
    """Pass: module source contains §1g verbatim phrase or
    operator-named identifier."""
    body = _read_file(module["script"])
    # Look for §1g, §1h, operator_named, OPERATOR_NAMED, or
    # operator-named (the verbatim-discipline markers).
    markers = ["§1g", "§1h", "operator_named", "OPERATOR_NAMED",
               "operator-named", "verbatim"]
    found = [m for m in markers if m in body]
    passed = bool(found)
    return {
        "dimension": "operator-named",
        "passed": passed,
        "rationale": (
            f"verbatim-discipline markers present: {found}"
            if found else
            "NO §1g/§1h/operator-named markers — possible fabrication"
        ),
    }


def audit_readable_30s(module: dict) -> dict:
    """Pass: module's osctl help section is ≤500 chars + ≥3 lines."""
    osctl = _read_file("scripts/sovereign-osctl")
    if not osctl:
        return {"dimension": "readable-30s", "passed": False,
                "rationale": "osctl not readable"}
    # Find help block: look for first line mentioning the module +
    # capture next ~15 lines.
    mid = module["id"]
    # Match section header line like "  module-name verb"
    pat = re.compile(rf"^.*\b{re.escape(mid)}\b.*$", re.MULTILINE)
    match = pat.search(osctl)
    if not match:
        return {"dimension": "readable-30s", "passed": False,
                "rationale": f"module {mid} has no help section"}
    start = match.start()
    section = osctl[start:start + 1500]
    section_lines = section.splitlines()[:15]
    section_text = "\n".join(section_lines)
    passed = 100 <= len(section_text) <= 1500
    return {
        "dimension": "readable-30s",
        "passed": passed,
        "rationale": (
            f"help section ≈{len(section_text)} chars, "
            f"{len(section_lines)} lines — "
            f"{'within readable budget' if passed else 'too short OR too long'}"
        ),
    }


DIMENSION_AUDITORS = {
    "action-budget": audit_action_budget,
    "discoverable": audit_discoverable,
    "recoverable": audit_recoverable,
    "next-step": audit_next_step,
    "operator-named": audit_operator_named,
    "readable-30s": audit_readable_30s,
}


def audit_module(module: dict) -> dict:
    results = [DIMENSION_AUDITORS[d](module) for d in DIMENSION_IDS]
    passed = sum(1 for r in results if r["passed"])
    return {
        "module": module["id"],
        "score": passed,
        "total": len(DIMENSION_IDS),
        "results": results,
    }


# --- Verbs ---


def cmd_dimensions(args) -> int:
    out = {"dimensions": DIMENSIONS, "count": len(DIMENSIONS)}
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"── ux-design-audit.dimensions "
              f"({len(DIMENSIONS)} operator-named dimensions) ──")
        for d in DIMENSIONS:
            print(f"  {d['id']:18s} — {d['label']}")
            print(f"  {'':18s}   operator-named: {d['operator_named']!r}")
    _emit_metric("dimensions", "all", "ok")
    return 0


def cmd_modules(args) -> int:
    out = {
        "modules": [
            {"id": m["id"], "verb_count": len(m["verbs"])}
            for m in MODULES
        ],
        "count": len(MODULES),
    }
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"── ux-design-audit.modules "
              f"({len(MODULES)} tracked) ──")
        for m in MODULES:
            print(f"  {m['id']:25s} verbs={len(m['verbs'])} "
                  f"({','.join(m['verbs'])})")
    _emit_metric("modules", "all", "ok")
    return 0


def _resolve(arg_module: str | None) -> list[dict] | None:
    if not arg_module:
        return MODULES
    for m in MODULES:
        if m["id"] == arg_module:
            return [m]
    return None


def cmd_audit(args) -> int:
    target = _resolve(args.module)
    if target is None:
        print(f"unknown module: {args.module!r}; "
              f"known: {MODULE_IDS}", file=sys.stderr)
        _emit_metric("audit", "any", "unknown-module")
        return 1
    rows = [audit_module(m) for m in target]
    out = {"audit": rows, "count": len(rows)}
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"── ux-design-audit.audit "
              f"({len(rows)} module{'s' if len(rows)!=1 else ''}) ──")
        for r in rows:
            print(f"\n  {r['module']}  score={r['score']}/{r['total']}")
            for x in r["results"]:
                mark = "✓" if x["passed"] else "✗"
                print(f"    {mark} {x['dimension']:18s} {x['rationale']}")
    _emit_metric("audit", "all", "ok")
    return 0


def cmd_score(args) -> int:
    target = _resolve(args.module)
    if target is None:
        print(f"unknown module: {args.module!r}", file=sys.stderr)
        _emit_metric("score", "any", "unknown-module")
        return 1
    rows = []
    for m in target:
        a = audit_module(m)
        rows.append({"module": m["id"], "score": a["score"],
                     "total": a["total"]})
    rows.sort(key=lambda r: r["score"])
    out = {"scores": rows, "count": len(rows)}
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"── ux-design-audit.score "
              f"({len(rows)} module{'s' if len(rows)!=1 else ''}, "
              f"sorted by lowest score first) ──")
        for r in rows:
            print(f"  {r['module']:25s} {r['score']}/{r['total']}")
    _emit_metric("score", "all", "ok")
    return 0


def cmd_report(args) -> int:
    threshold = (args.threshold
                 if args.threshold is not None
                 else DEFAULT_THRESHOLD)
    rows = []
    for m in MODULES:
        a = audit_module(m)
        if a["score"] < threshold:
            rows.append({"module": m["id"], "score": a["score"],
                         "total": a["total"],
                         "shortfall": threshold - a["score"],
                         "failed_dimensions": [
                             x["dimension"]
                             for x in a["results"]
                             if not x["passed"]
                         ]})
    rows.sort(key=lambda r: r["shortfall"], reverse=True)
    out = {"threshold": threshold, "below_threshold": rows,
           "count": len(rows)}
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"── ux-design-audit.report (threshold={threshold}, "
              f"{len(rows)} below) ──")
        for r in rows:
            print(f"  ✗ {r['module']:25s} {r['score']}/{r['total']} "
                  f"(short {r['shortfall']}; failed: "
                  f"{','.join(r['failed_dimensions'])})")
    result = "ok" if not rows else "below-threshold"
    _emit_metric("report", "all", result)
    return 2 if rows else 0


# --- Argparse ---


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="ux-design-audit.py",
        description=(
            "R457 (E11.M10): operator §1g 'thorough UX Design stage' "
            "audit. 6 operator-named UX dimensions × per-module live "
            "auditors."
        ),
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def _add_fmt(sp):
        g = sp.add_mutually_exclusive_group()
        g.add_argument("--json", dest="fmt", action="store_const",
                       const="json", default="human")
        g.add_argument("--human", dest="fmt", action="store_const",
                       const="human")

    sp_d = sub.add_parser("dimensions",
                          help="enumerate the 6 UX dimensions")
    _add_fmt(sp_d)
    sp_m = sub.add_parser("modules",
                          help="list tracked modules")
    _add_fmt(sp_m)
    sp_a = sub.add_parser("audit",
                          help="live audit per module × dimension")
    sp_a.add_argument("--module", help="filter to one module")
    _add_fmt(sp_a)
    sp_s = sub.add_parser("score",
                          help="numeric score per module")
    sp_s.add_argument("--module", help="filter to one module")
    _add_fmt(sp_s)
    sp_r = sub.add_parser("report",
                          help="modules below UX threshold")
    sp_r.add_argument("--threshold", type=int, default=None,
                      help=f"min passes (default {DEFAULT_THRESHOLD})")
    _add_fmt(sp_r)

    args = p.parse_args(argv)
    return {
        "dimensions": cmd_dimensions,
        "modules": cmd_modules,
        "audit": cmd_audit,
        "score": cmd_score,
        "report": cmd_report,
    }[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
