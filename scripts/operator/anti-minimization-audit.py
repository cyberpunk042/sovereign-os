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
    # R476: bare verb "minimize" removed — it produced systematic
    # false positives on hardware/power-optimization code
    # ("minimize wattage", "minimize disk I/O") and on doctrine
    # echoes of the operator's own rule ("do not minimize anything").
    # The semantically-meaningful admission signal lives in the noun
    # "minimization" + the explicit "TODO: minimize" anchor + the
    # longer phrases below.
    "minimization",
    "placeholder",
    "simplified",
    "we can improve later",
    "good enough",
    "quick and dirty",
    "TODO: minimize",
]

# R476: precision filters consulted by scan_minimize_phrase as a
# belt-and-suspenders layer over the MINIMIZE_PHRASES regex. Each
# filter targets one class of structural false-positive observed in
# the live repo at R475:
#
#   • Tool-self-reference  — callsites and tests that name the audit
#     tool ("anti-minimization-audit" / "anti_minimization_audit" /
#     "Anti-minimization audit") incidentally hit the "minimization"
#     phrase regex. These are infrastructure, not minimization debt.
#
#   • Doctrine-echo        — operator-verbatim quotes of the
#     standing rule ("do not minimize", "Never minimize", "not
#     minimize anything") surface in mandate-quote callouts inside
#     SDDs / handoff docs / charter / source comments. Quoting the
#     anti-minimization mandate is not itself minimization.
#
#   • Sed-sentinel         — test fixtures using the uppercase
#     literal "PLACEHOLDER" as a sed substitution marker
#     (`sed -i "s|PLACEHOLDER|...|"` / `path = "PLACEHOLDER"`).
#     This is a feature-of-the-system substitution pattern, not
#     minimization debt.
#
# Each filter is exposed as a module-level constant so the contract
# test suite can assert on its match/non-match behavior independently
# (the same discipline R474 applied to `_is_waived`).
_MINIMIZE_TOOL_SELFREF_RE = re.compile(
    r"anti[-_]minimization[-_ ]audit|Anti[-_ ]minimization",
)
_MINIMIZE_DOCTRINE_ECHO_RE = re.compile(
    # Quoted/echoed operator mandate of the form
    # "do/not/never/without minimize/minimization ...". Matching is
    # case-insensitive and tolerates a word in between
    # ("do not [rush, but never] minimize ...").
    r"\b(?:do\s+not|don'?t|never|without)\b[^.]{0,40}\bminimi[sz]"
    r"|\bnot\s+minimi[sz]e\s+anything\b"
    # R479: meta-discourse vocabulary about the doctrine itself —
    # comments / docstrings / tests that NAME the practice in order
    # to discuss / classify / forbid it. NOT admissions; doctrine
    # echoes. R478's surface-ceiling commentary surfaced 3 such
    # false-positives this round:
    #   "...is structural, not a minimization to close."
    #   "are not minimization candidates"
    #   "not minimization-by-silence"
    # plus the project-name-style compound "anti-minimization".
    r"|\bnot\s+(?:a|the|an)\s+minimi[sz](?:e|ation|ing)\b"
    r"|\bnot\s+minimi[sz](?:ation|ing)\b"
    r"|\bminimi[sz]ation[\s-]+(?:to|by|as)\b"
    r"|\banti[\s-]?minimi[sz]ation\b"
    # R491: doctrine-echo phrasing that NAMES what §1g forbids — comments,
    # docstrings, and gate rationales of the form "the minimization §1g
    # forbids" / "the exact minimization §1g forbids" / "minimization the
    # §1g rule forbids". These DESCRIBE the practice in order to forbid it
    # (the gate is preventing it) — not admissions. Tied to the literal
    # "forbid" so it can't overshoot a real admission (which never pairs
    # "minimization" with "forbid"). Plus the reflexive "itself a
    # minimization" (base-catalog: "from a hardening catalog is itself a
    # minimization") — discussing the concept, not confessing one.
    r"|\bminimi[sz]ation\b[^.\n]{0,40}\bforbid"
    r"|\bitself\s+(?:a|an)\s+minimi[sz]ation\b",
    re.IGNORECASE,
)
_MINIMIZE_SED_SENTINEL_RE = re.compile(
    # Either a bare uppercase PLACEHOLDER assignment ('path =
    # "PLACEHOLDER"', PATH=PLACEHOLDER) OR a sed-substitution-style
    # `s<sep>PLACEHOLDER<sep>` test marker. The all-caps + sentinel
    # context distinguishes this from prose use of the word.
    r"['\"`]PLACEHOLDER['\"`]"
    r"|=\s*PLACEHOLDER\b"
    r"|\bs[/|]PLACEHOLDER[/|]",
)

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


# R474 audit-waiver annotation: operator can mark a line as known-OK
# by appending an inline waiver comment. Pattern:
#
#   # anti-min-waiver: <R-number-or-SDD-anchor> <rationale-text>
#
# Examples:
#   foo = bar  # anti-min-waiver: R474 placeholder fixture for test
#   # TODO clean up  # anti-min-waiver: R-arc-cleanup-deferred-by-design
#
# The annotation MUST carry an anchor (R<N> / SDD-<N> / E<N>.M<N> /
# R-arc-* / SD-R-*) so it itself isn't a 'todo-no-anchor' violation.
# This is operator-§1g 'covered all angles' — the waiver mechanism
# itself follows the anti-fabrication discipline.
WAIVER_MARKER = "anti-min-waiver:"
_WAIVER_RE = re.compile(
    r"anti-min-waiver:\s*"
    r"(?P<anchor>R\d+|SDD-\d+|E\d+\.M\d+|R-arc-[\w-]+|SD-R-[\w-]+)"
    r"\s+(?P<rationale>\S.*)$"
)


def _is_waived(line: str) -> bool:
    """True if line contains a properly-anchored waiver annotation."""
    return bool(_WAIVER_RE.search(line))


def _waiver_anchor(line: str) -> str | None:
    m = _WAIVER_RE.search(line)
    return m.group("anchor") if m else None


# R475: shared self-exclusion list applied to ALL text-based scanners.
# These files DEFINE/DOCUMENT/REFERENCE the anti-minimization patterns
# (TODO + 'skipped'/'deferred' + minimize-phrase) verbatim and would
# otherwise be perpetual false-positives.
SHARED_SELF_EXCLUSIONS = frozenset({
    # Operator-mandate / SDDs / handoff docs that discuss the
    # minimization patterns BY NAME (operator-§1g verbatim content).
    "docs/standing-directives/2026-05-17-operator-mandate.md",
    "docs/standing-directives/mandate-review-2026-Q2.md",
    "docs/standing-directives/goal-rearming.md",
    "docs/sdd/033-perpetual-intake-doctrine.md",
    "docs/sdd/038-cross-repo-binding-doctrine.md",
    "docs/handoff/002-foundation-substantive-buildout.md",
    "docs/handoff/006-verbatim-preservation-arc.md",
    # The audit module + its sister wrappers + its own lints.
    "scripts/operator/anti-minimization-audit.py",
    "scripts/operator/compliance.py",
    "scripts/operator/README.md",
    "scripts/sovereign-osctl",  # osctl help text describes the patterns
    "tests/lint/test_anti_minimization_audit_contract.py",
    "tests/lint/test_cross_repo_saturation_invariant.py",
    "tests/lint/test_operator_mandate_doc_invariants.py",
    "tests/lint/test_cross_repo_compliance_end_to_end.py",
    "tests/lint/test_epic_e11_cross_repo_coverage.py",
    "tests/lint/test_coverage_axes_catalog.py",
    "tests/lint/test_mandate_section_1_subsections.py",
    "tests/lint/test_rearm_goal_script.py",
    "tests/lint/test_verbatim_preservation_doctrine.py",
    # Sister intelligence tools that REPORT on TODOs / partials /
    # minimization patterns (operator-named status-aggregator scripts).
    "scripts/intelligence/coverage-map.py",
    "scripts/intelligence/quarterly-review.py",
    "scripts/intelligence/verbatim-render.py",
    # nspawn tests that assert on operator-named '0 TODO / 0 partial'
    # success states.
    "tests/nspawn/test_coverage_map.sh",
    "tests/nspawn/test_quarterly_review.sh",
    "tests/nspawn/test_repl.sh",
    # R475: whitelabel / brand-identity-placeholder domain-vocabulary
    # exclusions. 'placeholder' here means OPERATOR-SUBSTITUTABLE
    # brand-identity slot (the canonical term in the cross-cutting
    # SDD-012 brand-identity-placeholder doctrine), NOT minimization
    # debt. The cloud-init / whitelabel verbatim-test files assert on
    # exact placeholder strings as feature-of-the-system.
    "docs/sdd/012-brand-identity-placeholder.md",
    "docs/sdd/005-initial-profiles.md",
    "docs/sdd/007-whitelabel-mechanism.md",
    "docs/sdd/004-profile-schema.md",
    "docs/sdd/INDEX.md",
    "docs/observability/dashboards/README.md",
    "docs/src/verbatim-surface.md",
    "docs/decisions.md",
    "tests/lint/test_cloud_init_templates_verbatim.py",
    "tests/lint/test_whitelabel_default_yaml_content.py",
    "tests/lint/test_preseed_content_verbatim.py",
    "tests/nspawn/test_workflow.sh",
    "tests/nspawn/test_whitelabel_render_live_build.sh",
    "whitelabel/default.yaml",
    "profiles/mixins/whitelabel-default.yaml",
    # R476: extend the whitelabel + profile + master-spec operator-
    # vocabulary domain. These files use "placeholder" as the
    # operator-canonical term for brand-identity-substitutable slots
    # (per SDD-012) + hardware-placeholder slots (per profile
    # doctrine) + tracker-anchored deferred items (per the
    # questions.md registry + SDD-037 doctrine). They are operator-
    # vocabulary DATA, not minimization debt.
    "whitelabel/INDEX.md",
    "whitelabel/default/README.md",
    "whitelabel/default/overlays/grub-theme/README.md",
    "profiles/INDEX.md",
    "profiles/old-workstation.yaml",
    "profiles/sain-01.yaml",
    "docs/src/whitelabel/mechanism.md",
    "docs/src/whitelabel/inventory.md",
    "docs/src/profiles/old-workstation.md",
    "docs/src/profiles/sain-01.md",
    "docs/src/sain-01-master-spec.md",
    "docs/src/model-catalog.md",
    "docs/src/questions.md",
    "models/catalog.yaml",
    # R476: tdd bug-catalog references previous bug fixtures by
    # their literal source-string ("placeholder" appears inside a
    # bug-description quote). This file is a forensic ledger, not
    # a minimization admission.
    "docs/src/tdd/bugs-caught.md",
    # R476: lint/nspawn tests that DESCRIBE the placeholder-as-
    # template-substitution feature (their text mentions
    # "placeholder verbs", "{placeholders}" assertions). They
    # are documentation of the feature, not its admission.
    "tests/lint/test_verb_dispatch_refs.py",
    "tests/lint/test_verbatim_spec_ref_format.py",
    "tests/lint/test_metric_inventory_lockstep.py",
    "tests/nspawn/test_orchestrator_rewind_skip.sh",
    "tests/nspawn/test_lifecycle.sh",
})


def scan_todo_no_anchor(limit: int | None = None) -> list[dict]:
    """TODO/FIXME without R-number (R\\d+) or SDD anchor (SDD-\\d+).

    R474: lines carrying a properly-anchored `anti-min-waiver:`
    annotation are skipped (operator-explicit known-OK).
    R475: sister-doctrine files self-excluded."""
    todo_re = re.compile(r"\b(?:TODO|FIXME)\b", re.IGNORECASE)
    anchor_re = re.compile(r"\b(?:R\d+|SDD-\d+|E\d+\.M\d+)\b")
    matches = []
    for f in _iter_scan_files():
        if str(f.relative_to(REPO_ROOT)) in SHARED_SELF_EXCLUSIONS:
            continue
        for lineno, line in _grep_lines(f, todo_re):
            if _is_waived(line):
                continue
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
    """'skipped'/'deferred'/'stub' without ticket/issue/R-number ref.

    R474: lines carrying an `anti-min-waiver:` annotation skipped.
    R475: sister-doctrine files self-excluded + context-word
    requirement (the keyword MUST appear adjacent to a context word
    that signals DEFERRED WORK — 'for now', 'until', 'pending',
    'out', 'TODO', 'FIXME' — so domain-vocabulary uses like
    'module skipped per policy' or 'beta skipped' (test fixture)
    don't fire as false-positives)."""
    # The keyword must appear next to a deferred-work signal. This
    # is the operator-§1g intent of the pattern: catch software
    # work that got pushed off WITHOUT a tracking anchor, not
    # operational vocabulary that happens to use the same word.
    keyword_re = re.compile(
        r"\b(?:skipped|deferred|stubbed?)\b"
        r"(?:\s+(?:for\s+now|until|pending|out\b|to\s+(?:M\d+|stage|phase|gate))"
        r"|\s*(?:[—:-]+\s*)?(?:TODO|FIXME)\b"
        r"|\s+(?:later|for\s+M\d+))",
        re.IGNORECASE,
    )
    # R477: phase-anchor vocabulary recognized as a valid tracking
    # anchor. The operator's standing structure uses `Stage <N>+`
    # and `Phase <N>` as first-class boundary anchors (Stage 1 / 2+
    # / 3 / 4 surface throughout SDDs, profiles, mandate, handoff
    # docs); `M<N>` is the module-counter inside an epic. A deferral
    # carrying any of these IS tracked-and-closed in the operator's
    # phase machinery, even when no R-number is yet assigned (the
    # work is bounded by phase boundary, not by individual ticket).
    anchor_re = re.compile(
        r"\b(?:R\d+|SDD-\d+|#\d+|issue|E\d+\.M\d+"
        r"|Stage\s+\d+\+?|Phase\s+\d+\+?|M\d+)\b",
        re.IGNORECASE,
    )
    matches = []
    for f in _iter_scan_files():
        if str(f.relative_to(REPO_ROOT)) in SHARED_SELF_EXCLUSIONS:
            continue
        for lineno, line in _grep_lines(f, keyword_re):
            if _is_waived(line):
                continue
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
    R474 SDD-038/R473 saturation lint excluded (defines waivers
    + saturation policy that mentions minimize-phrases verbatim).

    R474: lines carrying an `anti-min-waiver:` annotation skipped.
    R476: bare verb "minimize" dropped from MINIMIZE_PHRASES; three
    precision filters (_MINIMIZE_TOOL_SELFREF_RE /
    _MINIMIZE_DOCTRINE_ECHO_RE / _MINIMIZE_SED_SENTINEL_RE) consulted
    per candidate line to suppress structural false-positives. See
    each constant's docstring for rationale.
    """
    pat_re = re.compile(
        "|".join(re.escape(p) for p in MINIMIZE_PHRASES),
        re.IGNORECASE,
    )
    # R475: use shared self-exclusion list (same files that the other
    # text scanners skip — sister-doctrine documents discuss the
    # patterns by name and would otherwise be perpetual false-positives).
    matches = []
    for f in _iter_scan_files():
        rel = str(f.relative_to(REPO_ROOT))
        if rel in SHARED_SELF_EXCLUSIONS:
            continue
        for lineno, line in _grep_lines(f, pat_re):
            if _is_waived(line):
                continue
            # R476: precision filters — skip lines that are structural
            # false-positives (tool-self-reference, operator-mandate
            # doctrine-echo quotes, sed-substitution sentinel markers).
            if _MINIMIZE_TOOL_SELFREF_RE.search(line):
                continue
            if _MINIMIZE_DOCTRINE_ECHO_RE.search(line):
                continue
            if _MINIMIZE_SED_SENTINEL_RE.search(line):
                continue
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


def cmd_waivers(args) -> int:
    """R474: list every active `anti-min-waiver:` annotation in the
    repo. Operator-discoverable: every known-OK exemption surfaces
    with its anchor + rationale, so the operator can audit waivers
    themselves (operator-§1g 'covered all angles' — waivers cannot
    hide; they're listed alongside the audit's main findings)."""
    matches: list[dict] = []
    for f in _iter_scan_files():
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            m = _WAIVER_RE.search(line)
            if not m:
                continue
            matches.append({
                "file": str(f.relative_to(REPO_ROOT)),
                "line": i,
                "anchor": m.group("anchor"),
                "rationale": m.group("rationale")[:160],
            })
    out = {"waivers": matches, "count": len(matches)}
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"── anti-minimization-audit.waivers "
              f"({len(matches)} active operator-explicit waivers) ──")
        for w in matches:
            print(f"  {w['file']}:{w['line']}  "
                  f"[{w['anchor']}]  {w['rationale']}")
    _emit_metric("waivers", "all", "ok")
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

    sp_w = sub.add_parser(
        "waivers",
        help=("R474: list active 'anti-min-waiver:' annotations "
              "(operator-explicit known-OK exemptions)"),
    )
    _add_fmt(sp_w)

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
        "waivers": cmd_waivers,
        "selfdef": cmd_selfdef,
    }[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
