#!/usr/bin/env python3
"""scripts/operator/doc-coverage.py — R454 (E11.M1).

Operator §1g verbatim:
  "very clear and well defined documentation through and through
   which follow the high standards"

Per-module documentation coverage scanner. For every operator-facing
module, ASKS: which of the 6 documentation surfaces does it ship?

Operator-named documentation surfaces (6):
  1. readme            mention in repo top-level README.md
  2. sdd               dedicated chapter under docs/sdd/
  3. helptext          sovereign-osctl cmd_help section (DX surface)
  4. metric-inventory  row in docs/observability/dashboards/README.md
  5. mandate-row       row in operator-mandate (E11.Mx or E10.Mx)
  6. man-page          stub under docs/man/

CLI:
  doc-coverage.py kinds [--json|--human]
      Enumerate the 6 doc surfaces with operator-§1g rationale.

  doc-coverage.py modules [--json|--human]
      List operator-facing modules tracked by the scanner.

  doc-coverage.py scan [--module <m>] [--json|--human]
      Live grep: for each module, which doc surfaces actually mention
      it? Returns shipped/missing per cell. (Auto-discovery, not a
      hand-maintained table — the docs ARE the source of truth.)

  doc-coverage.py coverage [--module <m>] [--json|--human]
      Coverage matrix (same data as scan but in matrix form, sorted
      by largest gap first).

  doc-coverage.py gaps [--threshold N] [--module <m>] [--json|--human]
      Modules below documentation threshold (default 3 of 6).
      Exit 2 when below — operator-discoverable failure mode.

Exit codes:
  0 ok
  1 unknown subcommand / module
  2 modules below documentation threshold

Layer B metric (SDD-016):
  sovereign_os_operator_doc_coverage_query_total{verb,kind,result}

Operator-environment env vars:
  SOVEREIGN_OS_DOC_COVERAGE_DRY_RUN  Logs intent; no file writes.
  SOVEREIGN_OS_DRY_RUN               Same effect (sovereign-wide).
  SOVEREIGN_OS_DOC_THRESHOLD         Min doc surfaces per module
                                     (default 3 of 6).
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
    or os.environ.get("SOVEREIGN_OS_DOC_COVERAGE_DRY_RUN") == "1"
)
# R471 cross-repo: selfdef DocManifest TOMLs live here. Each selfdef
# module ships one declaring its per-kind doc-coverage standing
# (SD-R-DOC-MANIFEST-1, crate `selfdef-doc-manifest`).
SELFDEF_DOC_DIR = Path(
    os.environ.get(
        "SOVEREIGN_OS_SELFDEF_DOC_DIR",
        "/etc/selfdef/doc-manifests",
    )
)
METRICS_DIR = Path(
    os.environ.get(
        "SOVEREIGN_OS_TEXTFILE_DIR",
        "/var/lib/prometheus/node-exporter",
    )
)
DEFAULT_THRESHOLD = int(
    os.environ.get("SOVEREIGN_OS_DOC_THRESHOLD", "3")
)

# HELP sovereign_os_operator_doc_coverage_query_total doc-coverage operator-
# verb call count (verb, kind, result).
# TYPE sovereign_os_operator_doc_coverage_query_total counter
METRIC_NAME = "sovereign_os_operator_doc_coverage_query_total"

# Operator-named documentation surfaces. Each kind has a "locator"
# function that decides whether a module is documented in that surface.
DOC_KINDS = [
    {
        "id": "readme",
        "label": "top-level README.md mention",
        "operator_named": "README",
        "path": "README.md",
    },
    {
        "id": "sdd",
        "label": "dedicated SDD chapter under docs/sdd/",
        "operator_named": "SDD chapter",
        "path": "docs/sdd/",
    },
    {
        "id": "helptext",
        "label": "sovereign-osctl cmd_help section",
        "operator_named": "help-text (DX)",
        "path": "scripts/sovereign-osctl",
    },
    {
        "id": "metric-inventory",
        "label": "docs/observability/dashboards/README.md row",
        "operator_named": "metric inventory",
        "path": "docs/observability/dashboards/README.md",
    },
    {
        "id": "mandate-row",
        "label": "operator-mandate row (E11.Mx or E10.Mx)",
        "operator_named": "mandate row",
        "path": "docs/standing-directives/2026-05-17-operator-mandate.md",
    },
    {
        "id": "man-page",
        "label": "stub under docs/man/",
        "operator_named": "man page",
        "path": "docs/man/",
    },
]
DOC_KIND_IDS = [k["id"] for k in DOC_KINDS]

# Modules tracked. Same 8 as surface-map.py to give the operator a
# parallel doc-coverage view of the runtime surface-map view.
# Each module: id + alternate names to grep (some modules use hyphens
# vs underscores; some have multiple identifiers in docs).
MODULES = [
    {"id": "auth-tier", "patterns": ["auth-tier", "auth_tier",
                                     "auth tier"]},
    {"id": "edge-firewall", "patterns": ["edge-firewall",
                                         "edge_firewall",
                                         "edge firewall"]},
    {"id": "network-edge", "patterns": ["network-edge", "network_edge",
                                        "network edge",
                                        "network-topology"]},
    {"id": "master-dashboard", "patterns": ["master-dashboard",
                                            "master_dashboard",
                                            "master dashboard"]},
    {"id": "global-history", "patterns": ["global-history",
                                          "global_history",
                                          "global history"]},
    {"id": "bashrc", "patterns": ["bashrc-install", "bashrc install",
                                  "bashrc opt-in"]},
    {"id": "surface-map", "patterns": ["surface-map", "surface_map",
                                       "surface map"]},
    # Trinity is operator-§1g three-tier inference architecture; docs
    # use both the marketing name and per-tier names. Match either.
    {"id": "trinity", "patterns": [
        "trinity-pulse", "Trinity Pulse", "trinity-logic-engine",
        "trinity-oracle", "oracle-core", "logic-engine",
        "trinity tier", "Trinity tier", "Trinity tier-3",
        "TRINITY", "Trinity",
    ]},
    # Router = SDD-011 deterministic prompt router (sovereign-osctl
    # `inference route/start/status` verbs operate it; metric
    # inventory has 'sovereign_os_inference_router_*' families).
    {"id": "router", "patterns": [
        "SDD-011", "deterministic router", "deterministic prompt router",
        "inference router", "router tier", "prompt routing",
        "router classify", "selfdef-router",
        "sovereign_os_inference_router",
        "inference route", "inference start",
        "sovereign-router.service",
    ]},
]
MODULE_IDS = [m["id"] for m in MODULES]


def _emit_metric(verb: str, kind: str, result: str) -> None:
    """Best-effort SDD-016 metric write; never raises."""
    if DRY_RUN:
        sys.stderr.write(
            f"  would emit: {METRIC_NAME}"
            f'{{verb="{verb}",kind="{kind}",result="{result}"}} 1\n'
        )
        return
    try:
        METRICS_DIR.mkdir(parents=True, exist_ok=True)
        prom = METRICS_DIR / "sovereign-os-operator-doc-coverage.prom"
        line = (
            f"{METRIC_NAME}"
            f'{{verb="{verb}",kind="{kind}",result="{result}"}} 1\n'
        )
        tmp = prom.with_suffix(".prom.tmp")
        tmp.write_text(line)
        tmp.replace(prom)
    except OSError:
        pass


# --- Doc-presence detectors (per kind) ---


def _grep_file(path: Path, patterns: list[str]) -> bool:
    """Best-effort substring grep across a single file. Never raises."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return any(p in text for p in patterns)


def _grep_tree(root: Path, patterns: list[str], suffix: str = ".md") -> bool:
    """Best-effort substring grep across all files under root."""
    if not root.is_dir():
        return False
    for p in root.rglob(f"*{suffix}"):
        if _grep_file(p, patterns):
            return True
    return False


def detect_in_kind(module: dict, kind: dict) -> bool:
    """Does `module` appear in the documentation surface `kind`?"""
    target = REPO_ROOT / kind["path"]
    patterns = module["patterns"]
    if kind["id"] == "sdd":
        return _grep_tree(target, patterns, ".md")
    if kind["id"] == "man-page":
        return _grep_tree(target, patterns, ".md") or \
               _grep_tree(target, patterns, ".1") or \
               _grep_tree(target, patterns, "")
    if kind["id"] == "readme":
        # Top-level README OR any subdirectory README.md mentioning the
        # module (operator/README.md counts for operator/* modules).
        if _grep_file(target, patterns):
            return True
        for p in REPO_ROOT.rglob("README.md"):
            if p == target:
                continue
            if _grep_file(p, patterns):
                return True
        return False
    # Single-file kinds (helptext, metric-inventory, mandate-row)
    return _grep_file(target, patterns)


def scan_module(module: dict) -> dict:
    """Return doc-coverage map for one module."""
    present = []
    missing = []
    for kind in DOC_KINDS:
        if detect_in_kind(module, kind):
            present.append(kind["id"])
        else:
            missing.append(kind["id"])
    return {
        "module": module["id"],
        "patterns_searched": module["patterns"],
        "present_in": present,
        "missing_from": missing,
        "doc_surface_count": len(present),
    }


# --- Verbs ---


def cmd_kinds(args) -> int:
    out = {"kinds": DOC_KINDS, "count": len(DOC_KINDS)}
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"── doc-coverage.kinds "
              f"({len(DOC_KINDS)} operator-named doc surfaces) ──")
        for k in DOC_KINDS:
            print(f"  {k['id']:18s} ({k['operator_named']!r}) — "
                  f"{k['label']}  [{k['path']}]")
    _emit_metric("kinds", "all", "ok")
    return 0


def cmd_modules(args) -> int:
    out = {
        "modules": [
            {"id": m["id"], "patterns": m["patterns"]}
            for m in MODULES
        ],
        "count": len(MODULES),
    }
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"── doc-coverage.modules "
              f"({len(MODULES)} tracked modules) ──")
        for m in MODULES:
            print(f"  {m['id']:25s} grep-patterns={m['patterns']}")
    _emit_metric("modules", "all", "ok")
    return 0


def _resolve_target_modules(arg_module: str | None) -> list[dict] | None:
    if not arg_module:
        return MODULES
    for m in MODULES:
        if m["id"] == arg_module:
            return [m]
    return None


def cmd_scan(args) -> int:
    target = _resolve_target_modules(args.module)
    if target is None:
        print(f"unknown module: {args.module!r}; "
              f"known: {MODULE_IDS}", file=sys.stderr)
        _emit_metric("scan", "any", "unknown-module")
        return 1
    rows = [scan_module(m) for m in target]
    out = {"scan": rows, "count": len(rows)}
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"── doc-coverage.scan "
              f"({len(rows)} module{'s' if len(rows)!=1 else ''}) ──")
        for r in rows:
            print(f"\n  {r['module']} "
                  f"({r['doc_surface_count']}/{len(DOC_KINDS)} docs)")
            for k in DOC_KINDS:
                mark = "✓" if k["id"] in r["present_in"] else "✗"
                print(f"    {mark} {k['id']:18s} {k['path']}")
    _emit_metric("scan", "all", "ok")
    return 0


def cmd_coverage(args) -> int:
    target = _resolve_target_modules(args.module)
    if target is None:
        print(f"unknown module: {args.module!r}", file=sys.stderr)
        _emit_metric("coverage", "any", "unknown-module")
        return 1
    rows = [scan_module(m) for m in target]
    rows.sort(key=lambda r: r["doc_surface_count"])  # smallest first
    matrix = []
    for r in rows:
        matrix.append({
            "module": r["module"],
            "doc_surface_count": r["doc_surface_count"],
            "cells": [
                {
                    "kind": k["id"],
                    "state": "shipped" if k["id"] in r["present_in"]
                            else "gap",
                }
                for k in DOC_KINDS
            ],
        })
    out = {"coverage": matrix, "count": len(matrix)}
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"── doc-coverage.coverage "
              f"({len(matrix)} module{'s' if len(matrix)!=1 else ''}; "
              f"sorted by largest gap first) ──")
        for r in matrix:
            print(f"\n  {r['module']} "
                  f"(docs={r['doc_surface_count']}/{len(DOC_KINDS)})")
            for c in r["cells"]:
                mark = "✓" if c["state"] == "shipped" else "✗"
                print(f"    {mark} {c['kind']}")
    _emit_metric("coverage", "all", "ok")
    return 0


def cmd_gaps(args) -> int:
    threshold = (args.threshold
                 if args.threshold is not None
                 else DEFAULT_THRESHOLD)
    target = _resolve_target_modules(args.module)
    if target is None:
        print(f"unknown module: {args.module!r}", file=sys.stderr)
        _emit_metric("gaps", "any", "unknown-module")
        return 1
    below = []
    for m in target:
        cov = scan_module(m)
        if cov["doc_surface_count"] < threshold:
            below.append({
                "module": m["id"],
                "doc_surface_count": cov["doc_surface_count"],
                "shortfall": threshold - cov["doc_surface_count"],
                "missing_from": cov["missing_from"],
            })
    below.sort(key=lambda r: r["shortfall"], reverse=True)
    out = {
        "threshold": threshold,
        "below_threshold": below,
        "count": len(below),
    }
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"── doc-coverage.gaps (threshold={threshold}, "
              f"{len(below)} module{'s' if len(below)!=1 else ''} "
              f"below) ──")
        for r in below:
            print(f"  ✗ {r['module']:25s} "
                  f"docs={r['doc_surface_count']}/{len(DOC_KINDS)} "
                  f"(short by {r['shortfall']}; missing: "
                  f"{','.join(r['missing_from'])})")
    result = "ok" if not below else "below-threshold"
    _emit_metric("gaps", "all", result)
    return 2 if below else 0


# --- R471 cross-repo selfdef DocManifest discovery ---


def load_selfdef_doc_manifests() -> tuple[list[dict], list[dict]]:
    """Read every .toml under SELFDEF_DOC_DIR.

    Cross-repo binding: SD-R-DOC-MANIFEST-1 (selfdef crate
    `selfdef-doc-manifest`).

    Returns (valid, errors). Each valid entry has:
      module, label, docs (list of {kind, state, path?, reason?}),
      shipped_count, waived_count, planned_count,
      source_repo='selfdef', manifest_path.
    """
    valid: list[dict] = []
    errors: list[dict] = []
    if not SELFDEF_DOC_DIR.is_dir():
        return valid, errors
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[import-not-found]
        except ImportError:
            errors.append({
                "path": str(SELFDEF_DOC_DIR),
                "error": "no TOML library available",
            })
            return valid, errors
    valid_kinds = set(DOC_KIND_IDS)
    for p in sorted(SELFDEF_DOC_DIR.glob("*.toml")):
        try:
            data = tomllib.loads(p.read_text(encoding="utf-8"))
        except (OSError, Exception) as e:  # noqa: BLE001
            errors.append({"path": str(p), "error": f"parse: {e}"})
            continue
        if data.get("schema_version") != 1:
            errors.append({
                "path": str(p),
                "error": "unsupported schema_version",
            })
            continue
        mod = data.get("module") or {}
        docs_in = data.get("docs") or []
        if not mod.get("id") or not docs_in:
            errors.append({
                "path": str(p),
                "error": "missing module.id or docs[]",
            })
            continue
        docs_out = []
        bad = None
        for d in docs_in:
            kind = d.get("kind")
            state = d.get("state")
            if kind not in valid_kinds:
                bad = f"unknown kind {kind!r}"
                break
            if state not in ("shipped", "waived", "planned"):
                bad = f"unknown state {state!r}"
                break
            # Defense-in-depth: re-enforce selfdef-side rules
            if state == "shipped" and not d.get("path"):
                bad = f"kind {kind!r} state=shipped without path"
                break
            if state == "waived" and not d.get("reason"):
                bad = f"kind {kind!r} state=waived without reason"
                break
            docs_out.append({
                "kind": kind,
                "state": state,
                "path": d.get("path"),
                "reason": d.get("reason"),
            })
        if bad:
            errors.append({"path": str(p), "error": bad})
            continue
        valid.append({
            "module": str(mod["id"]),
            "label": str(mod.get("label", mod["id"])),
            "docs": docs_out,
            "shipped_count": sum(
                1 for d in docs_out if d["state"] == "shipped"
            ),
            "waived_count": sum(
                1 for d in docs_out if d["state"] == "waived"
            ),
            "planned_count": sum(
                1 for d in docs_out if d["state"] == "planned"
            ),
            "source_repo": "selfdef",
            "manifest_path": str(p),
        })
    return valid, errors


def cmd_selfdef(args) -> int:
    """Scan SELFDEF_DOC_DIR for cross-repo DocManifests."""
    valid, errors = load_selfdef_doc_manifests()
    out = {
        "manifest_dir": str(SELFDEF_DOC_DIR),
        "discovered": valid,
        "errors": errors,
        "count": len(valid),
    }
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"── doc-coverage.selfdef "
              f"({len(valid)} selfdef DocManifest{'s' if len(valid)!=1 else ''} "
              f"under {SELFDEF_DOC_DIR}) ──")
        for m in valid:
            print(f"  ✓ {m['module']:25s} "
                  f"shipped={m['shipped_count']}/6 "
                  f"waived={m['waived_count']} "
                  f"planned={m['planned_count']}  ({m['label']})")
        for e in errors:
            print(f"  ✗ {e['path']}  {e['error']}")
    _emit_metric("selfdef", "any", "ok" if not errors else "issues")
    return 0


# --- Argparse ---


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="doc-coverage.py",
        description=(
            "R454 (E11.M1): operator §1g 'documentation through and "
            "through' — per-module documentation coverage scanner. "
            "Auto-discovers which of the 6 doc surfaces each "
            "operator-facing module is documented in."
        ),
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def _add_fmt(sp):
        g = sp.add_mutually_exclusive_group()
        g.add_argument("--json", dest="fmt", action="store_const",
                       const="json", default="human")
        g.add_argument("--human", dest="fmt", action="store_const",
                       const="human")

    sp_k = sub.add_parser("kinds",
                          help="enumerate the 6 doc surfaces")
    _add_fmt(sp_k)

    sp_m = sub.add_parser("modules",
                          help="list tracked operator-facing modules")
    _add_fmt(sp_m)

    sp_s = sub.add_parser("scan",
                          help="live grep of doc presence per module")
    sp_s.add_argument("--module", help="filter to one module")
    _add_fmt(sp_s)

    sp_c = sub.add_parser("coverage",
                          help="module × doc-surface matrix")
    sp_c.add_argument("--module", help="filter to one module")
    _add_fmt(sp_c)

    sp_g = sub.add_parser("gaps",
                          help="modules below doc threshold")
    sp_g.add_argument("--module", help="filter to one module")
    sp_g.add_argument("--threshold", type=int, default=None,
                      help=f"min doc kinds (default {DEFAULT_THRESHOLD})")
    _add_fmt(sp_g)

    sp_sd = sub.add_parser("selfdef",
                           help="discover selfdef DocManifest TOMLs "
                                "(SD-R-DOC-MANIFEST-1 cross-repo)")
    _add_fmt(sp_sd)

    args = p.parse_args(argv)
    return {
        "kinds": cmd_kinds,
        "modules": cmd_modules,
        "scan": cmd_scan,
        "coverage": cmd_coverage,
        "gaps": cmd_gaps,
        "selfdef": cmd_selfdef,
    }[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
