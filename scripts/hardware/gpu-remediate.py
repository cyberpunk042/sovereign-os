#!/usr/bin/env python3
"""scripts/hardware/gpu-remediate.py — R249 (SDD-026 Z-5 closure).

Operator-named (verbatim): "with a warning if the RTX 4090 which
should be sliglly reduce which isn't and things like this that warn
deviance from 'perfertion'".

R219 (gpu-watch) DETECTS GPU power-limit deviance + emits actionable
`nvidia-smi -pl <safe>` fix commands. R249 closes the loop: read the
R219 analysis JSON + EXECUTE the fix commands automatically.

Cycle-8 doctrine: write verbs require operator opt-in. By default
this script DRY-RUNs (prints what it would do) without writing. The
`--apply` flag actually runs nvidia-smi; non-root rejection is loud
and operator-readable.

CLI:
  gpu-remediate.py                 dry-run (prints planned fixes, rc=0)
  gpu-remediate.py --apply         actually invoke nvidia-smi (root)
  gpu-remediate.py --json          machine-readable plan + outcomes
  gpu-remediate.py --policy P      override gpu-policy.toml path

Exit codes:
  0  no deviance OR remediation succeeded
  1  apply was attempted but ≥1 fix failed
  2  usage error / nvidia-smi unavailable / non-root with --apply
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]


def _summary(dry: bool, to_fix: list, results: list) -> str:
    if dry:
        return f"{len(to_fix)} GPU(s) deviating; dry-run"
    applied = sum(1 for r in results if r["outcome"] == "ok")
    return f"{len(to_fix)} GPU(s) deviating; applied {applied}/{len(to_fix)}"


def fetch_analysis(policy_arg: list[str]) -> dict[str, Any] | None:
    """Shell `gpu-watch.py --json` and parse the analysis dict."""
    bin_path = REPO_ROOT / "scripts" / "hardware" / "gpu-watch.py"
    if not bin_path.exists():
        return None
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), "--json", *policy_arg],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if r.returncode not in (0, 1):
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def cmd_main(args: argparse.Namespace) -> int:
    policy_arg = ["--policy", str(args.policy)] if args.policy else []
    analysis = fetch_analysis(policy_arg)
    if analysis is None:
        print("ERROR could not fetch gpu-watch analysis", file=sys.stderr)
        return 2

    # Collect the deviating GPU rows with non-null fix_command.
    to_fix: list[dict[str, Any]] = []
    for g in analysis.get("gpus", []):
        if g.get("fix_command"):
            to_fix.append({
                "idx": g["idx"],
                "name": g["name"],
                "current_limit_watts": g.get("power_limit_watts"),
                "deviance_watts": g.get("deviance_watts"),
                "policy_hint": g.get("policy_hint"),
                "fix_command": g["fix_command"],
            })

    dry = not args.apply
    nvidia_smi_present = shutil.which("nvidia-smi") is not None

    results: list[dict[str, Any]] = []
    failures = 0
    if not to_fix:
        # Nothing to do — short-circuit.
        report = {
            "round": "R249",
            "vector": "SDD-026 Z-5 closure (gpu remediate)",
            "dry_run": dry,
            "to_fix_count": 0,
            "results": [],
            "summary": "no deviance — every policed GPU is on operator-set safe_limit",
        }
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f"── R249 sovereign-os gpu-remediate ──")
            print("  (no deviance — nothing to remediate)")
        return 0

    # Apply mode validation.
    if not dry:
        if not nvidia_smi_present:
            print("ERROR nvidia-smi not on PATH", file=sys.stderr)
            return 2
        if os.geteuid() != 0:
            # Print actionable commands instead of failing.
            cmds = [g["fix_command"] for g in to_fix]
            print(
                "# Not running as root — to apply these fixes:\n  "
                + "\n  ".join(cmds),
                file=sys.stderr,
            )
            return 2

    for g in to_fix:
        cmd_str: str = g["fix_command"]
        # fix_command shape: "nvidia-smi -i N -pl <safe>"
        argv = cmd_str.split()
        if dry:
            results.append({
                "idx": g["idx"], "name": g["name"], "command": cmd_str,
                "outcome": "dry-run", "detail": "would exec",
            })
            continue
        try:
            r = subprocess.run(argv, capture_output=True, text=True, timeout=8, check=False)
            if r.returncode != 0:
                failures += 1
                results.append({
                    "idx": g["idx"], "name": g["name"], "command": cmd_str,
                    "outcome": "failed",
                    "detail": (r.stderr.strip() or f"rc={r.returncode}")[:200],
                })
            else:
                results.append({
                    "idx": g["idx"], "name": g["name"], "command": cmd_str,
                    "outcome": "ok", "detail": r.stdout.strip()[:200],
                })
        except (subprocess.TimeoutExpired, OSError) as e:
            failures += 1
            results.append({
                "idx": g["idx"], "name": g["name"], "command": cmd_str,
                "outcome": "exec-error", "detail": str(e),
            })

    report = {
        "round": "R249",
        "vector": "SDD-026 Z-5 closure (gpu remediate)",
        "dry_run": dry,
        "to_fix_count": len(to_fix),
        "results": results,
        "applied_count": sum(1 for r in results if r["outcome"] == "ok"),
        "failed_count": failures,
        "summary": _summary(dry, to_fix, results),
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"── R249 sovereign-os gpu-remediate ──")
        for r in results:
            mark = {"ok": "OK", "dry-run": "DRY", "failed": "FAIL",
                    "exec-error": "ERR"}.get(r["outcome"], "?")
            print(
                f"  [{mark}] idx={r['idx']} {r['name']}  → {r['command']}  "
                f"({r['detail']})"
            )
        print()
        print(f"  {report['summary']}")
    return 1 if failures else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gpu-remediate.py",
        description="R249 (SDD-026 Z-5 closure) — auto-apply R219 fix commands.",
    )
    p.add_argument("--policy", type=Path)
    p.add_argument("--apply", action="store_true",
                   help="actually run nvidia-smi -pl (default is dry-run)")
    p.add_argument("--json", action="store_true")
    return p


def main(argv: list[str]) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2
    return cmd_main(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
