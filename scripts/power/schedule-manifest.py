#!/usr/bin/env python3
"""scripts/power/schedule-manifest.py — R262 (SDD-029 R262 closure).

Operator-named (verbatim, 2026-05-17 expansion): "graceful on all
levels, orderly" — the operator wants a SCHEDULE manifest that
describes exactly which services drain in which order, with which
timeouts, before the host powers off.

R253 ships the per-minute UPS-battery shutdown guard. R262 closes the
gap between "we decided to shut down" and "systemctl poweroff":
operators declare a YAML/TOML manifest of services to gracefully stop,
optional pre-shutdown commands (e.g. flush a queue), and a final
poweroff step. The verb DRY-RUN-by-default; --apply gates real
execution behind explicit operator confirmation.

Manifest schema (TOML):
  [meta]
  description = "default headless-server graceful shutdown"
  total_budget_seconds = 180

  [[steps]]
  name      = "drain-inference-router"
  kind      = "systemctl-stop"     # systemctl-stop / shell / sleep
  target    = "sovereign-inference-router.service"
  timeout_s = 30
  fail_action = "continue"          # continue / abort

  [[steps]]
  name      = "flush-jsonl-buffers"
  kind      = "shell"
  cmd       = "sync"
  timeout_s = 10

  [[steps]]
  name      = "poweroff"
  kind      = "shell"
  cmd       = "systemctl poweroff"
  timeout_s = 60

CLI:
  schedule-manifest.py list [--json]              show declared steps
  schedule-manifest.py plan [--manifest P] [--json]
                                                  print the drain plan
                                                  (rc=0; doesn't execute)
  schedule-manifest.py apply [--manifest P] [--confirm] [--json]
                                                  execute steps in order;
                                                  --confirm required to run
                                                  destructive kinds

Exit codes:
  0  rendered / apply succeeded
  1  apply partially failed (some steps errored — see report)
  2  usage error (manifest missing, --apply without --confirm, etc.)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = Path("/etc/sovereign-os/shutdown-manifest.toml")
DEV_MANIFEST = REPO_ROOT / "config" / "shutdown-manifest.toml.example"

ALLOWED_KINDS = {"systemctl-stop", "shell", "sleep"}


def resolve_manifest_path(explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit if explicit.exists() else None
    env = os.environ.get("SOVEREIGN_OS_SHUTDOWN_MANIFEST")
    if env:
        p = Path(env)
        return p if p.exists() else None
    if DEFAULT_MANIFEST.exists():
        return DEFAULT_MANIFEST
    if DEV_MANIFEST.exists():
        return DEV_MANIFEST
    return None


def load_manifest(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"_source": "(missing)", "meta": {}, "steps": []}
    try:
        with path.open("rb") as fh:
            doc = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as e:
        return {"_source": str(path), "_parse_error": str(e), "meta": {}, "steps": []}
    if "meta" not in doc:
        doc["meta"] = {}
    if "steps" not in doc:
        doc["steps"] = []
    doc["_source"] = str(path)
    return doc


def validate_step(idx: int, step: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not step.get("name"):
        errors.append(f"step[{idx}]: missing 'name'")
    kind = step.get("kind")
    if kind not in ALLOWED_KINDS:
        errors.append(f"step[{idx}].kind={kind!r} not in {sorted(ALLOWED_KINDS)}")
    if kind == "systemctl-stop" and not step.get("target"):
        errors.append(f"step[{idx}]: systemctl-stop requires 'target'")
    if kind == "shell" and not step.get("cmd"):
        errors.append(f"step[{idx}]: shell requires 'cmd'")
    if kind == "sleep" and step.get("seconds") is None:
        errors.append(f"step[{idx}]: sleep requires 'seconds'")
    if "timeout_s" in step and not isinstance(step["timeout_s"], (int, float)):
        errors.append(f"step[{idx}].timeout_s must be number")
    fa = step.get("fail_action", "continue")
    if fa not in {"continue", "abort"}:
        errors.append(f"step[{idx}].fail_action={fa!r} not in {{continue, abort}}")
    return errors


def cmd_list(args: argparse.Namespace) -> int:
    doc = load_manifest(resolve_manifest_path(args.manifest))
    steps = doc.get("steps") or []
    errors: list[str] = []
    for i, s in enumerate(steps):
        errors.extend(validate_step(i, s))
    out = {
        "round": "R262",
        "vector": "SDD-029 R262 (schedule-manifest)",
        "manifest_source": doc.get("_source"),
        "parse_error": doc.get("_parse_error"),
        "meta": doc.get("meta") or {},
        "step_count": len(steps),
        "steps": steps,
        "validation_errors": errors,
        "valid": not errors and not doc.get("_parse_error"),
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"── R262 sovereign-os schedule-manifest list ──")
    print(f"  source:        {doc.get('_source')}")
    if doc.get("_parse_error"):
        print(f"  PARSE ERROR:   {doc.get('_parse_error')}")
    meta = doc.get("meta") or {}
    if meta:
        print(f"  description:   {meta.get('description','(none)')}")
        print(f"  budget:        {meta.get('total_budget_seconds','?')} s")
    print(f"  step count:    {len(steps)}")
    for i, s in enumerate(steps):
        print(f"    [{i}] {s.get('name','?'):<32} kind={s.get('kind'):<16} timeout={s.get('timeout_s','-')}s")
        if s.get("target"):
            print(f"        target={s.get('target')}")
        if s.get("cmd"):
            print(f"        cmd={s.get('cmd')}")
    if errors:
        print()
        print(f"  validation errors ({len(errors)}):")
        for e in errors:
            print(f"    ✗ {e}")
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    doc = load_manifest(resolve_manifest_path(args.manifest))
    steps = doc.get("steps") or []
    errors: list[str] = []
    for i, s in enumerate(steps):
        errors.extend(validate_step(i, s))
    plan_rows = []
    for i, s in enumerate(steps):
        plan_rows.append({
            "order": i,
            "name": s.get("name"),
            "kind": s.get("kind"),
            "would_do": _describe_step(s),
            "timeout_s": s.get("timeout_s", 30),
            "fail_action": s.get("fail_action", "continue"),
        })
    out = {
        "round": "R262",
        "vector": "SDD-029 R262 (plan)",
        "manifest_source": doc.get("_source"),
        "validation_errors": errors,
        "valid": not errors,
        "plan": plan_rows,
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"── R262 schedule-manifest plan (DRY-RUN) ──")
    print(f"  manifest: {doc.get('_source')}")
    for r in plan_rows:
        print(f"  [{r['order']}] {r['name']:<32} → {r['would_do']}")
    if errors:
        print()
        print("  validation errors:")
        for e in errors:
            print(f"    ✗ {e}")
    return 0


def _describe_step(s: dict[str, Any]) -> str:
    kind = s.get("kind")
    if kind == "systemctl-stop":
        return f"systemctl stop {s.get('target')}"
    if kind == "shell":
        return f"shell: {s.get('cmd')}"
    if kind == "sleep":
        return f"sleep {s.get('seconds')}s"
    return f"unknown kind: {kind}"


def execute_step(step: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    name = step.get("name", "?")
    kind = step.get("kind")
    timeout = float(step.get("timeout_s", 30))
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    t0 = time.time()
    if dry_run:
        return {
            "name": name,
            "kind": kind,
            "outcome": "dry-run",
            "detail": _describe_step(step),
            "duration_s": 0,
            "started_at": started_at,
        }
    if kind == "sleep":
        time.sleep(float(step.get("seconds", 0)))
        return {
            "name": name,
            "kind": kind,
            "outcome": "ok",
            "detail": f"slept {step.get('seconds')}s",
            "duration_s": round(time.time() - t0, 2),
            "started_at": started_at,
        }
    if kind == "systemctl-stop":
        target = step.get("target")
        if not shutil.which("systemctl"):
            return {
                "name": name,
                "kind": kind,
                "outcome": "failed",
                "detail": "systemctl missing on PATH",
                "duration_s": round(time.time() - t0, 2),
                "started_at": started_at,
            }
        try:
            r = subprocess.run(
                ["systemctl", "stop", target],
                capture_output=True, text=True, timeout=timeout, check=False,
            )
        except subprocess.TimeoutExpired:
            return {
                "name": name,
                "kind": kind,
                "outcome": "timeout",
                "detail": f"systemctl stop {target} exceeded {timeout}s",
                "duration_s": round(time.time() - t0, 2),
                "started_at": started_at,
            }
        return {
            "name": name,
            "kind": kind,
            "outcome": "ok" if r.returncode == 0 else "failed",
            "detail": (r.stderr or r.stdout).strip()[:200],
            "duration_s": round(time.time() - t0, 2),
            "started_at": started_at,
        }
    if kind == "shell":
        cmd = step.get("cmd", "")
        try:
            r = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,  # noqa: S602
                timeout=timeout, check=False,
            )
        except subprocess.TimeoutExpired:
            return {
                "name": name,
                "kind": kind,
                "outcome": "timeout",
                "detail": f"shell exceeded {timeout}s",
                "duration_s": round(time.time() - t0, 2),
                "started_at": started_at,
            }
        return {
            "name": name,
            "kind": kind,
            "outcome": "ok" if r.returncode == 0 else "failed",
            "detail": (r.stderr or r.stdout).strip()[:200],
            "duration_s": round(time.time() - t0, 2),
            "started_at": started_at,
        }
    return {
        "name": name,
        "kind": kind,
        "outcome": "failed",
        "detail": f"unknown kind {kind!r}",
        "duration_s": 0,
        "started_at": started_at,
    }


def cmd_apply(args: argparse.Namespace) -> int:
    doc = load_manifest(resolve_manifest_path(args.manifest))
    steps = doc.get("steps") or []
    errors: list[str] = []
    for i, s in enumerate(steps):
        errors.extend(validate_step(i, s))
    if errors:
        print(
            f"ERROR manifest has {len(errors)} validation error(s); refusing to apply:",
            file=sys.stderr,
        )
        for e in errors:
            print(f"  ✗ {e}", file=sys.stderr)
        return 2
    dry = bool(args.dry_run) or os.environ.get("SOVEREIGN_OS_DRY_RUN")
    # Triple-gate: --confirm OR SOVEREIGN_OS_CONFIRM_DESTROY=YES required
    # for the WRITE path. DRY-RUN auto-implies safe path.
    if not dry:
        confirm_env = os.environ.get("SOVEREIGN_OS_CONFIRM_DESTROY") == "YES"
        if not args.confirm and not confirm_env:
            print(
                "ERROR apply without --confirm OR SOVEREIGN_OS_CONFIRM_DESTROY=YES",
                file=sys.stderr,
            )
            print(
                "      schedule-manifest apply can stop services + run shell "
                "commands + power off the host. Add --confirm to acknowledge.",
                file=sys.stderr,
            )
            return 2

    results: list[dict[str, Any]] = []
    aborted = False
    failures = 0
    for s in steps:
        res = execute_step(s, dry_run=bool(dry))
        results.append(res)
        if res["outcome"] not in {"ok", "dry-run"}:
            failures += 1
            if s.get("fail_action", "continue") == "abort":
                aborted = True
                results.append({
                    "name": "(abort)",
                    "kind": "(abort)",
                    "outcome": "skipped",
                    "detail": f"prior step {res['name']!r} {res['outcome']} + fail_action=abort",
                    "duration_s": 0,
                    "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                })
                break
    out = {
        "round": "R262",
        "vector": "SDD-029 R262 (apply)",
        "manifest_source": doc.get("_source"),
        "dry_run": bool(dry),
        "confirmed": bool(args.confirm) or os.environ.get("SOVEREIGN_OS_CONFIRM_DESTROY") == "YES",
        "aborted": aborted,
        "step_count": len(steps),
        "executed_count": len(results),
        "failure_count": failures,
        "results": results,
    }
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print(f"── R262 schedule-manifest apply (dry_run={out['dry_run']}) ──")
        for r in results:
            mark = {"ok": "OK ", "dry-run": "DRY", "failed": "FAIL",
                    "timeout": "TMO", "skipped": "SKP"}.get(r["outcome"], "?")
            print(f"  [{mark}] {r['name']:<32} {r['outcome']:<8} {r['duration_s']:>6.2f}s  {r['detail'][:60]}")
    return 1 if failures else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="schedule-manifest.py",
        description="R262 (SDD-029 R262) — graceful drain-then-poweroff manifest.",
    )
    sub = p.add_subparsers(dest="verb", required=True)
    for name, fn, helptxt in [
        ("list", cmd_list, "render declared manifest + validation"),
        ("plan", cmd_plan, "describe what apply would do (DRY-RUN)"),
        ("apply", cmd_apply, "execute steps; --confirm required"),
    ]:
        sp = sub.add_parser(name, help=helptxt)
        sp.add_argument("--manifest", type=Path)
        sp.add_argument("--json", action="store_true")
        if name == "apply":
            sp.add_argument("--confirm", action="store_true",
                            help="acknowledge that apply mutates the host")
            sp.add_argument("--dry-run", action="store_true",
                            help="simulate steps without executing them")
        sp.set_defaults(func=fn)
    return p


def main(argv: list[str]) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
