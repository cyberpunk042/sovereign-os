#!/usr/bin/env python3
"""scripts/diagnostics/assistant-next-steps.py — R282 (E5.M10).

Operator-named (§1a verbatim):
  "full IAC and User Experience and Developer experience and an
   assistant feel and clear path and options and modules combo
   features and super-features"

R266 ships `diagnose` (cross-axis analyzer). R234 ships `insights`
(fs+log synthesizer). R263/R275/R268 ship per-stack advisors. R273
ships severity escalation. EVERY advisor surfaces `action` strings
on each finding — but the operator has to READ each card to find
the next-best step.

R282 closes E5.M10: a `next-steps` synthesizer that walks EVERY
advisor surface + extracts each finding's `action`, ranks them by
operator-impact (critical > attention > informational; touching
hardware > touching config > informational only), and emits a
SINGLE prioritized "do this next" list with operator-readable
explanations.

Also surfaces "modules combo features" / "super-features": curated
operator-packs that flip MULTIPLE knobs at once (e.g. "inference-
burst pack" = kernel-tuning inference-burst preset + cpu-mode
performance + GPU power limit + thermal headroom check).

CLI:
  assistant-next-steps.py next [--limit N] [--severity S] [--json]
                                          aggregated next-best-step list
  assistant-next-steps.py packs [--json]   curated operator-packs
                                          (combo-features / super-features)
  assistant-next-steps.py apply-pack <name> [--dry-run] [--json]
                                          execute the pack's steps

Exit codes:
  0  rendered OR pack-apply succeeded
  1  ≥1 critical step queued OR apply partially failed
  2  usage error
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

SEVERITY_RANK = {"critical": 0, "attention": 1, "informational": 2}


def _call(argv: list[str], timeout: int = 25) -> dict[str, Any] | None:
    if not Path(argv[0]).exists():
        return None
    try:
        r = subprocess.run(
            [sys.executable, *argv], capture_output=True, text=True,
            timeout=timeout, check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if r.returncode not in (0, 1):
        return None
    try:
        return json.loads(r.stdout) or {}
    except json.JSONDecodeError:
        return None


def gather_diagnose_findings() -> list[dict[str, Any]]:
    """Pull cross-axis findings via R266 diagnose."""
    bin_path = REPO_ROOT / "scripts" / "diagnostics" / "doctor.py"
    d = _call([str(bin_path), "run", "--all", "--json"])
    if not d:
        return []
    return d.get("findings") or []


def gather_per_axis_advisories() -> list[dict[str, Any]]:
    """Pull standalone per-axis advisors that diagnose may not include."""
    sources = [
        # (name, script-path, args, epic/module, severity-key, advisory-key)
        ("ram-advisor",     REPO_ROOT / "scripts/hardware/ram-advisor.py",     ["advisory", "--json"], "E1.M16", "verdict", "advisories"),
        ("zmm-ternary",     REPO_ROOT / "scripts/hardware/zmm-ternary-probe.py", ["advisory", "--json"], "E1.M18", "fit", "advisories"),
        ("wasm-aot",        REPO_ROOT / "scripts/hardware/wasm-aot-enforcer.py", ["advisory", "--json"], "E1.M17", "fit", "advisories"),
        ("gpu-card",        REPO_ROOT / "scripts/hardware/gpu-card-advisor.py", ["advisories", "--json"], "E1.M13", None, None),
        ("memory-pressure", REPO_ROOT / "scripts/hardware/memory-pressure.py", ["status", "--json"], "E1.M15", "verdict", "advisories"),
        ("dns-advisor",     REPO_ROOT / "scripts/network/dns-advisor.py",     ["status", "--json"], "E3.M4", "posture", "advisories"),
        ("net-perf",        REPO_ROOT / "scripts/network/perf-baseline.py",   ["drift", "--json"], "E3.M6", "verdict", None),
    ]
    findings: list[dict[str, Any]] = []
    for (name, path, args, module, sev_key, adv_key) in sources:
        if not path.exists():
            continue
        d = _call([str(path), *args])
        if not d:
            continue
        sev_raw = (d.get(sev_key) if sev_key else None) or "informational"
        # Map non-standard severity vocab to our trichotomy.
        severity = {
            "critical": "critical", "degraded": "critical",
            "attention": "attention", "warn": "attention",
            "drifting": "attention",
            "not-supported": "attention", "partial": "attention",
            "ok": "informational", "ready": "informational",
        }.get(sev_raw, "informational")
        # Gather string advisories OR the special results-list shapes.
        adv_list: list[str] = []
        if adv_key and isinstance(d.get(adv_key), list):
            adv_list = [a if isinstance(a, str) else a.get("message", str(a))
                        for a in d[adv_key]]
        # gpu-card returns results[*].live_findings (different shape).
        if name == "gpu-card" and isinstance(d.get("results"), list):
            for r in d["results"]:
                for lf in r.get("live_findings") or []:
                    adv_list.append(f"{r.get('matched_key','')}: {lf}")
        for adv in adv_list:
            findings.append({
                "source": name,
                "module": module,
                "severity": severity,
                "title": adv[:120],
                "detail": adv,
                "action": adv,  # advisories are themselves actionable
            })
    return findings


# Curated operator-packs — combo-features / super-features per §1a.
PACKS: dict[str, dict[str, Any]] = {
    "inference-burst": {
        "summary": "Maximum-throughput AI inference pack",
        "operator_note": (
            "Pegged-clock posture for sustained LLM serving + ternary "
            "inference. Combines kernel-tuning + CPU mode + GPU power "
            "headroom check. Operator runs this BEFORE starting long "
            "fine-tunes OR large-batch serving."
        ),
        "steps": [
            {"kind": "advisory", "verb": "sovereign-osctl kernel apply inference-burst --dry-run"},
            {"kind": "advisory", "verb": "sovereign-osctl cpu-mode set performance"},
            {"kind": "advisory", "verb": "sovereign-osctl gpu-card-advisor dual-card"},
            {"kind": "advisory", "verb": "sovereign-osctl power-status budget"},
            {"kind": "advisory", "verb": "sovereign-osctl thermals --json"},
        ],
    },
    "headless-server": {
        "summary": "Audit-friendly headless-server posture pack",
        "operator_note": (
            "Conservative network + kernel posture for SSH-only servers. "
            "Useful when sovereign-os is the operator's remote inference "
            "backend (not the daily-driver workstation)."
        ),
        "steps": [
            {"kind": "advisory", "verb": "sovereign-osctl kernel apply server-headless --dry-run"},
            {"kind": "advisory", "verb": "sovereign-osctl reverse-proxy status"},
            {"kind": "advisory", "verb": "sovereign-osctl services failures"},
            {"kind": "advisory", "verb": "sovereign-osctl dns-advisor status"},
        ],
    },
    "low-power": {
        "summary": "Fanless/battery posture pack",
        "operator_note": (
            "Drops sustained TDP + tunes PCIe ASPM. Use on battery / "
            "quiet hours when no inference workload is queued."
        ),
        "steps": [
            {"kind": "advisory", "verb": "sovereign-osctl kernel apply low-power --dry-run"},
            {"kind": "advisory", "verb": "sovereign-osctl cpu-mode set powersave"},
            {"kind": "advisory", "verb": "sovereign-osctl gpu-mode show"},
            {"kind": "advisory", "verb": "sovereign-osctl power-status psu"},
        ],
    },
    "spec-conformance": {
        "summary": "Master-spec §1-§22 conformance audit pack",
        "operator_note": (
            "Re-validates the host against the operator's master spec: "
            "256 GB RAM + ZFS ARC clamp + XMP/EXPO + AVX-512 VNNI + "
            "BIOS hint conformance + PCIe lane fabric + Wasm-AOT env."
        ),
        "steps": [
            {"kind": "advisory", "verb": "sovereign-osctl ram-advisor status"},
            {"kind": "advisory", "verb": "sovereign-osctl memory-profile status"},
            {"kind": "advisory", "verb": "sovereign-osctl bios-info advisories"},
            {"kind": "advisory", "verb": "sovereign-osctl avx512-advisor workloads"},
            {"kind": "advisory", "verb": "sovereign-osctl pcie-policy status"},
            {"kind": "advisory", "verb": "sovereign-osctl wasm-aot status"},
            {"kind": "advisory", "verb": "sovereign-osctl zmm-ternary status"},
        ],
    },
    "graceful-shutdown-rehearsal": {
        "summary": "Rehearse the R262 schedule-manifest drain WITHOUT poweroff",
        "operator_note": (
            "Dry-runs the graceful-shutdown sequence; operator verifies "
            "the drain order + per-step durations + each unit's stop "
            "behavior BEFORE counting on it during a UPS event."
        ),
        "steps": [
            {"kind": "advisory", "verb": "sovereign-osctl power-shutdown plan"},
            {"kind": "advisory", "verb": "sovereign-osctl power-shutdown apply --dry-run"},
            {"kind": "advisory", "verb": "sovereign-osctl service-deps drain"},
        ],
    },
}


def cmd_next(args: argparse.Namespace) -> int:
    diagnose = gather_diagnose_findings()
    per_axis = gather_per_axis_advisories()
    # Dedup by (source, title) — diagnose may pull from the same sub-probe.
    seen: set[tuple[str, str]] = set()
    merged: list[dict[str, Any]] = []
    for f in diagnose + per_axis:
        key = (f.get("source", "?"), (f.get("title") or "")[:80])
        if key in seen:
            continue
        seen.add(key)
        merged.append(f)
    # Severity filter.
    if args.severity:
        min_rank = SEVERITY_RANK[args.severity]
        merged = [f for f in merged if SEVERITY_RANK.get(f.get("severity", "informational"), 9) <= min_rank]
    # Sort: critical > attention > informational
    merged.sort(key=lambda f: SEVERITY_RANK.get(f.get("severity", "informational"), 9))
    if args.limit and not args.all:
        merged_render = merged[:args.limit]
    else:
        merged_render = merged
    counts = {
        "critical": sum(1 for f in merged if f.get("severity") == "critical"),
        "attention": sum(1 for f in merged if f.get("severity") == "attention"),
        "informational": sum(1 for f in merged if f.get("severity") == "informational"),
        "total": len(merged),
    }
    out = {
        "round": "R282",
        "vector": "E5.M10 (assistant-next-steps)",
        "evaluated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "counts": counts,
        "next_steps": merged_render,
        "rendered_count": len(merged_render),
        "total_count": len(merged),
    }
    rc = 1 if counts["critical"] > 0 else 0
    if args.json:
        print(json.dumps(out, indent=2))
        return rc
    print(f"── R282 sovereign-os assistant-next-steps (E5.M10) ──")
    print(f"  evaluated:  {out['evaluated_at']}")
    print(f"  totals:     critical={counts['critical']} attention={counts['attention']} informational={counts['informational']} total={counts['total']}")
    print(f"  rendering:  {len(merged_render)} of {len(merged)}")
    if not merged_render:
        print("\n  (no next steps queued — host posture is uncontroversial)")
        return rc
    glyph = {"critical": "⛔", "attention": "⚠", "informational": "·"}
    print()
    for i, f in enumerate(merged_render, start=1):
        g = glyph.get(f.get("severity", "informational"), "?")
        print(f"  {i:>3}. {g} [{f.get('severity'):13s}] [{f.get('module','?')}] {f.get('title','')}")
        if f.get("action") and f.get("action") != f.get("title"):
            print(f"        action: {f['action']}")
        print(f"        source: {f.get('source')}")
    return rc


def cmd_packs(args: argparse.Namespace) -> int:
    rows = [
        {
            "name": name,
            "summary": meta["summary"],
            "operator_note": meta["operator_note"],
            "step_count": len(meta["steps"]),
        }
        for name, meta in PACKS.items()
    ]
    out = {
        "round": "R282",
        "vector": "E5.M10 (operator-packs)",
        "pack_count": len(rows),
        "packs": rows,
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"── R282 assistant-next-steps packs (E5.M10) ──")
    for r in rows:
        print(f"\n  {r['name']}  ({r['step_count']} steps)")
        print(f"    summary:  {r['summary']}")
        print(f"    note:     {r['operator_note']}")
    return 0


def cmd_apply_pack(args: argparse.Namespace) -> int:
    if args.name not in PACKS:
        print(f"ERROR unknown pack {args.name!r}; available: {sorted(PACKS)}", file=sys.stderr)
        return 2
    pack = PACKS[args.name]
    dry = bool(args.dry_run) or os.environ.get("SOVEREIGN_OS_DRY_RUN")
    out: dict[str, Any] = {
        "round": "R282",
        "vector": "E5.M10 (apply-pack)",
        "pack": args.name,
        "dry_run": bool(dry),
        "summary": pack["summary"],
        "results": [],
    }
    failed = 0
    for step in pack["steps"]:
        # cycle-8 doctrine: only `kind=advisory` packs (informational
        # surface). Future round adds kind=write packs gated by
        # SOVEREIGN_OS_CONFIRM_DESTROY.
        kind = step.get("kind", "advisory")
        verb = step.get("verb", "")
        if dry or kind == "advisory":
            out["results"].append({
                "kind": kind,
                "verb": verb,
                "outcome": "would-run" if dry else "advisory-shown",
                "detail": (
                    "advisory pack — operator runs the command manually. "
                    "Use SOVEREIGN_OS_DRY_RUN=1 to suppress execution "
                    "context."
                ),
            })
        else:
            out["results"].append({
                "kind": kind,
                "verb": verb,
                "outcome": "skipped",
                "detail": f"kind={kind!r} not supported in cycle-8 (advisory only)",
            })
    if args.json:
        print(json.dumps(out, indent=2))
        return 1 if failed else 0
    print(f"── R282 assistant-next-steps apply-pack {args.name} (E5.M10) ──")
    print(f"  summary: {pack['summary']}")
    print(f"  dry-run: {bool(dry)}")
    print()
    for i, r in enumerate(out["results"], start=1):
        mark = {"would-run": "DRY", "advisory-shown": "ADV",
                "ok": "OK", "failed": "FAIL", "skipped": "SKP"}.get(r["outcome"], "?")
        print(f"  {i:>3}. [{mark}] {r['verb']}")
    return 1 if failed else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="assistant-next-steps.py",
        description="R282 (E5.M10) — operator 'assistant feel' next-best-step + curated packs.",
    )
    sub = p.add_subparsers(dest="verb", required=True)
    pn = sub.add_parser("next", help="aggregated next-best-step list")
    pn.add_argument("--severity", choices=["critical", "attention", "informational"])
    pn.add_argument("--limit", type=int, default=15)
    pn.add_argument("--all", action="store_true", help="render every step (ignore --limit)")
    pn.add_argument("--json", action="store_true")
    pn.set_defaults(func=cmd_next)
    pp = sub.add_parser("packs", help="curated operator-packs (combo / super features)")
    pp.add_argument("--json", action="store_true")
    pp.set_defaults(func=cmd_packs)
    pa = sub.add_parser("apply-pack", help="emit / execute a pack's step list")
    pa.add_argument("name")
    pa.add_argument("--dry-run", action="store_true")
    pa.add_argument("--json", action="store_true")
    pa.set_defaults(func=cmd_apply_pack)
    return p


def main(argv: list[str]) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
