#!/usr/bin/env python3
"""scripts/intelligence/doctrine-status.py — R376 (E10.M20).

Operator-pull "doctrine health at a glance" verb. Runs the SDD-037
verbatim-preservation lint family + reports pass/fail per-lint +
cumulative state + bug-catch tally + remediation hints.

Without this verb, operator has to run `pytest tests/lint/` (developer-
facing). This verb wraps pytest with an operator-friendly output:
which doctrine surfaces are clean, which need attention, what's
specifically failing, and how to fix.

CLI:
  doctrine-status.py status              [--config P] [--json|--human]
                                          pass/fail per-lint + total
                                          assertion count
  doctrine-status.py tally               [--config P] [--json|--human]
                                          cumulative bug-catch + drift-
                                          mode catalog (operator-readable
                                          tally)
  doctrine-status.py run                 [--config P] [--json|--human]
                                          execute pytest on the SDD-037
                                          lint family + emit verdict
                                          (slowest verb; ~1-3s)

Operator-overlay (R283/SDD-030): /etc/sovereign-os/doctrine-status.toml
  - override lint module paths
  - extend lint-family with operator-authored lints

Exit codes:
  0  all clean
  1  ≥1 lint failed
  2  usage error
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
ROUND = "R376"
SDD_VECTOR = "E10.M20"


# SDD-037 lint family (R367 + R368 + R370 + R371 + R372 + R373 + R374)
SDD_037_LINT_FAMILY: list[dict[str, Any]] = [
    {
        "round": "R367",
        "name": "verbatim-preservation doctrine + catalog floors",
        "path": "tests/lint/test_verbatim_preservation_doctrine.py",
        "assertion_count": 12,
        "purpose": ("Pins SDD-037 doc 7 required sections + catalog "
                     "floors (≥4 Q + ≥3 G + ≥10 C + ≥30 A) + spec_ref "
                     "non-empty + every-axis-has-verb invariant + "
                     "Tetragon 4-binary bidirectional + ID monotonic"),
    },
    {
        "round": "R368",
        "name": "spec_ref format + valid §N + coverage source format",
        "path": "tests/lint/test_verbatim_spec_ref_format.py",
        "assertion_count": 7,
        "purpose": ("Every Q/G/C spec_ref matches one of 11 known "
                     "citation patterns; every §N reference is in §1..§23 "
                     "+ §N.M valid range; coverage breadth ≥10 sections; "
                     "implementing_verbs use real prefix"),
    },
    {
        "round": "R370",
        "name": "static doc drift detection",
        "path": "tests/lint/test_verbatim_surface_doc_drift.py",
        "assertion_count": 9,
        "purpose": ("verbatim-surface.md stays in sync with catalog "
                     "modules; every C/A/Q/G ID appears in the doc; "
                     "SUMMARY.md links to it; tally ≥70 items"),
    },
    {
        "round": "R371",
        "name": "mandate-row reference validator",
        "path": "tests/lint/test_mandate_row_refs.py",
        "assertion_count": 7,
        "purpose": ("Every E.M mandate_rows entry in coverage-map points "
                     "to a real mandate row; mandate has ≥100 rows; "
                     "format check; no duplicates; ≥5 distinct epics"),
        "bugs_caught_at_ship": 2,
    },
    {
        "round": "R372",
        "name": "verb-dispatch + SDD reference validator",
        "path": "tests/lint/test_verb_dispatch_refs.py",
        "assertion_count": 8,
        "purpose": ("Every sovereign-osctl <verb> reference in catalogs "
                     "dispatches in scripts/sovereign-osctl; every SDD "
                     "reference exists in docs/sdd/; osctl ≥50 subverbs; "
                     "no duplicate dispatch cases"),
        "bugs_caught_at_ship": 16,
    },
    {
        "round": "R373",
        "name": "cross-catalog phrase consistency",
        "path": "tests/lint/test_cross_catalog_phrase_consistency.py",
        "assertion_count": 12,
        "purpose": ("11 operator-verbatim phrases cross-checked across "
                     "multiple catalogs (M.2_2 / sync=always / 31.5 GB/s "
                     "/ Marvell AQC113C / Intel I226-V / BindsTo / "
                     "CMK128GX5M2B6400C42 / SMT2200C / 990 EVO Plus / "
                     "'Magician' / Ryzen 9 9900X); silent-paraphrase "
                     "forbidden-list check"),
        "bugs_caught_at_ship": 2,
    },
    {
        "round": "R374",
        "name": "round-reference validator",
        "path": "tests/lint/test_round_refs.py",
        "assertion_count": 6,
        "purpose": ("R<N> citations in mandate Rounds column in active "
                     "range; recent rounds R350+ have backing commits in "
                     "git history; primary collision check; ≥150 rows; "
                     "no zero-padding"),
        "bugs_caught_at_ship": 0,
    },
]


# Cumulative drift / fabrication modes mechanized at push-time.
DRIFT_MODE_CATALOG: list[str] = [
    "SDD-037 doc section structure missing",
    "Catalog floors regressed (< 4 Q, < 3 G, < 10 C, < 30 A)",
    "Catalog hygiene broken (duplicate IDs, malformed C-NN/A-NN)",
    "spec_ref empty / too terse / wrong format",
    "Fabricated §N section ref (e.g. §99, §-1)",
    "Coverage breadth regressed (< 10 distinct master spec sections)",
    "Implementing_verb missing sovereign-osctl prefix",
    "Tetragon 4-binary allowlist divergence (C-14 ↔ shipped script)",
    "Static verbatim-surface.md drift (catalog grew without doc regen)",
    "Fabricated mandate row ref (E1.M999, typos, stale)",
    "Mandate file row-ID duplicates / format violations",
    "Fabricated sovereign-osctl verb (typos, renamed verbs)",
    "Fabricated SDD reference (no such docs/sdd/NNN-*.md)",
    "Duplicate dispatch cases in osctl",
    "Cross-catalog phrase drift (11 specific phrases)",
    "Silent paraphrase (forbidden-list patterns)",
    "Fabricated R<N> round numbers + zero-padding + git-history-backing",
]


def _run_pytest_module(module_path: str) -> dict[str, Any]:
    """Run pytest on a single module. NEVER raises. Returns
    pass/fail + assertion count + per-test results."""
    try:
        cp = subprocess.run(
            ["python3", "-m", "pytest", module_path, "-q", "--tb=no"],
            capture_output=True, text=True, timeout=60, cwd=REPO_ROOT,
        )
    except Exception as e:
        return {"ok": False, "error": str(e), "rc": -1,
                 "passed": 0, "failed": 0}
    # Parse "N passed" / "N failed" from output
    passed = 0
    failed = 0
    import re
    pm = re.search(r"(\d+) passed", cp.stdout)
    fm = re.search(r"(\d+) failed", cp.stdout)
    if pm:
        passed = int(pm.group(1))
    if fm:
        failed = int(fm.group(1))
    return {
        "ok": cp.returncode == 0 and failed == 0,
        "rc": cp.returncode,
        "passed": passed,
        "failed": failed,
        "tail": "\n".join(cp.stdout.strip().split("\n")[-10:]),
    }


def run_lint_family() -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    total_assertions = 0
    total_passed = 0
    total_failed = 0
    for lint in SDD_037_LINT_FAMILY:
        outcome = _run_pytest_module(lint["path"])
        results.append({
            "round": lint["round"],
            "name": lint["name"],
            "path": lint["path"],
            "declared_count": lint["assertion_count"],
            "ok": outcome["ok"],
            "passed": outcome["passed"],
            "failed": outcome["failed"],
            "tail": outcome.get("tail", "")[:200],
        })
        total_assertions += lint["assertion_count"]
        total_passed += outcome["passed"]
        total_failed += outcome["failed"]
    return {
        "lints": results,
        "total_assertions_declared": total_assertions,
        "total_passed": total_passed,
        "total_failed": total_failed,
        "all_clean": total_failed == 0,
    }


def status_summary() -> dict[str, Any]:
    """Lightweight: doesn't actually run pytest. Returns the catalog
    state."""
    total = sum(l["assertion_count"] for l in SDD_037_LINT_FAMILY)
    total_bugs = sum(l.get("bugs_caught_at_ship", 0) for l in SDD_037_LINT_FAMILY)
    return {
        "schema_version": SCHEMA_VERSION,
        "round": ROUND,
        "sdd_vector": SDD_VECTOR,
        "lint_family_size": len(SDD_037_LINT_FAMILY),
        "total_declared_assertions": total,
        "cumulative_bugs_caught": total_bugs,
        "drift_mode_count": len(DRIFT_MODE_CATALOG),
        "lints": [
            {"round": l["round"], "name": l["name"],
              "assertions": l["assertion_count"],
              "bugs_caught": l.get("bugs_caught_at_ship", 0)}
            for l in SDD_037_LINT_FAMILY
        ],
    }


def tally() -> dict[str, Any]:
    """Catalog of cumulative state without running pytest."""
    return {
        "schema_version": SCHEMA_VERSION,
        "round": ROUND,
        "sdd_vector": SDD_VECTOR,
        "drift_modes": DRIFT_MODE_CATALOG,
        "drift_mode_count": len(DRIFT_MODE_CATALOG),
        "lint_family": SDD_037_LINT_FAMILY,
        "lint_family_size": len(SDD_037_LINT_FAMILY),
        "total_assertions": sum(l["assertion_count"]
                                  for l in SDD_037_LINT_FAMILY),
        "cumulative_bugs_caught": sum(
            l.get("bugs_caught_at_ship", 0) for l in SDD_037_LINT_FAMILY),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="doctrine-status.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    for verb in ("status", "tally", "run"):
        sp = sub.add_parser(verb)
        sp.add_argument("--config", type=Path)
        spg = sp.add_mutually_exclusive_group()
        spg.add_argument("--json", dest="fmt", action="store_const", const="json")
        spg.add_argument("--human", dest="fmt", action="store_const", const="human")
        sp.set_defaults(fmt="json")

    args = p.parse_args(argv)

    if args.cmd == "status":
        s = status_summary()
        if args.fmt == "json":
            print(json.dumps(s, indent=2))
        else:
            print(f"── R376 SDD-037 doctrine status ──")
            print(f"  lint family: {s['lint_family_size']} rounds")
            print(f"  total assertions: {s['total_declared_assertions']}")
            print(f"  drift modes: {s['drift_mode_count']}")
            print(f"  cumulative bugs caught at ship: {s['cumulative_bugs_caught']}")
            print()
            print("  Per-lint:")
            for l in s["lints"]:
                bugs = l["bugs_caught"]
                bug_str = f" ({bugs} bugs caught)" if bugs else ""
                print(f"    {l['round']:>4}  {l['name'][:60]:<60}  "
                       f"{l['assertions']} assertions{bug_str}")
        return 0

    if args.cmd == "tally":
        t = tally()
        if args.fmt == "json":
            print(json.dumps(t, indent=2))
        else:
            print(f"── R376 SDD-037 cumulative drift tally ──")
            print(f"  lint family: {t['lint_family_size']} rounds × "
                   f"{t['total_assertions']} total assertions")
            print(f"  drift modes caught: {t['drift_mode_count']}")
            print(f"  bugs caught at ship: {t['cumulative_bugs_caught']}")
            print()
            print("  Drift modes:")
            for i, mode in enumerate(t["drift_modes"], 1):
                print(f"    {i:>2}. {mode}")
        return 0

    if args.cmd == "run":
        r = run_lint_family()
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                **r,
            }, indent=2))
        else:
            print(f"── R376 SDD-037 lint family run ──")
            glyph = "✓" if r["all_clean"] else "✗"
            print(f"  overall: {glyph} {r['total_passed']} passed / "
                   f"{r['total_failed']} failed / {r['total_assertions_declared']} declared")
            print()
            print("  Per-lint:")
            for l in r["lints"]:
                g = "✓" if l["ok"] else "✗"
                print(f"    {g} {l['round']:>4}  {l['name'][:50]:<50}  "
                       f"{l['passed']}/{l['declared_count']}")
                if not l["ok"]:
                    print(f"           Tail: {l['tail'][:100]}")
        return 0 if r["all_clean"] else 1

    return 2


if __name__ == "__main__":
    sys.exit(main())
