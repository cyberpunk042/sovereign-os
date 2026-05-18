#!/usr/bin/env python3
"""scripts/operator/compliance.py — R458.

§1g/§1h compliance dashboard aggregator. Consolidates the 4-tool
operator-§1g compliance instrument suite (R453 surface-map + R454
doc-coverage + R456 anti-minimization-audit + R457 ux-design-audit)
into a single screen.

Operator per §1g: "We do not minimize anything." This aggregator IS
the §1g operator-discoverable accountability dashboard.

4 underlying instruments (read-only delegation):
  R453 surface-map         runtime-surface coverage per module
  R454 doc-coverage        doc-surface coverage per module
  R456 anti-min-audit      cross-axis + source-code minimization patterns
  R457 ux-design-audit     6-dimension UX quality per module

CLI:
  compliance.py status [--json|--human]
      One-screen rollup: gap counts per instrument, top-priority
      modules (short on most axes simultaneously).

  compliance.py module <name> [--json|--human]
      Per-module rollup across all 4 instruments — surface count +
      doc count + UX score + minimize-phrase count in module files.

  compliance.py worst [--limit N] [--json|--human]
      Top-N modules by composite gap score (lower = worse).

  compliance.py history [--limit N] [--json|--human]
      Recent compliance snapshots from history journal (≤N entries).

  compliance.py snapshot [--apply --confirm-snapshot] [--json|--human]
      Record current compliance state to history journal at
      /var/lib/sovereign-os/compliance/snapshots.jsonl. Triple-gated.

Exit codes:
  0 ok
  1 unknown subcommand / module
  2 RESERVED (compliance audit explicitly never "fails" — operator
    decides; same reasoning as R456 anti-minimization-audit)

Layer B metric (SDD-016):
  sovereign_os_operator_compliance_query_total{verb,instrument,result}

Operator-environment env vars:
  SOVEREIGN_OS_COMPLIANCE_DRY_RUN  Logs intent; no file writes.
  SOVEREIGN_OS_DRY_RUN             Same effect (sovereign-wide).
  SOVEREIGN_OS_COMPLIANCE_OUT      Override snapshot output path
                                    (default: /var/lib/sovereign-os/
                                     compliance/snapshots.jsonl).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OP_DIR = REPO_ROOT / "scripts" / "operator"

DRY_RUN = (
    os.environ.get("SOVEREIGN_OS_DRY_RUN") == "1"
    or os.environ.get("SOVEREIGN_OS_COMPLIANCE_DRY_RUN") == "1"
)
METRICS_DIR = Path(
    os.environ.get(
        "SOVEREIGN_OS_TEXTFILE_DIR",
        "/var/lib/prometheus/node-exporter",
    )
)
SNAPSHOT_PATH = Path(
    os.environ.get(
        "SOVEREIGN_OS_COMPLIANCE_OUT",
        "/var/lib/sovereign-os/compliance/snapshots.jsonl",
    )
)

# HELP sovereign_os_operator_compliance_query_total compliance aggregator
# operator-verb call count (verb, instrument, result).
# TYPE sovereign_os_operator_compliance_query_total counter
METRIC_NAME = "sovereign_os_operator_compliance_query_total"

INSTRUMENTS = [
    {"id": "surface-map", "round": "R453",
     "script": "surface-map.py", "gap_verb": "gaps"},
    {"id": "doc-coverage", "round": "R454",
     "script": "doc-coverage.py", "gap_verb": "gaps"},
    {"id": "anti-minimization-audit", "round": "R456",
     "script": "anti-minimization-audit.py", "gap_verb": "report"},
    {"id": "ux-design-audit", "round": "R457",
     "script": "ux-design-audit.py", "gap_verb": "report"},
]
INSTRUMENT_IDS = [i["id"] for i in INSTRUMENTS]


def _emit_metric(verb: str, instrument: str, result: str) -> None:
    """Best-effort SDD-016 metric write; never raises."""
    if DRY_RUN:
        sys.stderr.write(
            f"  would emit: {METRIC_NAME}"
            f'{{verb="{verb}",instrument="{instrument}",'
            f'result="{result}"}} 1\n'
        )
        return
    try:
        METRICS_DIR.mkdir(parents=True, exist_ok=True)
        prom = METRICS_DIR / "sovereign-os-operator-compliance.prom"
        line = (
            f"{METRIC_NAME}"
            f'{{verb="{verb}",instrument="{instrument}",'
            f'result="{result}"}} 1\n'
        )
        tmp = prom.with_suffix(".prom.tmp")
        tmp.write_text(line)
        tmp.replace(prom)
    except OSError:
        pass


def _run_json(*args: str, timeout: int = 30) -> dict | None:
    """Run a subcommand and parse JSON. Return None on failure."""
    try:
        r = subprocess.run(
            ["python3", *args],
            capture_output=True, text=True, timeout=timeout,
        )
        # exit-2 from gaps/report is the operator-discoverable signal
        # but the JSON payload is still valid
        if r.returncode not in (0, 2):
            return None
        return json.loads(r.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None


def collect_status() -> dict:
    """Aggregate gap state from all 4 instruments. Read-only."""
    surface = _run_json(str(OP_DIR / "surface-map.py"), "gaps",
                        "--json", timeout=15)
    doc = _run_json(str(OP_DIR / "doc-coverage.py"), "gaps",
                    "--json", timeout=30)
    amin = _run_json(str(OP_DIR / "anti-minimization-audit.py"),
                     "report", "--json", timeout=120)
    ux = _run_json(str(OP_DIR / "ux-design-audit.py"), "report",
                   "--json", timeout=30)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "surface_map": {
            "available": surface is not None,
            "gaps_count": (surface or {}).get("count", 0),
            "below_threshold": (surface or {}).get(
                "below_threshold", []
            ),
        },
        "doc_coverage": {
            "available": doc is not None,
            "gaps_count": (doc or {}).get("count", 0),
            "below_threshold": (doc or {}).get(
                "below_threshold", []
            ),
        },
        "anti_minimization_audit": {
            "available": amin is not None,
            "summary": (amin or {}).get("summary", {}),
            "total": (amin or {}).get("total", 0),
        },
        "ux_design_audit": {
            "available": ux is not None,
            "below_threshold_count": (ux or {}).get("count", 0),
            "below_threshold": (ux or {}).get(
                "below_threshold", []
            ),
        },
    }


def compute_worst(status: dict) -> list[dict]:
    """Rank modules by composite gap score (lower = worse)."""
    scores: dict[str, dict] = {}

    def _ensure(mid: str):
        if mid not in scores:
            scores[mid] = {
                "module": mid,
                "surface_shortfall": 0,
                "doc_shortfall": 0,
                "ux_shortfall": 0,
                "in_surface_gaps": False,
                "in_doc_gaps": False,
                "in_ux_gaps": False,
            }
        return scores[mid]

    for g in status["surface_map"]["below_threshold"]:
        e = _ensure(g["module"])
        e["surface_shortfall"] = g.get("shortfall", 0)
        e["in_surface_gaps"] = True
    for g in status["doc_coverage"]["below_threshold"]:
        e = _ensure(g["module"])
        e["doc_shortfall"] = g.get("shortfall", 0)
        e["in_doc_gaps"] = True
    for g in status["ux_design_audit"]["below_threshold"]:
        e = _ensure(g["module"])
        e["ux_shortfall"] = g.get("shortfall", 0)
        e["in_ux_gaps"] = True

    ranked = list(scores.values())
    for e in ranked:
        # Composite score: more axes flagged = worse. Higher number
        # = worse module.
        e["composite_shortfall"] = (
            e["surface_shortfall"]
            + e["doc_shortfall"]
            + e["ux_shortfall"]
        )
        e["axes_flagged"] = sum([
            e["in_surface_gaps"],
            e["in_doc_gaps"],
            e["in_ux_gaps"],
        ])
    ranked.sort(
        key=lambda e: (e["axes_flagged"], e["composite_shortfall"]),
        reverse=True,
    )
    return ranked


# --- Verbs ---


def cmd_status(args) -> int:
    status = collect_status()
    if args.fmt == "json":
        print(json.dumps(status, indent=2))
    else:
        ts = status["timestamp"]
        print(f"── compliance.status @ {ts} ──")
        sm = status["surface_map"]
        print(f"  surface-map       (R453)  "
              f"{'✓' if sm['available'] else '✗'} "
              f"{sm['gaps_count']} module(s) below default threshold")
        dc = status["doc_coverage"]
        print(f"  doc-coverage      (R454)  "
              f"{'✓' if dc['available'] else '✗'} "
              f"{dc['gaps_count']} module(s) below default threshold")
        am = status["anti_minimization_audit"]
        if am["available"]:
            print(f"  anti-min-audit    (R456)  ✓ "
                  f"{am['total']} matches across 8 patterns")
            for p, n in am["summary"].items():
                mark = "✗" if n > 0 else "✓"
                print(f"    {mark} {p:22s} {n}")
        else:
            print("  anti-min-audit    (R456)  ✗ unavailable")
        ux = status["ux_design_audit"]
        print(f"  ux-design-audit   (R457)  "
              f"{'✓' if ux['available'] else '✗'} "
              f"{ux['below_threshold_count']} module(s) below default "
              f"threshold")
    _emit_metric("status", "all", "ok")
    return 0


def cmd_module(args) -> int:
    name = args.name
    status = collect_status()
    # Per-module rollup
    surface_gap = next(
        (g for g in status["surface_map"]["below_threshold"]
         if g["module"] == name),
        None,
    )
    doc_gap = next(
        (g for g in status["doc_coverage"]["below_threshold"]
         if g["module"] == name),
        None,
    )
    ux_gap = next(
        (g for g in status["ux_design_audit"]["below_threshold"]
         if g["module"] == name),
        None,
    )
    out = {
        "module": name,
        "surface_gap": surface_gap,
        "doc_gap": doc_gap,
        "ux_gap": ux_gap,
    }
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"── compliance.module {name} ──")
        print(f"  surface-map (R453):  "
              f"{'✗ ' + str(surface_gap) if surface_gap else '✓ no gap'}")
        print(f"  doc-coverage (R454): "
              f"{'✗ ' + str(doc_gap) if doc_gap else '✓ no gap'}")
        print(f"  ux-design-audit (R457): "
              f"{'✗ ' + str(ux_gap) if ux_gap else '✓ no gap'}")
    _emit_metric("module", "all", "ok")
    return 0


def cmd_worst(args) -> int:
    limit = args.limit or 10
    status = collect_status()
    ranked = compute_worst(status)
    out = {"worst": ranked[:limit], "count": len(ranked[:limit])}
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"── compliance.worst (top {limit} by composite gap) ──")
        if not ranked:
            print("  ✓ no modules below any default threshold — "
                  "operator §1g standards met across the board")
        else:
            for e in ranked[:limit]:
                axes = []
                if e["in_surface_gaps"]:
                    axes.append("surface")
                if e["in_doc_gaps"]:
                    axes.append("doc")
                if e["in_ux_gaps"]:
                    axes.append("ux")
                print(f"  ✗ {e['module']:25s} "
                      f"axes-flagged={e['axes_flagged']} "
                      f"composite-shortfall={e['composite_shortfall']} "
                      f"({','.join(axes)})")
    _emit_metric("worst", "all", "ok")
    return 0


def cmd_history(args) -> int:
    limit = args.limit or 10
    snapshots = []
    if SNAPSHOT_PATH.is_file():
        try:
            for line in SNAPSHOT_PATH.read_text(
                encoding="utf-8"
            ).splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    snapshots.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        except OSError:
            pass
    snapshots = snapshots[-limit:]
    out = {
        "history": snapshots,
        "count": len(snapshots),
        "path": str(SNAPSHOT_PATH),
    }
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"── compliance.history ({len(snapshots)} entries from "
              f"{SNAPSHOT_PATH}) ──")
        if not snapshots:
            print("  (no snapshots — use `compliance snapshot` to record one)")
        else:
            for s in snapshots:
                ts = s.get("timestamp", "?")
                sm = s.get("surface_map", {}).get("gaps_count", 0)
                dc = s.get("doc_coverage", {}).get("gaps_count", 0)
                am = s.get("anti_minimization_audit",
                           {}).get("total", 0)
                ux = (s.get("ux_design_audit", {})
                      .get("below_threshold_count", 0))
                print(f"  {ts}  surface={sm} doc={dc} amin={am} ux={ux}")
    _emit_metric("history", "all", "ok")
    return 0


def cmd_snapshot(args) -> int:
    """Record current compliance state to history journal.
    Triple-gated: --apply + --confirm-snapshot."""
    status = collect_status()

    # Triple-gate: --apply + --confirm-snapshot
    if not (args.apply and args.confirm_snapshot):
        out = {
            "preview": True,
            "would_write_to": str(SNAPSHOT_PATH),
            "next_action": (
                "Run: sovereign-osctl compliance snapshot "
                "--apply --confirm-snapshot"
            ),
            "snapshot": status,
        }
        if args.fmt == "json":
            print(json.dumps(out, indent=2))
        else:
            print(f"── compliance.snapshot PREVIEW ──")
            print(f"  would write to: {SNAPSHOT_PATH}")
            print(f"  next: --apply --confirm-snapshot to commit")
        _emit_metric("snapshot", "all", "preview")
        return 0

    if DRY_RUN:
        if args.fmt == "json":
            status["dry_run"] = True
            print(json.dumps(status, indent=2))
        else:
            print(f"── compliance.snapshot DRY-RUN ──")
            print(f"  would write to: {SNAPSHOT_PATH}")
        _emit_metric("snapshot", "all", "dry-run")
        return 0

    try:
        SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with SNAPSHOT_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(status) + "\n")
    except OSError as e:
        print(f"snapshot write failed: {e}", file=sys.stderr)
        _emit_metric("snapshot", "all", "write-failed")
        return 1

    out = {"applied": True, "wrote_to": str(SNAPSHOT_PATH),
           "snapshot_timestamp": status["timestamp"]}
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"── compliance.snapshot APPLIED ──")
        print(f"  wrote: {SNAPSHOT_PATH}")
    _emit_metric("snapshot", "all", "applied")
    return 0


# --- Argparse ---


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="compliance.py",
        description=(
            "R458: operator §1g/§1h compliance dashboard aggregator. "
            "Consolidates R453 + R454 + R456 + R457 into a single "
            "operator-discoverable view of §1g compliance state."
        ),
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def _add_fmt(sp):
        g = sp.add_mutually_exclusive_group()
        g.add_argument("--json", dest="fmt", action="store_const",
                       const="json", default="human")
        g.add_argument("--human", dest="fmt", action="store_const",
                       const="human")

    sp_st = sub.add_parser("status",
                           help="one-screen 4-instrument rollup")
    _add_fmt(sp_st)
    sp_mod = sub.add_parser("module",
                            help="per-module rollup across 4 instruments")
    sp_mod.add_argument("name")
    _add_fmt(sp_mod)
    sp_w = sub.add_parser("worst",
                          help="top-N modules by composite gap")
    sp_w.add_argument("--limit", type=int, default=None)
    _add_fmt(sp_w)
    sp_h = sub.add_parser("history",
                          help="recent compliance snapshots")
    sp_h.add_argument("--limit", type=int, default=None)
    _add_fmt(sp_h)
    sp_sn = sub.add_parser("snapshot",
                           help="record current state to history "
                                "journal (triple-gated)")
    sp_sn.add_argument("--apply", action="store_true")
    sp_sn.add_argument("--confirm-snapshot", action="store_true")
    _add_fmt(sp_sn)

    args = p.parse_args(argv)
    return {
        "status": cmd_status,
        "module": cmd_module,
        "worst": cmd_worst,
        "history": cmd_history,
        "snapshot": cmd_snapshot,
    }[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
