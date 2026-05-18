#!/usr/bin/env python3
"""scripts/operator/anti-minimization-audit.py — R456 (E11.M11).

Operator §1g standing rule (VERBATIM):
  "If you think something is really already done, ask yourself if you
   covered all angles and levels and layers and even if then improve
   it. Do not minimize or settle for less."

  "We do not minimize anything."

This module scans the codebase for known minimization patterns and
surfaces them so the operator can re-audit. Operator-discoverable
ANTI-minimization discipline. Calls into R453 (surface-map) and R454
(doc-coverage) for cross-module gap reporting.

Operator-named minimization patterns (8):
  1. todo-no-anchor       TODO/FIXME without R-number or SDD anchor
                          (drift: gets forgotten, never closed)
  2. empty-stub           Python `pass`-only function body
                          (drift: API exists but does nothing)
  3. skipped-no-followup  "skipped" / "deferred" / "stub" without
                          ticket/issue reference
                          (drift: same as todo-no-anchor)
  4. surface-gap          Module below surface-map threshold (3 of 8)
                          (drift: §1g 8-surface contract violation)
  5. doc-gap              Module below doc-coverage threshold (3 of 6)
                          (drift: §1g "documentation through and
                          through" violation)
  6. mandate-todo         E11.Mx or E10.Mx mandate row still TODO
                          (drift: §1g feature unshipped)
  7. minimize-phrase      Code/comment contains "for now" / "minimize"
                          / "placeholder" / "simplified" / "stub"
                          / "we can improve later"
                          (drift: explicit operator-§1g violation)
  8. partial-status       Mandate row status="partial" or "in-flight"
                          (drift: half-done is itself a form of
                          minimization to track-and-close)

CLI:
  anti-minimization-audit.py patterns [--json|--human]
      Enumerate the 8 operator-named minimization patterns.

  anti-minimization-audit.py scan [--pattern <p>] [--limit N]
                                  [--json|--human]
      Scan the repo for ALL patterns (or one). Returns matches with
      file:line locations.

  anti-minimization-audit.py module <name> [--json|--human]
      Per-module audit: surface gaps + doc gaps + minimize-phrases
      in the module's own files.

  anti-minimization-audit.py cross-module [--threshold N] [--json|--human]
      Aggregate: which modules are short of §1g compliance across
      both runtime surfaces (R453) AND doc surfaces (R454)?

  anti-minimization-audit.py report [--json|--human]
      One-screen operator-discoverable summary: total matches per
      pattern, count of modules below threshold, mandate TODO/partial
      count.

Exit codes:
  0 ok / matches found (informational)
  1 unknown subcommand / pattern / module
  2 RESERVED (audit explicitly never "fails" — operator decides next
    action; non-zero exit would itself be minimization)

Layer B metric (SDD-016):
  sovereign_os_operator_anti_minimization_audit_query_total{verb,pattern,result}

Operator-environment env vars:
  SOVEREIGN_OS_AMIN_DRY_RUN  Logs intent; no file writes.
  SOVEREIGN_OS_DRY_RUN       Same effect (sovereign-wide).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

DRY_RUN = (
    os.environ.get("SOVEREIGN_OS_DRY_RUN") == "1"
    or os.environ.get("SOVEREIGN_OS_AMIN_DRY_RUN") == "1"
)
# R466 cross-repo: selfdef AuditManifest TOMLs live here. Each
# selfdef module ships one declaring its 8-pattern minimization
# standing (SD-R-AUDIT-1, crate `selfdef-audit-manifest`).
SELFDEF_AUDIT_DIR = Path(
    os.environ.get(
        "SOVEREIGN_OS_SELFDEF_AUDIT_DIR",
        "/etc/selfdef/audit-manifests",
    )
)
METRICS_DIR = Path(
    os.environ.get(
        "SOVEREIGN_OS_TEXTFILE_DIR",
        "/var/lib/prometheus/node-exporter",
    )
)

# HELP sovereign_os_operator_anti_minimization_audit_query_total anti-
# minimization audit operator-verb call count (verb, pattern, result).
# TYPE sovereign_os_operator_anti_minimization_audit_query_total counter
METRIC_NAME = "sovereign_os_operator_anti_minimization_audit_query_total"

PATTERNS = [
    {
        "id": "todo-no-anchor",
        "label": "TODO/FIXME without R-number or SDD anchor",
        "operator_named_rationale": (
            "TODOs without anchors get forgotten; minimization-by-attrition."
        ),
    },
    {
        "id": "empty-stub",
        "label": "Python pass-only function body",
        "operator_named_rationale": (
            "Empty body = API exists but does nothing; minimum viable lie."
        ),
    },
    {
        "id": "skipped-no-followup",
        "label": "'skipped' / 'deferred' / 'stub' without ticket reference",
        "operator_named_rationale": (
            "Skipped-without-followup is identical to never-doing-it."
        ),
    },
    {
        "id": "surface-gap",
        "label": "Module below surface-map threshold (R453)",
        "operator_named_rationale": (
            "§1g 'not just core, not just cli...' — too few surfaces "
            "= operator-facing-minimization."
        ),
    },
    {
        "id": "doc-gap",
        "label": "Module below doc-coverage threshold (R454)",
        "operator_named_rationale": (
            "§1g 'documentation through and through' — too few doc "
            "surfaces = documentation-minimization."
        ),
    },
    {
        "id": "mandate-todo",
        "label": "Mandate E11.Mx or E10.Mx row still TODO",
        "operator_named_rationale": (
            "TODO in mandate = §1g/§1h feature unshipped = the "
            "operator-most-visible form of minimization."
        ),
    },
    {
        "id": "minimize-phrase",
        "label": ("Code/comment contains 'for now' / 'minimize' / "
                  "'placeholder' / 'simplified' / 'stub'"),
        "operator_named_rationale": (
            "Explicit operator-§1g violation phrase — the code "
            "ITSELF admits it minimized."
        ),
    },
    {
        "id": "partial-status",
        "label": "Mandate row status 'partial' or 'in-flight'",
        "operator_named_rationale": (
            "Half-done is itself a form of minimization to "
            "track-and-close."
        ),
    },
]
PATTERN_IDS = [p["id"] for p in PATTERNS]

MINIMIZE_PHRASES = [
    "for now",
    "minimize",
    "minimization",
    "placeholder",
    "simplified",
    "we can improve later",
    "good enough",
    "quick and dirty",
    "TODO: minimize",
]

# Paths to scan (relative to REPO_ROOT). Exclude generated artifacts.
SCAN_INCLUDE_DIRS = ["scripts", "tests", "profiles", "schemas",
                     "docs", "models", "whitelabel", "systemd"]
SCAN_EXCLUDE_DIRS = {".git", "__pycache__", "node_modules",
                     ".pytest_cache"}


def _emit_metric(verb: str, pattern: str, result: str) -> None:
    """Best-effort SDD-016 metric write; never raises."""
    if DRY_RUN:
        sys.stderr.write(
            f"  would emit: {METRIC_NAME}"
            f'{{verb="{verb}",pattern="{pattern}",result="{result}"}} 1\n'
        )
        return
    try:
        METRICS_DIR.mkdir(parents=True, exist_ok=True)
        prom = (METRICS_DIR
                / "sovereign-os-operator-anti-minimization-audit.prom")
        line = (
            f"{METRIC_NAME}"
            f'{{verb="{verb}",pattern="{pattern}",result="{result}"}} 1\n'
        )
        tmp = prom.with_suffix(".prom.tmp")
        tmp.write_text(line)
        tmp.replace(prom)
    except OSError:
        pass


# --- Pattern scanners ---


def _iter_scan_files() -> list[Path]:
    files: list[Path] = []
    for d in SCAN_INCLUDE_DIRS:
        root = REPO_ROOT / d
        if not root.is_dir():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if any(part in SCAN_EXCLUDE_DIRS for part in p.parts):
                continue
            suffix = p.suffix.lower()
            if suffix in (".py", ".sh", ".md", ".yaml", ".yml",
                          ".toml", ".bash"):
                files.append(p)
            elif p.name == "sovereign-osctl":
                files.append(p)
    return files


def _grep_lines(path: Path, regex: re.Pattern) -> list[tuple[int, str]]:
    """Best-effort grep returning (lineno, line) tuples. Never raises."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return [
        (i + 1, line.rstrip())
        for i, line in enumerate(text.splitlines())
        if regex.search(line)
    ]


def scan_todo_no_anchor(limit: int | None = None) -> list[dict]:
    """TODO/FIXME without R-number (R\\d+) or SDD anchor (SDD-\\d+)."""
    todo_re = re.compile(r"\b(?:TODO|FIXME)\b", re.IGNORECASE)
    anchor_re = re.compile(r"\b(?:R\d+|SDD-\d+|E\d+\.M\d+)\b")
    matches = []
    for f in _iter_scan_files():
        for lineno, line in _grep_lines(f, todo_re):
            if not anchor_re.search(line):
                matches.append({
                    "file": str(f.relative_to(REPO_ROOT)),
                    "line": lineno,
                    "text": line[:160],
                })
                if limit and len(matches) >= limit:
                    return matches
    return matches


def scan_empty_stub(limit: int | None = None) -> list[dict]:
    """Python `def foo(...):\\n    pass` with no other body."""
    empty_re = re.compile(
        r"^\s*def\s+\w+\s*\([^)]*\)\s*(?:->\s*[\w\[\],\s.|]+)?:\s*\n"
        r"\s*pass\s*$",
        re.MULTILINE,
    )
    matches = []
    for f in _iter_scan_files():
        if f.suffix != ".py":
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in empty_re.finditer(text):
            lineno = text[: m.start()].count("\n") + 1
            matches.append({
                "file": str(f.relative_to(REPO_ROOT)),
                "line": lineno,
                "text": m.group(0).splitlines()[0][:120],
            })
            if limit and len(matches) >= limit:
                return matches
    return matches


def scan_skipped_no_followup(limit: int | None = None) -> list[dict]:
    """'skipped'/'deferred'/'stub' without ticket/issue/R-number ref."""
    keyword_re = re.compile(
        r"\b(?:skipped|deferred|stubbed?)\b", re.IGNORECASE
    )
    anchor_re = re.compile(
        r"\b(?:R\d+|SDD-\d+|#\d+|issue|E\d+\.M\d+)\b",
        re.IGNORECASE,
    )
    matches = []
    for f in _iter_scan_files():
        for lineno, line in _grep_lines(f, keyword_re):
            if not anchor_re.search(line):
                matches.append({
                    "file": str(f.relative_to(REPO_ROOT)),
                    "line": lineno,
                    "text": line[:160],
                })
                if limit and len(matches) >= limit:
                    return matches
    return matches


def scan_mandate_todo(limit: int | None = None) -> list[dict]:
    """Mandate E11.Mx or E10.Mx rows with status 'TODO'."""
    mandate = (REPO_ROOT / "docs" / "standing-directives"
               / "2026-05-17-operator-mandate.md")
    if not mandate.is_file():
        return []
    matches = []
    todo_row_re = re.compile(r"^\|\s*E1[01]\.M\d+\s*\|.*?\|\s*TODO\s*\|")
    try:
        text = mandate.read_text(encoding="utf-8")
    except OSError:
        return []
    for i, line in enumerate(text.splitlines(), 1):
        if todo_row_re.match(line):
            # Extract module id
            m = re.match(r"^\|\s*(E1[01]\.M\d+)", line)
            mid = m.group(1) if m else "?"
            matches.append({
                "file": "docs/standing-directives/"
                        "2026-05-17-operator-mandate.md",
                "line": i,
                "module": mid,
                "text": line[:160],
            })
            if limit and len(matches) >= limit:
                return matches
    return matches


def scan_partial_status(limit: int | None = None) -> list[dict]:
    """Mandate rows with status 'partial' or 'in-flight'."""
    mandate = (REPO_ROOT / "docs" / "standing-directives"
               / "2026-05-17-operator-mandate.md")
    if not mandate.is_file():
        return []
    matches = []
    partial_re = re.compile(
        r"^\|\s*E1[01]\.M\d+\s*\|.*?\|\s*(partial|in-flight)\b",
        re.IGNORECASE,
    )
    try:
        text = mandate.read_text(encoding="utf-8")
    except OSError:
        return []
    for i, line in enumerate(text.splitlines(), 1):
        m = partial_re.match(line)
        if m:
            mid_m = re.match(r"^\|\s*(E1[01]\.M\d+)", line)
            matches.append({
                "file": "docs/standing-directives/"
                        "2026-05-17-operator-mandate.md",
                "line": i,
                "module": mid_m.group(1) if mid_m else "?",
                "status": m.group(1),
                "text": line[:160],
            })
            if limit and len(matches) >= limit:
                return matches
    return matches


def scan_minimize_phrase(limit: int | None = None) -> list[dict]:
    """Code/comment contains a known minimize-phrase. Mandate file
    excluded (it discusses minimization but is not itself a violation).
    Anti-minimization-audit module itself excluded (defines patterns).
    """
    pat_re = re.compile(
        "|".join(re.escape(p) for p in MINIMIZE_PHRASES),
        re.IGNORECASE,
    )
    mandate_path = ("docs/standing-directives/"
                    "2026-05-17-operator-mandate.md")
    self_path = "scripts/operator/anti-minimization-audit.py"
    test_path = "tests/lint/test_anti_minimization_audit_contract.py"
    matches = []
    for f in _iter_scan_files():
        rel = str(f.relative_to(REPO_ROOT))
        if rel == mandate_path or rel == self_path or rel == test_path:
            continue
        for lineno, line in _grep_lines(f, pat_re):
            matches.append({
                "file": rel,
                "line": lineno,
                "text": line[:160],
            })
            if limit and len(matches) >= limit:
                return matches
    return matches


# Cross-module gap scanners (shell out to R453/R454)


def scan_surface_gap(threshold: int = 3) -> list[dict]:
    """Modules below surface-map threshold (calls R453)."""
    surface_map = REPO_ROOT / "scripts" / "operator" / "surface-map.py"
    try:
        r = subprocess.run(
            ["python3", str(surface_map), "gaps",
             "--threshold", str(threshold), "--json"],
            capture_output=True, text=True, timeout=10,
        )
        # exit 2 is the operator-discoverable signal; payload still valid
        if r.returncode not in (0, 2):
            return []
        data = json.loads(r.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return []
    return [
        {"module": e["module"],
         "surface_count": e["surface_count"],
         "shortfall": e["shortfall"]}
        for e in data.get("below_threshold", [])
    ]


def scan_doc_gap(threshold: int = 3) -> list[dict]:
    """Modules below doc-coverage threshold (calls R454)."""
    doc_cov = REPO_ROOT / "scripts" / "operator" / "doc-coverage.py"
    try:
        r = subprocess.run(
            ["python3", str(doc_cov), "gaps",
             "--threshold", str(threshold), "--json"],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode not in (0, 2):
            return []
        data = json.loads(r.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return []
    return [
        {"module": e["module"],
         "doc_surface_count": e["doc_surface_count"],
         "shortfall": e["shortfall"]}
        for e in data.get("below_threshold", [])
    ]


PATTERN_SCANNERS = {
    "todo-no-anchor": scan_todo_no_anchor,
    "empty-stub": scan_empty_stub,
    "skipped-no-followup": scan_skipped_no_followup,
    "mandate-todo": scan_mandate_todo,
    "partial-status": scan_partial_status,
    "minimize-phrase": scan_minimize_phrase,
    # cross-module patterns wrapped so signature matches
    "surface-gap": lambda limit=None: scan_surface_gap(),
    "doc-gap": lambda limit=None: scan_doc_gap(),
}


# --- Verbs ---


def cmd_patterns(args) -> int:
    out = {"patterns": PATTERNS, "count": len(PATTERNS)}
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"── anti-minimization-audit.patterns "
              f"({len(PATTERNS)} operator-named patterns) ──")
        for p in PATTERNS:
            print(f"  {p['id']:22s} — {p['label']}")
            print(f"  {'':22s}   {p['operator_named_rationale']}")
    _emit_metric("patterns", "all", "ok")
    return 0


def cmd_scan(args) -> int:
    pat = args.pattern
    if pat and pat not in PATTERN_IDS:
        print(f"unknown pattern: {pat!r}; known: {PATTERN_IDS}",
              file=sys.stderr)
        _emit_metric("scan", pat, "unknown-pattern")
        return 1
    pats = [pat] if pat else PATTERN_IDS
    results: dict[str, list[dict]] = {}
    for p in pats:
        scanner = PATTERN_SCANNERS[p]
        if p in ("surface-gap", "doc-gap"):
            results[p] = scanner()
        else:
            results[p] = scanner(limit=args.limit)
    total = sum(len(v) for v in results.values())
    out = {"results": results, "total_matches": total}
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"── anti-minimization-audit.scan "
              f"({total} matches across "
              f"{len(pats)} pattern{'s' if len(pats)!=1 else ''}) ──")
        for p in pats:
            n = len(results[p])
            print(f"\n  [{p}]  {n} match{'es' if n != 1 else ''}")
            shown = results[p][:5] if not args.json else results[p]
            for m in shown:
                loc = f"{m.get('file', '?')}:{m.get('line', '?')}"
                txt = m.get("text", m.get("module", ""))[:100]
                print(f"    {loc:60s} {txt}")
            if len(results[p]) > 5:
                print(f"    ... ({len(results[p]) - 5} more; use "
                      f"--json for full list)")
    _emit_metric("scan", pat or "all", "ok")
    return 0


def cmd_module(args) -> int:
    name = args.name
    if not name:
        print("module name required", file=sys.stderr)
        return 1
    # Per-module audit: surface gap + doc gap + minimize-phrase in
    # files matching the module name.
    surface_gaps = [g for g in scan_surface_gap() if g["module"] == name]
    doc_gaps = [g for g in scan_doc_gap() if g["module"] == name]
    name_re = re.compile(
        re.escape(name).replace(r"\-", r"[-_]"),
        re.IGNORECASE,
    )
    minimize_in_module = []
    minimize_re = re.compile(
        "|".join(re.escape(p) for p in MINIMIZE_PHRASES),
        re.IGNORECASE,
    )
    for f in _iter_scan_files():
        if not name_re.search(f.name):
            continue
        for lineno, line in _grep_lines(f, minimize_re):
            minimize_in_module.append({
                "file": str(f.relative_to(REPO_ROOT)),
                "line": lineno,
                "text": line[:160],
            })
    out = {
        "module": name,
        "surface_gaps": surface_gaps,
        "doc_gaps": doc_gaps,
        "minimize_phrases_in_module_files": minimize_in_module,
    }
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"── anti-minimization-audit.module {name} ──")
        if surface_gaps:
            for g in surface_gaps:
                print(f"  ✗ surface gap: {g['surface_count']}/8 "
                      f"(short {g['shortfall']})")
        else:
            print("  ✓ no surface gap")
        if doc_gaps:
            for g in doc_gaps:
                print(f"  ✗ doc gap: {g['doc_surface_count']}/6 "
                      f"(short {g['shortfall']})")
        else:
            print("  ✓ no doc gap")
        if minimize_in_module:
            print(f"  ✗ {len(minimize_in_module)} minimize-phrase "
                  f"matches in module files:")
            for m in minimize_in_module[:5]:
                print(f"    {m['file']}:{m['line']}  {m['text'][:80]}")
        else:
            print("  ✓ no minimize-phrases in module files")
    _emit_metric("module", "all", "ok")
    return 0


def cmd_cross_module(args) -> int:
    threshold = args.threshold if args.threshold is not None else 3
    surface = scan_surface_gap(threshold=threshold)
    doc = scan_doc_gap(threshold=threshold)
    # Modules short on BOTH axes — highest-priority anti-minimization
    surface_ids = {g["module"] for g in surface}
    doc_ids = {g["module"] for g in doc}
    short_both = sorted(surface_ids & doc_ids)
    short_only_surface = sorted(surface_ids - doc_ids)
    short_only_doc = sorted(doc_ids - surface_ids)
    out = {
        "threshold": threshold,
        "short_on_both_axes": short_both,
        "short_only_surface": short_only_surface,
        "short_only_doc": short_only_doc,
    }
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"── anti-minimization-audit.cross-module "
              f"(threshold={threshold}) ──")
        print(f"  ✗✗ short on BOTH axes ({len(short_both)}): "
              f"{', '.join(short_both) if short_both else '(none)'}")
        print(f"  ✗  short only on surface ({len(short_only_surface)}): "
              f"{', '.join(short_only_surface) if short_only_surface else '(none)'}")
        print(f"  ✗  short only on doc ({len(short_only_doc)}): "
              f"{', '.join(short_only_doc) if short_only_doc else '(none)'}")
    _emit_metric("cross-module", "all", "ok")
    return 0


def cmd_report(args) -> int:
    summary = {}
    for p in PATTERN_IDS:
        scanner = PATTERN_SCANNERS[p]
        if p in ("surface-gap", "doc-gap"):
            summary[p] = len(scanner())
        else:
            summary[p] = len(scanner(limit=None))
    total = sum(summary.values())
    out = {"summary": summary, "total": total}
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"── anti-minimization-audit.report "
              f"({total} total matches across "
              f"{len(PATTERN_IDS)} patterns) ──")
        for p in PATTERN_IDS:
            n = summary[p]
            mark = "✗" if n > 0 else "✓"
            print(f"  {mark} {p:22s} {n}")
    _emit_metric("report", "all", "ok")
    return 0


# --- R466 cross-repo selfdef AuditManifest discovery ---


def load_selfdef_audit_manifests() -> tuple[list[dict], list[dict]]:
    """Read every .toml under SELFDEF_AUDIT_DIR.

    Cross-repo binding: SD-R-AUDIT-1 (selfdef crate
    `selfdef-audit-manifest`).
    """
    valid: list[dict] = []
    errors: list[dict] = []
    if not SELFDEF_AUDIT_DIR.is_dir():
        return valid, errors
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[import-not-found]
        except ImportError:
            errors.append({
                "path": str(SELFDEF_AUDIT_DIR),
                "error": "no TOML library available",
            })
            return valid, errors
    valid_patterns = set(PATTERN_IDS)
    import os as _os
    for p in sorted(SELFDEF_AUDIT_DIR.glob("*.toml")):
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
        findings_in = data.get("findings") or []
        if not mod.get("id") or not findings_in:
            errors.append({
                "path": str(p),
                "error": "missing module.id or findings[]",
            })
            continue
        findings_out = []
        bad = None
        for f in findings_in:
            pat = f.get("pattern")
            count = f.get("count")
            if pat not in valid_patterns:
                bad = f"unknown pattern {pat!r}"
                break
            if not isinstance(count, int) or count < 0:
                bad = f"bad count {count!r} for {pat!r}"
                break
            findings_out.append({
                "pattern": pat,
                "count": int(count),
                "note": f.get("note"),
            })
        if bad:
            errors.append({"path": str(p), "error": bad})
            continue
        valid.append({
            "module": str(mod["id"]),
            "label": str(mod.get("label", mod["id"])),
            "findings": findings_out,
            "total_findings": sum(f["count"] for f in findings_out),
            "source_repo": "selfdef",
            "manifest_path": str(p),
        })
    return valid, errors


def cmd_selfdef(args) -> int:
    """Scan SELFDEF_AUDIT_DIR for cross-repo AuditManifests."""
    valid, errors = load_selfdef_audit_manifests()
    out = {
        "manifest_dir": str(SELFDEF_AUDIT_DIR),
        "discovered": valid,
        "errors": errors,
        "count": len(valid),
    }
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"── anti-minimization-audit.selfdef "
              f"({len(valid)} selfdef AuditManifest{'s' if len(valid)!=1 else ''} "
              f"under {SELFDEF_AUDIT_DIR}) ──")
        for m in valid:
            mark = "✓" if m["total_findings"] == 0 else "⚠"
            print(f"  {mark} {m['module']:25s} "
                  f"total_findings={m['total_findings']}  "
                  f"({m['label']})")
        for e in errors:
            print(f"  ✗ {e['path']}  {e['error']}")
    _emit_metric("selfdef", "any", "ok" if not errors else "issues")
    return 0


# --- Argparse ---


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="anti-minimization-audit.py",
        description=(
            "R456 (E11.M11): operator §1g 'do not minimize or settle "
            "for less' standing-rule audit. Scans codebase for 8 "
            "operator-named minimization patterns and surfaces them "
            "for re-audit."
        ),
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def _add_fmt(sp):
        g = sp.add_mutually_exclusive_group()
        g.add_argument("--json", dest="fmt", action="store_const",
                       const="json", default="human")
        g.add_argument("--human", dest="fmt", action="store_const",
                       const="human")

    sp_pat = sub.add_parser("patterns",
                            help="enumerate the 8 patterns")
    _add_fmt(sp_pat)

    sp_scan = sub.add_parser("scan",
                             help="scan repo for matches (all or one)")
    sp_scan.add_argument("--pattern", help="filter to one pattern id")
    sp_scan.add_argument("--limit", type=int, default=None,
                         help="max matches per pattern")
    sp_scan.add_argument("--json-flag", dest="json",
                         action="store_true", default=False)
    _add_fmt(sp_scan)

    sp_mod = sub.add_parser("module", help="per-module audit")
    sp_mod.add_argument("name")
    _add_fmt(sp_mod)

    sp_x = sub.add_parser("cross-module",
                          help="surface × doc gap intersection")
    sp_x.add_argument("--threshold", type=int, default=None)
    _add_fmt(sp_x)

    sp_rep = sub.add_parser("report",
                            help="one-screen summary")
    _add_fmt(sp_rep)

    sp_sd = sub.add_parser(
        "selfdef",
        help=("R466 cross-repo: scan SELFDEF_AUDIT_DIR for selfdef-side "
              "AuditManifests (SD-R-AUDIT-1)"),
    )
    _add_fmt(sp_sd)

    args = p.parse_args(argv)
    return {
        "patterns": cmd_patterns,
        "scan": cmd_scan,
        "module": cmd_module,
        "cross-module": cmd_cross_module,
        "report": cmd_report,
        "selfdef": cmd_selfdef,
    }[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
