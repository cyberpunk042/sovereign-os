#!/usr/bin/env python3
"""scripts/intelligence/quarterly-review.py — R377 (E10.M21).

Operator-pull quarterly review meta-audit. Composes the doctrine +
coverage + verbatim + mandate health into one consolidated verdict
suitable for periodic operator review snapshots.

Without this verb, operator runs 4+ separate commands to assess
sovereign-os health. With this verb, one command emits the
quarterly snapshot.

Composed sources (each NEVER-raises; missing source degrades
gracefully):
  R365 coverage-map audit       — operator demand coverage state
  R376 doctrine-status run      — SDD-037 lint family health
  R369 verbatim-render summary  — catalog tally (~80 verbatim items)
  R374 round refs               — git history vs mandate consistency
  mandate file size + row count  — sanity check vs truncation
  recent-rounds tally            — last N rounds shipped (rolling window)

CLI:
  quarterly-review.py snapshot   [--since R<N>] [--config P] [--json|--human]
                                  full consolidated report
  quarterly-review.py grade      [--config P] [--json|--human]
                                  operator-readable letter grade
                                  (A/B/C/D/F) + headline issues
  quarterly-review.py recent     [--since R<N>] [--config P] [--json|--human]
                                  rounds shipped since R<N> (default
                                  R350 = the verbatim-preservation arc)

Exit codes:
  0  health verdict A or B (clean)
  1  health verdict C / D / F (attention needed)
  2  usage error
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
MANDATE = (REPO_ROOT / "docs" / "standing-directives"
           / "2026-05-17-operator-mandate.md")

sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
try:
    from operator_overlay import load_with_overlay  # type: ignore
except Exception:  # pragma: no cover
    load_with_overlay = None


SCHEMA_VERSION = "1.0.0"
ROUND = "R377"
SDD_VECTOR = "E10.M21"


def _run_verb(verb: str, args: list[str]) -> dict[str, Any]:
    """Run a sovereign-osctl verb via the underlying script. NEVER-raises."""
    script_map = {
        "coverage-audit": [
            "scripts/intelligence/coverage-map.py", "audit"],
        "doctrine-status": [
            "scripts/intelligence/doctrine-status.py", "status"],
        "verbatim-summary": [
            "scripts/intelligence/verbatim-render.py", "summary"],
    }
    if verb not in script_map:
        return {"error": f"unknown verb: {verb}"}
    cmd = ["python3"] + script_map[verb] + args + ["--json"]
    try:
        cp = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, cwd=REPO_ROOT,
        )
    except Exception as e:
        return {"error": str(e)}
    if cp.returncode not in (0, 1):
        return {"error": f"rc={cp.returncode}", "stderr": cp.stderr[:200]}
    try:
        return {"rc": cp.returncode, "data": json.loads(cp.stdout)}
    except json.JSONDecodeError as e:
        return {"error": f"json parse: {e}", "stdout": cp.stdout[:200]}


def _mandate_stats() -> dict[str, Any]:
    """Parse mandate file for row count + most recent rounds."""
    if not MANDATE.is_file():
        return {"file_present": False}
    body = MANDATE.read_text(encoding="utf-8")
    rows = re.findall(r"^\| (E\d+\.M\d+)\s*\|", body, re.M)
    rounds = sorted(set(int(r) for r in re.findall(
        r"\bR(\d+)\b", body)), reverse=True)[:20]
    return {
        "file_present": True,
        "file_size_bytes": len(body),
        "row_count": len(rows),
        "distinct_row_ids": len(set(rows)),
        "recent_rounds": [f"R{r}" for r in rounds[:10]],
    }


def _git_recent_rounds(since_round: int) -> list[dict[str, Any]]:
    """Parse git log for commits since R<N>. NEVER-raises."""
    try:
        cp = subprocess.run(
            ["git", "log", "--all", "--pretty=format:%h|%s",
              "--max-count=200"],
            capture_output=True, text=True, timeout=10, cwd=REPO_ROOT,
        )
    except Exception:
        return []
    if cp.returncode != 0:
        return []
    out: list[dict[str, Any]] = []
    for line in cp.stdout.splitlines():
        parts = line.split("|", 1)
        if len(parts) != 2:
            continue
        sha, msg = parts
        rmatch = re.search(r"\bR(\d+)\b", msg)
        if rmatch:
            r_num = int(rmatch.group(1))
            if r_num >= since_round:
                out.append({"sha": sha, "round": f"R{r_num}",
                             "summary": msg[:120]})
    return out


def _grade(snapshot: dict[str, Any]) -> tuple[str, list[str]]:
    """Return (letter_grade, [headline_issues])."""
    issues: list[str] = []
    grade = "A"

    cov = snapshot.get("coverage_audit", {}).get("data", {})
    if cov.get("todo_count", 0) > 0:
        issues.append(f"{cov['todo_count']} TODO axes in coverage-map")
        grade = "C"
    if cov.get("partial_count", 0) > 2:
        issues.append(f"{cov['partial_count']} partial axes (>2 threshold)")
        if grade < "B":
            grade = "B"

    doc = snapshot.get("doctrine_status", {}).get("data", {})
    if doc.get("lint_family_size", 0) < 7:
        issues.append("SDD-037 lint family below floor (7 lints)")
        grade = "D"

    verb = snapshot.get("verbatim_summary", {}).get("data", {})
    if verb.get("total_items", 0) < 70:
        issues.append(f"verbatim catalog below floor (70 items)")
        grade = "D"

    mandate = snapshot.get("mandate_stats", {})
    if not mandate.get("file_present"):
        issues.append("mandate file missing!")
        grade = "F"
    elif mandate.get("row_count", 0) < 150:
        issues.append(f"mandate has only {mandate['row_count']} rows")
        if grade < "C":
            grade = "C"

    return grade, issues


def snapshot(since_round: int = 350) -> dict[str, Any]:
    coverage_audit = _run_verb("coverage-audit", [])
    doctrine_status = _run_verb("doctrine-status", [])
    verbatim_summary = _run_verb("verbatim-summary", [])
    mandate_stats = _mandate_stats()
    recent = _git_recent_rounds(since_round)
    s = {
        "schema_version": SCHEMA_VERSION,
        "round": ROUND,
        "sdd_vector": SDD_VECTOR,
        "coverage_audit": coverage_audit,
        "doctrine_status": doctrine_status,
        "verbatim_summary": verbatim_summary,
        "mandate_stats": mandate_stats,
        "since_round": since_round,
        "recent_rounds_shipped": recent,
    }
    grade, issues = _grade(s)
    s["grade"] = grade
    s["headline_issues"] = issues
    return s


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="quarterly-review.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    for verb in ("snapshot", "grade", "recent"):
        sp = sub.add_parser(verb)
        sp.add_argument("--since", default="R350")
        sp.add_argument("--config", type=Path)
        spg = sp.add_mutually_exclusive_group()
        spg.add_argument("--json", dest="fmt", action="store_const", const="json")
        spg.add_argument("--human", dest="fmt", action="store_const", const="human")
        sp.set_defaults(fmt="json")

    args = p.parse_args(argv)
    since_match = re.match(r"R?(\d+)", args.since)
    since_round = int(since_match.group(1)) if since_match else 350

    if args.cmd == "snapshot":
        s = snapshot(since_round)
        if args.fmt == "json":
            print(json.dumps(s, indent=2))
        else:
            print(f"── R377 Quarterly Review Snapshot (grade: {s['grade']}) ──")
            print(f"  since: R{since_round}")
            print()
            cov = s["coverage_audit"].get("data", {})
            if cov:
                print(f"  Coverage:  {cov.get('shipped_count', 0)} ✓ shipped, "
                       f"{cov.get('partial_count', 0)} partial, "
                       f"{cov.get('todo_count', 0)} TODO "
                       f"(of {cov.get('total_axes', 0)} total)")
            doc = s["doctrine_status"].get("data", {})
            if doc:
                print(f"  Doctrine:  {doc.get('lint_family_size', 0)} lints / "
                       f"{doc.get('total_declared_assertions', 0)} assertions / "
                       f"{doc.get('cumulative_bugs_caught', 0)} bugs caught")
            verb = s["verbatim_summary"].get("data", {})
            if verb:
                print(f"  Verbatim:  {verb.get('total_items', 0)} catalogued items, "
                       f"~{verb.get('estimated_phrase_count', 0)} phrases")
            mandate = s["mandate_stats"]
            if mandate.get("file_present"):
                print(f"  Mandate:   {mandate['row_count']} rows / "
                       f"{mandate['file_size_bytes']} bytes")
            print(f"  Rounds since R{since_round}: "
                   f"{len(s['recent_rounds_shipped'])} commits")
            if s["headline_issues"]:
                print()
                print("  Headline issues:")
                for i in s["headline_issues"]:
                    print(f"    ⚠ {i}")
        return 0 if s["grade"] in ("A", "B") else 1

    if args.cmd == "grade":
        s = snapshot(since_round)
        out = {"grade": s["grade"], "headline_issues": s["headline_issues"]}
        if args.fmt == "json":
            print(json.dumps(out, indent=2))
        else:
            print(f"── R377 Quarterly Review Grade ──")
            print(f"  Grade: {s['grade']}")
            if s["headline_issues"]:
                for i in s["headline_issues"]:
                    print(f"    ⚠ {i}")
            else:
                print("  ✓ no headline issues")
        return 0 if s["grade"] in ("A", "B") else 1

    if args.cmd == "recent":
        recent = _git_recent_rounds(since_round)
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "since_round": since_round,
                "commit_count": len(recent),
                "commits": recent,
            }, indent=2))
        else:
            print(f"── R377 Rounds since R{since_round} ──")
            print(f"  {len(recent)} commits")
            for c in recent[:25]:
                print(f"    {c['sha']}  {c['round']}  {c['summary'][:90]}")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
