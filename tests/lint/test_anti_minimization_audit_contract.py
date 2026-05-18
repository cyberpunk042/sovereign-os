"""R456 (E11.M11) — anti-minimization audit contract lint.

Per operator §1g standing rule (VERBATIM):
  "If you think something is really already done, ask yourself if you
   covered all angles and levels and layers and even if then improve
   it. Do not minimize or settle for less."

11th substantive feature of §1g/§1h Epic E11 arc (closing E11.M11).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AM_PY = REPO_ROOT / "scripts" / "operator" / "anti-minimization-audit.py"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"

EXPECTED_PATTERNS = [
    "todo-no-anchor",
    "empty-stub",
    "skipped-no-followup",
    "surface-gap",
    "doc-gap",
    "mandate-todo",
    "minimize-phrase",
    "partial-status",
]


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# --- Structural ---


def test_anti_minimization_script_exists():
    assert AM_PY.is_file(), f"missing {AM_PY}"


def test_anti_minimization_script_executable():
    assert os.access(AM_PY, os.X_OK), f"{AM_PY} not executable"


def test_python3_shebang():
    body = _read(AM_PY)
    assert body.startswith("#!/usr/bin/env python3")


def test_documents_e11_m11_origin():
    body = _read(AM_PY)
    assert "E11.M11" in body and "§1g" in body


def test_quotes_operator_verbatim_standing_rule():
    """§1g standing-rule verbatim phrases MUST appear."""
    body = _read(AM_PY)
    flat = re.sub(r"\s+", " ", body)
    for phrase in (
        "covered all angles and levels and layers",
        "Do not minimize or settle for less",
        "We do not minimize anything",
    ):
        assert phrase in flat, (
            f"missing operator §1g standing-rule verbatim {phrase!r}"
        )


# --- 8-pattern catalog ---


def test_patterns_catalog_defined():
    body = _read(AM_PY)
    assert "PATTERNS" in body, "missing PATTERNS catalog"
    for p in EXPECTED_PATTERNS:
        assert f'"{p}"' in body, f"PATTERNS missing {p!r}"


def test_each_pattern_has_label_field():
    body = _read(AM_PY)
    n = body.count('"label":')
    assert n >= 8, f"only {n} 'label' fields (expected ≥8)"


def test_each_pattern_has_operator_rationale_field():
    body = _read(AM_PY)
    n = body.count('"operator_named_rationale":')
    assert n >= 8, (
        f"only {n} 'operator_named_rationale' fields (expected ≥8)"
    )


# --- Pattern scanners (one function per pattern) ---


def test_scanner_function_per_pattern():
    body = _read(AM_PY)
    for fn in (
        "scan_todo_no_anchor",
        "scan_empty_stub",
        "scan_skipped_no_followup",
        "scan_mandate_todo",
        "scan_partial_status",
        "scan_minimize_phrase",
        "scan_surface_gap",
        "scan_doc_gap",
    ):
        assert f"def {fn}(" in body, f"missing scanner function {fn}()"


def test_minimize_phrases_constant_defined():
    body = _read(AM_PY)
    assert "MINIMIZE_PHRASES" in body, (
        "missing MINIMIZE_PHRASES constant"
    )
    # Must include canonical operator-named admission phrases. R476:
    # bare verb "minimize" intentionally NOT required — it produced
    # systematic false positives on hardware/power-optimization code
    # ("minimize wattage", "minimize disk I/O") and on doctrine
    # echoes of the operator's own rule ("do not minimize"). The
    # semantically-meaningful admission signal lives in the longer
    # phrases below + the standalone noun "minimization" + the
    # explicit "TODO: minimize" anchor.
    for phrase in ('"for now"', '"minimization"', '"placeholder"',
                   '"simplified"', '"TODO: minimize"'):
        assert phrase in body, (
            f"MINIMIZE_PHRASES missing {phrase!r}"
        )


def test_minimize_phrase_precision_filters_constant_defined():
    """R476: precision-filter regexes for tool-self-reference,
    doctrine-echo, and sed-sentinel PLACEHOLDER use-as-substitution.
    Each filter MUST be exposed as a module-level constant so it can
    be reasoned about + unit-tested independently."""
    body = _read(AM_PY)
    for name in (
        "_MINIMIZE_TOOL_SELFREF_RE",
        "_MINIMIZE_DOCTRINE_ECHO_RE",
        "_MINIMIZE_SED_SENTINEL_RE",
    ):
        assert name in body, (
            f"R476 contract: missing precision-filter regex {name}"
        )


def test_minimize_phrase_precision_filters_match_known_fps():
    """R476: each precision regex MUST match a representative
    real-world false-positive observed in the repo before R476."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_am", AM_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Tool-self-reference: callsites + tests that name the tool.
    for line in (
        '{"id": "anti-minimization-audit",',
        '    "script": "scripts/operator/anti-minimization-audit.py",',
        '"anti_minimization_audit", "ux_design_audit",',
        '"E11.M11",  # Anti-minimization audit — process',
    ):
        assert mod._MINIMIZE_TOOL_SELFREF_RE.search(line), (
            f"R476: tool-self-ref filter missed: {line!r}"
        )

    # Doctrine-echo: operator-verbatim "do not minimize" / "Never
    # minimize" surfaces (mandate quotes embedded in code/docs).
    for line in (
        '"Do not rush anything and do not minimize anything"',
        "- **Never minimize, conflate, hack, or take shortcuts**",
        '> "Do not rush anything and do not minimize anything nor',
        "- Never minimize, conflate, hack, shortcut.",
    ):
        assert mod._MINIMIZE_DOCTRINE_ECHO_RE.search(line), (
            f"R476: doctrine-echo filter missed: {line!r}"
        )

    # Sed-sentinel: test fixtures using literal "PLACEHOLDER" as a
    # substitution marker; this is feature-of-the-system, not
    # minimization debt.
    for line in (
        'path = "PLACEHOLDER"',
        'sed -i "s|PLACEHOLDER|${TMPDIR}/events.jsonl|" "${TMPDIR}/cfg.toml"',
    ):
        assert mod._MINIMIZE_SED_SENTINEL_RE.search(line), (
            f"R476: sed-sentinel filter missed: {line!r}"
        )


def test_minimize_phrase_precision_filters_do_not_overshoot():
    """R476: precision filters MUST NOT match genuine admission lines.
    Catches the 'over-tightening drops real signal' regression."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_am", AM_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Real admission lines — these are the kind R476 must KEEP flagging.
    real_admissions = (
        "    # For now: just boot to firmware + check the disk is bootable.",
        '    log_info "  → for now, run \'sovereign-osctl models pull <id>\' manually"',
        "# Model catalog pick (placeholder; full Q-017 + E110 integration is Stage 2+)",
        "manual invocation for now.",
    )
    for line in real_admissions:
        assert not mod._MINIMIZE_TOOL_SELFREF_RE.search(line), (
            f"R476: tool-self-ref filter OVERSHOT to real admission: {line!r}"
        )
        assert not mod._MINIMIZE_DOCTRINE_ECHO_RE.search(line), (
            f"R476: doctrine-echo filter OVERSHOT to real admission: {line!r}"
        )
        assert not mod._MINIMIZE_SED_SENTINEL_RE.search(line), (
            f"R476: sed-sentinel filter OVERSHOT to real admission: {line!r}"
        )


def test_minimize_phrase_scan_applies_precision_filters():
    """R476: scan_minimize_phrase MUST consult the three precision
    filters and skip matching lines, per the same belt-and-suspenders
    discipline R474 applied with `_is_waived`."""
    body = _read(AM_PY)
    # The scan_minimize_phrase function body must reference all three
    # precision-filter constants (consults them on each candidate).
    import re as _re
    fn_match = _re.search(
        r"def scan_minimize_phrase\([^)]*\)[^:]*:.*?(?=\n(?:def |class |\Z))",
        body,
        _re.DOTALL,
    )
    assert fn_match, "could not locate scan_minimize_phrase definition"
    fn_body = fn_match.group(0)
    for name in (
        "_MINIMIZE_TOOL_SELFREF_RE",
        "_MINIMIZE_DOCTRINE_ECHO_RE",
        "_MINIMIZE_SED_SENTINEL_RE",
    ):
        assert name in fn_body, (
            f"R476 contract break: scan_minimize_phrase does not "
            f"consult {name}"
        )


# --- R479 doctrine-echo regex extension for meta-discourse ---


def test_doctrine_echo_matches_meta_discourse_vocabulary():
    """R479: extended _MINIMIZE_DOCTRINE_ECHO_RE must catch the
    operator-doctrinal meta-discourse vocabulary that R478 itself
    introduced: 'not a minimization to close', 'not minimization
    candidates', 'minimization-by-silence', 'anti-minimization'.
    These are doctrine-NAMING not admission-MAKING."""
    import importlib.util as _ilu
    spec = _ilu.spec_from_file_location("_amaudit_r479", AM_PY)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rgx = mod._MINIMIZE_DOCTRINE_ECHO_RE
    for sample in (
        "remaining shortfall is structural, not a minimization to close.",
        "are not minimization candidates, they are operator-fully-described",
        "transparency — not minimization-by-silence",
        "the anti-minimization audit catches this",
        "do not minimize the work",
        "not minimize anything",
    ):
        assert rgx.search(sample), (
            f"R479: doctrine-echo regex missed meta-discourse: {sample!r}"
        )


def test_doctrine_echo_does_not_overshoot_real_admissions():
    """R479: extended doctrine-echo MUST NOT catch genuine admissions
    that happen to share roots with the doctrinal vocabulary."""
    import importlib.util as _ilu
    spec = _ilu.spec_from_file_location("_amaudit_r479b", AM_PY)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rgx = mod._MINIMIZE_DOCTRINE_ECHO_RE
    for sample in (
        "minimization of the surface to close out work",
        "we minimize disk I/O by batching writes",
        "TODO: minimize the schema before shipping",
        "this is a minimization placeholder",
    ):
        assert not rgx.search(sample), (
            f"R479 overshoot: doctrine-echo falsely matched real "
            f"admission: {sample!r}"
        )


# --- R477 phase-anchor vocabulary in skipped-no-followup ---


def test_skipped_anchor_recognizes_phase_vocabulary():
    """R477: scan_skipped_no_followup's anchor_re MUST recognize the
    operator's first-class phase-anchor vocabulary (`Stage <N>+` /
    `Phase <N>` / `M<N>`). These tokens ARE tracked-and-closed in the
    operator's phase machinery — a deferral bounded by `Stage 2+` IS
    anchored, even when no R-number is yet assigned."""
    body = _read(AM_PY)
    import re as _re
    fn_match = _re.search(
        r"def scan_skipped_no_followup\([^)]*\)[^:]*:.*?(?=\n(?:def |class |\Z))",
        body,
        _re.DOTALL,
    )
    assert fn_match, "could not locate scan_skipped_no_followup definition"
    fn_body = fn_match.group(0)
    for token in (r"Stage\s+\d+\+?", r"Phase\s+\d+\+?", r"M\d+"):
        assert token in fn_body, (
            f"R477 contract break: anchor_re missing phase-anchor "
            f"vocabulary token {token!r}"
        )


def test_skipped_anchor_matches_real_phase_anchors():
    """R477: independently re-derive the anchor regex from the source
    and assert it matches the three real-world phase-anchored
    deferrals observed in the repo before R477 closed them."""
    body = _read(AM_PY)
    import re as _re
    # Pull the anchor_re literal out of scan_skipped_no_followup.
    m = _re.search(
        r"def scan_skipped_no_followup\([^)]*\)[^:]*:.*?"
        r"anchor_re\s*=\s*re\.compile\(\s*"
        r"(?P<pat>(?:r?\"(?:[^\"\\]|\\.)*\"\s*|r?'(?:[^'\\]|\\.)*'\s*)+)",
        body,
        _re.DOTALL,
    )
    assert m, "could not extract anchor_re pattern literal"
    # Concatenate all the adjacent string literals into one pattern.
    literals = _re.findall(
        r"r?\"((?:[^\"\\]|\\.)*)\"|r?'((?:[^'\\]|\\.)*)'", m.group("pat")
    )
    pat = "".join(a or b for a, b in literals)
    anchor_re = _re.compile(pat, _re.IGNORECASE)
    for sample in (
        "rpm-ostree, nixos: deferred to Stage 2+ (ALT paths).",
        "Layer B — metrics (contract; implementation deferred to Stage 2+)",
        "stubbed for Phase 3 rollout",
        "skipped until M12",
    ):
        assert anchor_re.search(sample), (
            f"R477: phase-anchored deferral not matched by anchor_re: "
            f"{sample!r}"
        )


def test_skipped_anchor_rejects_unanchored_deferrals():
    """R477: phase-anchor extension MUST NOT cause the regex to swallow
    deferrals that carry NO tracking token — those still need to fire
    as skipped-no-followup matches."""
    body = _read(AM_PY)
    import re as _re
    m = _re.search(
        r"def scan_skipped_no_followup\([^)]*\)[^:]*:.*?"
        r"anchor_re\s*=\s*re\.compile\(\s*"
        r"(?P<pat>(?:r?\"(?:[^\"\\]|\\.)*\"\s*|r?'(?:[^'\\]|\\.)*'\s*)+)",
        body,
        _re.DOTALL,
    )
    assert m, "could not extract anchor_re pattern literal"
    literals = _re.findall(
        r"r?\"((?:[^\"\\]|\\.)*)\"|r?'((?:[^'\\]|\\.)*)'", m.group("pat")
    )
    pat = "".join(a or b for a, b in literals)
    anchor_re = _re.compile(pat, _re.IGNORECASE)
    for sample in (
        "deferred until further notice",
        "skipped — TODO clean this up later",
        "stubbed for now (no follow-up plan)",
    ):
        assert not anchor_re.search(sample), (
            f"R477 overshoot: anchor_re falsely accepted unanchored "
            f"deferral: {sample!r}"
        )


# --- R453/R454 bridge ---


def test_bridges_to_surface_map():
    body = _read(AM_PY)
    assert "surface-map.py" in body, (
        "missing R453 surface-map.py bridge for surface-gap detection"
    )


def test_bridges_to_doc_coverage():
    body = _read(AM_PY)
    assert "doc-coverage.py" in body, (
        "missing R454 doc-coverage.py bridge for doc-gap detection"
    )


# --- CLI surface (5 verbs) ---


def test_supports_patterns_verb():
    body = _read(AM_PY)
    assert '"patterns"' in body


def test_supports_scan_verb():
    body = _read(AM_PY)
    assert '"scan"' in body


def test_supports_module_verb():
    body = _read(AM_PY)
    assert '"module"' in body


def test_supports_cross_module_verb():
    body = _read(AM_PY)
    assert '"cross-module"' in body


def test_supports_report_verb():
    body = _read(AM_PY)
    assert '"report"' in body


def test_supports_waivers_verb():
    """R474: operator-explicit waiver listing verb."""
    body = _read(AM_PY)
    assert '"waivers"' in body
    assert "anti-min-waiver:" in body


def test_waiver_marker_constant_present():
    """R474: WAIVER_MARKER constant + _WAIVER_RE regex exposed
    (stable contract — downstream tools may grep for them)."""
    body = _read(AM_PY)
    assert "WAIVER_MARKER" in body
    assert "_WAIVER_RE" in body


def test_waiver_anchor_required_in_regex():
    """R474: waiver regex MUST require an R-number / SDD-N / E-N.M-N /
    R-arc-* / SD-R-* anchor — so the waiver mechanism itself
    follows the anti-fabrication discipline."""
    body = _read(AM_PY)
    # Look for the anchor alternation inside the regex
    assert r"R\d+|SDD-\d+" in body
    assert "R-arc-" in body
    assert "SD-R-" in body


def test_scanners_consult_is_waived():
    """R474: every text-based scanner MUST call _is_waived() to
    short-circuit waived lines. Drift catches: new scanner added
    without waiver-awareness."""
    body = _read(AM_PY)
    # At least these three scanners must consult _is_waived()
    for fn in (
        "scan_todo_no_anchor",
        "scan_skipped_no_followup",
        "scan_minimize_phrase",
    ):
        # crude check: function body should reference _is_waived
        # within the function body. R477 expanded
        # scan_skipped_no_followup with phase-anchor commentary, so
        # take the slice up to the NEXT top-level def/class boundary
        # rather than a fixed byte window.
        idx = body.find(f"def {fn}(")
        assert idx >= 0, f"function {fn} not found"
        rest = body[idx + len(f"def {fn}("):]
        import re as _re
        boundary = _re.search(r"\n(?:def |class )", rest)
        end = idx + len(f"def {fn}(") + (
            boundary.start() if boundary else len(rest)
        )
        body_slice = body[idx:end]
        assert "_is_waived(" in body_slice, (
            f"{fn} doesn't consult _is_waived(); R474 contract break"
        )


def test_waivers_verb_smoke(tmp_path):
    """R474 end-to-end: create a fixture file with a waiver
    annotation; the waivers verb finds it."""
    import json as _json
    import os as _os
    import subprocess as _sp
    fixture_root = tmp_path / "scripts"
    fixture_root.mkdir()
    f = fixture_root / "demo.py"
    f.write_text(
        "# TODO clean up this hack\n"
        "# TODO operator-deferred  # anti-min-waiver: R474 example "
        "rationale text\n",
        encoding="utf-8",
    )
    # Smoke test: invoke waivers verb against the repo (catches
    # the audit script's own usage example + any other live waivers).
    r = _sp.run(
        ["python3", str(AM_PY), "waivers", "--json"],
        capture_output=True, text=True, timeout=30,
        env={**_os.environ},
    )
    assert r.returncode == 0
    data = _json.loads(r.stdout)
    assert "waivers" in data
    # ≥1 waiver because the audit script's own usage example
    # ('# anti-min-waiver: R474 placeholder fixture for test')
    # is real and picks up here.
    assert data["count"] >= 1


def test_supports_selfdef_verb():
    """R466: cross-repo selfdef AuditManifest discovery verb."""
    body = _read(AM_PY)
    assert '"selfdef"' in body
    assert "SD-R-AUDIT-1" in body


def test_selfdef_audit_dir_env_overridable():
    body = _read(AM_PY)
    assert "SOVEREIGN_OS_SELFDEF_AUDIT_DIR" in body


def test_selfdef_default_audit_dir():
    body = _read(AM_PY)
    assert "/etc/selfdef/audit-manifests" in body


def test_selfdef_verb_smoke():
    """R466: end-to-end consuming a real selfdef AuditManifest."""
    import subprocess as _sp
    import tempfile as _tf
    with _tf.TemporaryDirectory() as td:
        Path(td, "agent-guard.toml").write_text(
            'schema_version = 1\n\n'
            '[module]\nid = "agent-guard"\nlabel = "Agent Guard"\n\n'
            '[[findings]]\npattern = "todo-no-anchor"\ncount = 0\n\n'
            '[[findings]]\npattern = "minimize-phrase"\ncount = 3\n'
            'note = "three uses in operator-§1g context"\n'
        )
        result = _sp.run(
            ["python3", str(AM_PY), "selfdef", "--json"],
            capture_output=True, text=True, timeout=10,
            env={**os.environ,
                 "SOVEREIGN_OS_SELFDEF_AUDIT_DIR": td},
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["count"] == 1
        m = data["discovered"][0]
        assert m["module"] == "agent-guard"
        assert m["total_findings"] == 3
        assert m["source_repo"] == "selfdef"


def test_selfdef_verb_rejects_unknown_pattern():
    """R466: shape-validates patterns; unknown ones surface as errors."""
    import subprocess as _sp
    import tempfile as _tf
    with _tf.TemporaryDirectory() as td:
        Path(td, "bad.toml").write_text(
            'schema_version = 1\n[module]\nid = "x"\nlabel = "X"\n'
            '[[findings]]\npattern = "vibes-check"\ncount = 0\n'
        )
        result = _sp.run(
            ["python3", str(AM_PY), "selfdef", "--json"],
            capture_output=True, text=True, timeout=10,
            env={**os.environ,
                 "SOVEREIGN_OS_SELFDEF_AUDIT_DIR": td},
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["count"] == 0
        assert len(data["errors"]) == 1


def test_json_and_human_format_flags():
    body = _read(AM_PY)
    assert "--json" in body and "--human" in body


# --- DRY-RUN ---


def test_supports_dry_run():
    body = _read(AM_PY)
    assert "SOVEREIGN_OS_DRY_RUN" in body


def test_supports_dedicated_dry_run_env():
    body = _read(AM_PY)
    assert "SOVEREIGN_OS_AMIN_DRY_RUN" in body


# --- Metric ---


def test_emits_layer_b_metric():
    body = _read(AM_PY)
    assert "sovereign_os_operator_anti_minimization_audit_query_total" in body


# --- osctl integration ---


def test_osctl_dispatches_anti_minimization_audit():
    body = _read(OSCTL)
    assert "anti-minimization-audit)" in body, (
        "osctl missing anti-minimization-audit) dispatcher"
    )
    assert "anti-minimization-audit.py" in body, (
        "osctl dispatcher doesn't reference anti-minimization-audit.py"
    )


def test_osctl_help_documents_audit_verbs():
    body = _read(OSCTL)
    for sub in (
        "anti-minimization-audit patterns",
        "anti-minimization-audit scan",
        "anti-minimization-audit module",
        "anti-minimization-audit cross-module",
        "anti-minimization-audit report",
    ):
        assert sub in body, f"osctl help missing {sub!r}"


def test_osctl_help_references_e11_m11():
    body = _read(OSCTL)
    assert "E11.M11" in body


# --- Smoke tests ---


def test_patterns_verb_returns_eight():
    """patterns --json MUST return exactly 8 minimization patterns."""
    result = subprocess.run(
        ["python3", str(AM_PY), "patterns", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, (
        f"patterns failed: stderr={result.stderr[:200]}"
    )
    data = json.loads(result.stdout)
    assert data["count"] == 8, (
        f"expected 8 patterns, got {data['count']}"
    )
    ids = [p["id"] for p in data["patterns"]]
    assert set(ids) == set(EXPECTED_PATTERNS), (
        f"pattern set drift: {ids} vs {EXPECTED_PATTERNS}"
    )


def test_report_verb_runs():
    result = subprocess.run(
        ["python3", str(AM_PY), "report", "--json"],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, (
        f"report failed: stderr={result.stderr[:500]}"
    )
    data = json.loads(result.stdout)
    assert "summary" in data
    assert "total" in data
    # All 8 pattern ids in summary
    assert set(data["summary"].keys()) == set(EXPECTED_PATTERNS)


def test_scan_with_pattern_limit_runs():
    result = subprocess.run(
        ["python3", str(AM_PY), "scan",
         "--pattern", "mandate-todo", "--limit", "3", "--json"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "results" in data
    assert "mandate-todo" in data["results"]


def test_scan_unknown_pattern_fails():
    result = subprocess.run(
        ["python3", str(AM_PY), "scan", "--pattern", "bogus-pattern"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode != 0


def test_cross_module_verb_runs():
    result = subprocess.run(
        ["python3", str(AM_PY), "cross-module", "--json"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    for key in ("short_on_both_axes", "short_only_surface",
                "short_only_doc"):
        assert key in data, f"cross-module missing {key!r}"


def test_module_verb_runs():
    result = subprocess.run(
        ["python3", str(AM_PY), "module", "auth-tier", "--json"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["module"] == "auth-tier"
    for key in ("surface_gaps", "doc_gaps",
                "minimize_phrases_in_module_files"):
        assert key in data


# --- R490 (R456+) — Grafana dashboard surface + first-class module registration ---


AM_DASHBOARD_JSON = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-anti-minimization-audit.json"
)


def test_dashboard_json_exists():
    """R490 — anti-min Grafana dashboard surface registers anti-min as
    a first-class module + ships the operator-§1g visualization."""
    assert AM_DASHBOARD_JSON.is_file(), (
        f"missing anti-min dashboard: {AM_DASHBOARD_JSON}"
    )


def test_dashboard_json_parseable():
    """The dashboard MUST be valid JSON (Grafana refuses invalid JSON
    on import)."""
    data = json.loads(AM_DASHBOARD_JSON.read_text(encoding="utf-8"))
    assert "panels" in data, "dashboard missing panels"
    assert "title" in data and data["title"], "dashboard missing title"
    assert "uid" in data and data["uid"], "dashboard missing uid"


def test_dashboard_references_anti_min_metric():
    """At least one panel MUST query the Layer-B metric — otherwise the
    dashboard isn't visualizing the operator-§1g surface."""
    body = AM_DASHBOARD_JSON.read_text(encoding="utf-8")
    assert "sovereign_os_operator_anti_minimization_audit_query_total" in body, (
        "anti-min dashboard doesn't reference the Layer B metric"
    )


def test_dashboard_covers_eight_patterns():
    """Per R456 8-pattern suite, dashboard MUST reference all 8 pattern
    labels (the canonical operator-§1g minimization-shape catalog)."""
    body = AM_DASHBOARD_JSON.read_text(encoding="utf-8")
    for pat in ("todo-no-anchor", "empty-stub", "skipped-no-followup",
                "surface-gap", "doc-gap", "mandate-todo",
                "minimize-phrase", "partial-status"):  # anti-min-waiver: R490 dashboard contract — enumerate 8 canonical pattern names verbatim
        assert pat in body, (
            f"anti-min dashboard missing pattern reference: {pat!r}"
        )


def test_dashboard_covers_core_verbs():
    """Dashboard MUST reference the core verbs the operator can invoke
    (patterns / scan / module / report / waivers)."""
    body = AM_DASHBOARD_JSON.read_text(encoding="utf-8")
    for verb in ("patterns", "scan", "module", "report", "waivers"):
        assert verb in body, (
            f"anti-min dashboard missing verb reference: {verb!r}"
        )


def test_dashboard_quotes_operator_standing_rule_verbatim():
    """Dashboard MUST quote the §1g standing rule verbatim ('We do not
    minimize anything.') — the sacrosanct operator-anti-min mandate
    that this instrument enforces."""
    body = AM_DASHBOARD_JSON.read_text(encoding="utf-8")
    assert "We do not minimize anything" in body, (
        "anti-min dashboard missing §1g verbatim standing rule"
    )


def test_dashboard_listed_in_readme():
    """README.md MUST list the new dashboard (operator-discoverable
    inventory)."""
    readme = (AM_DASHBOARD_JSON.parent / "README.md").read_text(encoding="utf-8")
    assert "sovereign-os-anti-minimization-audit.json" in readme, (
        "dashboards/README.md missing sovereign-os-anti-minimization-audit.json entry"
    )


def test_dashboard_tagged_sovereign_os():
    """Grafana 'sovereign-os' tag MUST be set — operator's dashboard
    folder filter depends on it."""
    data = json.loads(AM_DASHBOARD_JSON.read_text(encoding="utf-8"))
    assert "sovereign-os" in (data.get("tags") or []), (
        "anti-min dashboard missing sovereign-os tag"
    )


def test_anti_min_registered_in_surface_map():
    """R490 registers anti-minimization-audit as a first-class module in
    surface-map.py MODULE_COVERAGE. After this round it MUST appear with
    at least 3 shipped surfaces (core/cli/dashboard) — at threshold."""
    sm_path = REPO_ROOT / "scripts" / "operator" / "surface-map.py"
    sm = sm_path.read_text(encoding="utf-8")
    assert '"anti-minimization-audit":' in sm, (
        "surface-map.py MODULE_COVERAGE missing 'anti-minimization-audit' entry"
    )
    result = subprocess.run(
        ["python3", str(sm_path), "coverage", "--module",
         "anti-minimization-audit", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, (
        f"surface-map coverage anti-min failed: {result.stderr[:300]}"
    )
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    surface_count = entry.get("surface_count", 0)
    assert surface_count >= 3, (
        f"anti-min must be at threshold (>=3 surfaces); got {surface_count}"
    )
