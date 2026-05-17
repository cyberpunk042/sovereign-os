#!/usr/bin/env python3
"""scripts/diagnostics/self-test.py — R331 (E9.M14).

Operator-pull "is sovereign-os itself working correctly on this
host?" Runs L1 lint suites via pytest + a curated subset of L3
nspawn shell tests + emits operator-readable health summary.

Distinct from R322 state-snapshot (which probes the OPERATOR'S
host) — this verb tests the TOOLING running on the host.

CLI:
  self-test.py run     [--config P] [--json|--human]
                          run lint + curated L3 sample + summarize
  self-test.py list    [--config P] [--json|--human]
                          list which suites would run (dry-run catalog)

Suite catalog defaults:

  lint (always run, via pytest):
    tests/lint/*.py

  l3 (curated subset, low subprocess cost):
    tests/nspawn/test_rounds_catalog.sh
    tests/nspawn/test_overlay_drift_detector.sh
    tests/nspawn/test_maintenance_window.sh
    tests/nspawn/test_inventory_catalog.sh
    tests/nspawn/test_next_action_advisor.sh

  unit (always run, via pytest):
    tests/unit/test_safe_apply.py

Operator-overlay (R283/SDD-030):
/etc/sovereign-os/self-test.toml
  - lint_glob              tests/lint/*.py
  - unit_globs             [tests/unit/*.py]
  - l3_paths               curated list (overlay can extend or replace)
  - per_suite_timeout_sec  60

Exit codes:
  0  all suites pass
  1  ≥1 suite failure
  2  usage error / pytest missing
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
try:
    from operator_overlay import load_with_overlay  # type: ignore
except Exception:  # pragma: no cover
    load_with_overlay = None


SCHEMA_VERSION = "1.0.0"
ROUND = "R331"
SDD_VECTOR = "E9.M14"


DEFAULTS = {
    "lint_glob": "tests/lint/*.py",
    "unit_globs": ["tests/unit/test_safe_apply.py"],
    "l3_paths": [
        "tests/nspawn/test_rounds_catalog.sh",
        "tests/nspawn/test_overlay_drift_detector.sh",
        "tests/nspawn/test_maintenance_window.sh",
        "tests/nspawn/test_inventory_catalog.sh",
        "tests/nspawn/test_next_action_advisor.sh",
    ],
    "per_suite_timeout_sec": 60,
}


def load_state(overlay_path: Path | None) -> tuple[dict, dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    cfg = dict(DEFAULTS)
    if load_with_overlay is not None:
        loaded = load_with_overlay("self-test", DEFAULTS,
                                    explicit_path=overlay_path)
        for k in DEFAULTS:
            if k in loaded:
                cfg[k] = loaded[k]
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]
    return cfg, meta


def run_pytest_glob(glob_pattern: str, timeout: int) -> dict[str, Any]:
    """Run pytest against a glob pattern; return per-suite result."""
    matched = sorted(REPO_ROOT.glob(glob_pattern))
    if not matched:
        return {"glob": glob_pattern, "matched": 0, "rc": 0,
                 "passed": 0, "failed": 0, "duration_ms": 0,
                 "available": False,
                 "detail": f"no files matched {glob_pattern}"}
    started = time.time()
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pytest", *[str(p) for p in matched],
             "--tb=line", "-q"],
            capture_output=True, text=True, timeout=timeout, check=False,
            cwd=str(REPO_ROOT),
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"glob": glob_pattern, "matched": len(matched), "rc": -1,
                 "passed": 0, "failed": 0,
                 "duration_ms": int((time.time() - started) * 1000),
                 "available": True,
                 "detail": f"pytest subprocess failed: {e}"}
    # Parse pytest's "N passed, M failed" line.
    out = (r.stdout or "") + (r.stderr or "")
    passed, failed = 0, 0
    for tok in out.split():
        if tok.endswith("passed"):
            try:
                passed = int(tok.split("p")[0].strip(",") or "0")
            except (ValueError, IndexError):
                pass
    # Use last word before 'passed' / 'failed' as the count.
    import re
    m_pass = re.search(r"(\d+)\s+passed", out)
    if m_pass:
        passed = int(m_pass.group(1))
    m_fail = re.search(r"(\d+)\s+failed", out)
    if m_fail:
        failed = int(m_fail.group(1))
    return {
        "glob": glob_pattern,
        "matched": len(matched),
        "rc": r.returncode,
        "passed": passed,
        "failed": failed,
        "duration_ms": int((time.time() - started) * 1000),
        "available": True,
        "detail": "pass" if r.returncode == 0 else "fail",
    }


def run_l3_script(rel_path: str, timeout: int) -> dict[str, Any]:
    """Run one nspawn bash test; parse PASS/FAIL count from stdout."""
    full = REPO_ROOT / rel_path
    if not full.is_file():
        return {"script": rel_path, "rc": -1, "passed": 0, "failed": 0,
                 "duration_ms": 0, "available": False,
                 "detail": "script not found"}
    started = time.time()
    try:
        r = subprocess.run(
            ["bash", str(full)],
            capture_output=True, text=True, timeout=timeout, check=False,
            cwd=str(REPO_ROOT),
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"script": rel_path, "rc": -1, "passed": 0, "failed": 0,
                 "duration_ms": int((time.time() - started) * 1000),
                 "available": True,
                 "detail": f"subprocess failed: {e}"}
    out = r.stdout or ""
    # L3 scripts print "PASS: <description>" per assertion + "ALL OK"
    # at end. Count PASS lines that begin with "PASS:".
    passed = sum(1 for line in out.splitlines()
                  if line.startswith("PASS:"))
    failed = sum(1 for line in out.splitlines()
                  if line.startswith("FAIL:"))
    return {
        "script": rel_path,
        "rc": r.returncode,
        "passed": passed,
        "failed": failed,
        "duration_ms": int((time.time() - started) * 1000),
        "available": True,
        "detail": "ALL OK" if "ALL OK" in out else
                  (out.splitlines()[-1][:80] if out.strip() else "(no output)"),
    }


def run_all(cfg: dict) -> dict[str, Any]:
    timeout = int(cfg["per_suite_timeout_sec"])
    started = time.time()
    lint_result = run_pytest_glob(cfg["lint_glob"], timeout)
    unit_results = []
    for g in cfg.get("unit_globs", []):
        unit_results.append(run_pytest_glob(g, timeout))
    l3_results = []
    for p in cfg.get("l3_paths", []):
        l3_results.append(run_l3_script(p, timeout))

    total_passed = (lint_result.get("passed", 0)
                     + sum(u.get("passed", 0) for u in unit_results)
                     + sum(l.get("passed", 0) for l in l3_results))
    total_failed = (lint_result.get("failed", 0)
                     + sum(u.get("failed", 0) for u in unit_results)
                     + sum(l.get("failed", 0) for l in l3_results))
    rc = 0 if total_failed == 0 and lint_result.get("rc") == 0 \
            and all(u.get("rc") == 0 for u in unit_results) \
            and all(l.get("rc") == 0 for l in l3_results) else 1
    return {
        "schema_version": SCHEMA_VERSION,
        "round": ROUND,
        "sdd_vector": SDD_VECTOR,
        "started_at_epoch": started,
        "wall_clock_ms": int((time.time() - started) * 1000),
        "lint": lint_result,
        "unit": unit_results,
        "l3": l3_results,
        "totals": {
            "passed": total_passed,
            "failed": total_failed,
        },
        "verdict": "all-pass" if rc == 0 else "failures",
        "rc": rc,
    }


def render_human(doc: dict) -> str:
    lines = [f"── R331 sovereign-os self-test (E9.M14) ──"]
    lines.append(f"  verdict:       {doc['verdict']} (rc={doc['rc']})")
    lines.append(f"  wall clock:    {doc['wall_clock_ms']}ms")
    lines.append(f"  total passed:  {doc['totals']['passed']}")
    lines.append(f"  total failed:  {doc['totals']['failed']}")
    lines.append("")
    lint = doc["lint"]
    mark = "OK" if lint["rc"] == 0 else "!!"
    lines.append(f"  [{mark}] lint   {lint['glob']:40s}  "
                  f"passed={lint['passed']}  failed={lint['failed']}  "
                  f"{lint['duration_ms']:>5d}ms")
    for u in doc["unit"]:
        mark = "OK" if u["rc"] == 0 else "!!"
        lines.append(f"  [{mark}] unit   {u['glob']:40s}  "
                      f"passed={u['passed']}  failed={u['failed']}  "
                      f"{u['duration_ms']:>5d}ms")
    for l3 in doc["l3"]:
        mark = "OK" if l3["rc"] == 0 else "!!"
        lines.append(f"  [{mark}] l3     {l3['script']:40s}  "
                      f"passed={l3['passed']}  failed={l3['failed']}  "
                      f"{l3['duration_ms']:>5d}ms")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="self-test.py")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("run")
    pr.add_argument("--config", type=Path)
    fr = pr.add_mutually_exclusive_group()
    fr.add_argument("--json", dest="fmt", action="store_const", const="json")
    fr.add_argument("--human", dest="fmt", action="store_const", const="human")
    pr.set_defaults(fmt="json")

    pl = sub.add_parser("list")
    pl.add_argument("--config", type=Path)
    fl = pl.add_mutually_exclusive_group()
    fl.add_argument("--json", dest="fmt", action="store_const", const="json")
    fl.add_argument("--human", dest="fmt", action="store_const", const="human")
    pl.set_defaults(fmt="json")

    args = p.parse_args(argv)
    cfg, meta = load_state(args.config)

    if args.cmd == "list":
        lint_files = sorted(REPO_ROOT.glob(cfg["lint_glob"]))
        unit_files = []
        for g in cfg.get("unit_globs", []):
            unit_files.extend(sorted(REPO_ROOT.glob(g)))
        l3_files = [str(REPO_ROOT / p) for p in cfg.get("l3_paths", [])]
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "lint_glob": cfg["lint_glob"],
                "lint_files": [str(p) for p in lint_files],
                "unit_globs": cfg.get("unit_globs", []),
                "unit_files": [str(p) for p in unit_files],
                "l3_paths": cfg.get("l3_paths", []),
                "l3_files_exist": [str(p) for p in l3_files
                                   if Path(p).is_file()],
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R331 self-test catalog (E9.M14) ──")
            print(f"  lint glob:    {cfg['lint_glob']}")
            print(f"  lint files:   {len(lint_files)}")
            for f in lint_files:
                print(f"    {f.relative_to(REPO_ROOT)}")
            print(f"  unit globs:   {cfg.get('unit_globs', [])}")
            for f in unit_files:
                print(f"    {f.relative_to(REPO_ROOT)}")
            print(f"  l3 paths:")
            for p_str in cfg.get("l3_paths", []):
                exists = (REPO_ROOT / p_str).is_file()
                mark = "OK" if exists else "??"
                print(f"    [{mark}] {p_str}")
        return 0

    # run
    doc = run_all(cfg)
    doc["overlay"] = meta
    if args.fmt == "json":
        print(json.dumps(doc, indent=2))
    else:
        print(render_human(doc), end="")
    return doc["rc"]


if __name__ == "__main__":
    sys.exit(main())
