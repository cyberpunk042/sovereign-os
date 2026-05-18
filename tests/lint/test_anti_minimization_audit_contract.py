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
    # Must include canonical operator-named phrases
    for phrase in ('"for now"', '"minimize"', '"placeholder"',
                   '"simplified"'):
        assert phrase in body, (
            f"MINIMIZE_PHRASES missing {phrase!r}"
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
