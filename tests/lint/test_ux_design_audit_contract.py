"""R457 (E11.M10) — UX-design-stage audit contract lint.

Per operator §1g verbatim:
  "everything will also need to go through a thorough UX Design stage
   in order to be of quality"

12th substantive feature of §1g/§1h Epic E11 arc (closes E11.M10).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
UX_PY = REPO_ROOT / "scripts" / "operator" / "ux-design-audit.py"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"

EXPECTED_DIMENSIONS = [
    "action-budget",
    "discoverable",
    "recoverable",
    "next-step",
    "operator-named",
    "readable-30s",
]


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# --- Structural ---


def test_ux_audit_script_exists():
    assert UX_PY.is_file(), f"missing {UX_PY}"


def test_ux_audit_executable():
    assert os.access(UX_PY, os.X_OK), f"{UX_PY} not executable"


def test_python3_shebang():
    body = _read(UX_PY)
    assert body.startswith("#!/usr/bin/env python3")


def test_documents_e11_m10_origin():
    body = _read(UX_PY)
    assert "E11.M10" in body and "§1g" in body


def test_quotes_operator_verbatim_ux_phrase():
    """§1g verbatim UX-design-stage phrase MUST appear."""
    body = _read(UX_PY)
    flat = re.sub(r"\s+", " ", body)
    for phrase in (
        "thorough UX Design stage",
        "of quality",
        "reach the goal of the surface in N or fewer actions",
    ):
        assert phrase in flat, (
            f"missing operator §1g verbatim phrase {phrase!r}"
        )


# --- 6-dimension catalog ---


def test_dimensions_catalog_defined():
    body = _read(UX_PY)
    assert "DIMENSIONS" in body, "missing DIMENSIONS catalog"
    for d in EXPECTED_DIMENSIONS:
        assert f'"{d}"' in body, f"DIMENSIONS missing {d!r}"


def test_each_dimension_has_operator_named_field():
    body = _read(UX_PY)
    n = body.count('"operator_named":')
    assert n >= 6, (
        f"only {n} 'operator_named' fields (expected ≥6)"
    )


def test_each_dimension_has_test_field():
    body = _read(UX_PY)
    n = body.count('"test":')
    assert n >= 6, f"only {n} 'test' fields (expected ≥6)"


# --- Auditor functions (one per dimension) ---


def test_auditor_function_per_dimension():
    body = _read(UX_PY)
    for fn in (
        "audit_action_budget",
        "audit_discoverable",
        "audit_recoverable",
        "audit_next_step",
        "audit_operator_named",
        "audit_readable_30s",
    ):
        assert f"def {fn}(" in body, f"missing auditor function {fn}()"


# --- Modules table ---


def test_modules_catalog_defined():
    body = _read(UX_PY)
    assert "MODULES" in body, "missing MODULES catalog"


def test_modules_include_recent_e11():
    body = _read(UX_PY)
    for m in ("auth-tier", "edge-firewall", "network-edge",
              "master-dashboard", "global-history", "bashrc",
              "surface-map", "doc-coverage",
              "anti-minimization-audit"):
        assert f'"{m}"' in body, (
            f"MODULES missing E11 module {m!r}"
        )


def test_each_module_has_verbs_field():
    body = _read(UX_PY)
    n = body.count('"verbs":')
    assert n >= 9, f"only {n} 'verbs' fields (expected ≥9 modules)"


# --- CLI surface (5 verbs) ---


def test_supports_dimensions_verb():
    body = _read(UX_PY)
    assert '"dimensions"' in body


def test_supports_modules_verb():
    body = _read(UX_PY)
    assert '"modules"' in body


def test_supports_audit_verb():
    body = _read(UX_PY)
    assert '"audit"' in body


def test_supports_score_verb():
    body = _read(UX_PY)
    assert '"score"' in body


def test_supports_report_verb():
    body = _read(UX_PY)
    assert '"report"' in body


def test_json_and_human_format_flags():
    body = _read(UX_PY)
    assert "--json" in body and "--human" in body


def test_threshold_env_overridable():
    body = _read(UX_PY)
    assert "SOVEREIGN_OS_UX_THRESHOLD" in body


def test_action_budget_env_overridable():
    body = _read(UX_PY)
    assert "SOVEREIGN_OS_UX_ACTION_BUDGET" in body


# --- DRY-RUN ---


def test_supports_dry_run():
    body = _read(UX_PY)
    assert "SOVEREIGN_OS_DRY_RUN" in body


def test_supports_dedicated_dry_run_env():
    body = _read(UX_PY)
    assert "SOVEREIGN_OS_UX_DRY_RUN" in body


# --- Metric ---


def test_emits_layer_b_metric():
    body = _read(UX_PY)
    assert "sovereign_os_operator_ux_design_audit_query_total" in body


# --- osctl integration ---


def test_osctl_dispatches_ux_design_audit():
    body = _read(OSCTL)
    assert "ux-design-audit)" in body, (
        "osctl missing ux-design-audit) dispatcher"
    )
    assert "ux-design-audit.py" in body, (
        "osctl dispatcher doesn't reference ux-design-audit.py"
    )


def test_osctl_help_documents_ux_design_audit_verbs():
    body = _read(OSCTL)
    for sub in (
        "ux-design-audit dimensions",
        "ux-design-audit modules",
        "ux-design-audit audit",
        "ux-design-audit score",
        "ux-design-audit report",
    ):
        assert sub in body, f"osctl help missing {sub!r}"


def test_osctl_help_references_e11_m10():
    body = _read(OSCTL)
    assert "E11.M10" in body


# --- Smoke tests ---


def test_dimensions_verb_returns_six():
    result = subprocess.run(
        ["python3", str(UX_PY), "dimensions", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["count"] == 6
    ids = [d["id"] for d in data["dimensions"]]
    assert ids == EXPECTED_DIMENSIONS, (
        f"dimension order drift: {ids} vs {EXPECTED_DIMENSIONS}"
    )


def test_modules_verb_runs():
    result = subprocess.run(
        ["python3", str(UX_PY), "modules", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["count"] >= 9


def test_audit_verb_returns_six_results_per_module():
    result = subprocess.run(
        ["python3", str(UX_PY), "audit", "--module", "auth-tier",
         "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    rows = data["audit"]
    assert len(rows) == 1
    assert len(rows[0]["results"]) == 6


def test_score_verb_runs():
    result = subprocess.run(
        ["python3", str(UX_PY), "score", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "scores" in data
    # Sorted lowest first
    scores = [s["score"] for s in data["scores"]]
    assert scores == sorted(scores)


def test_report_low_threshold_clean():
    result = subprocess.run(
        ["python3", str(UX_PY), "report", "--threshold", "0",
         "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["count"] == 0


def test_report_high_threshold_exits_2():
    """All modules below threshold=7 (impossible — 6 dimensions max)."""
    result = subprocess.run(
        ["python3", str(UX_PY), "report", "--threshold", "7",
         "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 2


def test_audit_unknown_module_fails():
    result = subprocess.run(
        ["python3", str(UX_PY), "audit", "--module", "bogus"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode != 0
