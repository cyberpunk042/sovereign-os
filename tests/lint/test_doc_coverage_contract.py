"""R454 (E11.M1) — documentation-through-and-through contract lint.

Per operator §1g verbatim:
  "very clear and well defined documentation through and through
   which follow the high standards"

9th substantive feature of §1g/§1h Epic E11 arc:
  R446-R453: 8 prior E11 substantive features
  R454 — E11.M1 doc-coverage scanner
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DC_PY = REPO_ROOT / "scripts" / "operator" / "doc-coverage.py"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"

EXPECTED_KINDS = [
    "readme",
    "sdd",
    "helptext",
    "metric-inventory",
    "mandate-row",
    "man-page",
]


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# --- Structural ---


def test_doc_coverage_script_exists():
    assert DC_PY.is_file(), f"missing {DC_PY}"


def test_doc_coverage_executable():
    assert os.access(DC_PY, os.X_OK), f"{DC_PY} not executable"


def test_python3_shebang():
    body = _read(DC_PY)
    assert body.startswith("#!/usr/bin/env python3")


def test_documents_e11_m1_origin():
    body = _read(DC_PY)
    assert "E11.M1" in body and "§1g" in body


def test_quotes_operator_verbatim_1g_phrase():
    """§1g verbatim documentation phrase MUST appear."""
    body = _read(DC_PY)
    flat = re.sub(r"\s+", " ", body)
    for phrase in (
        "very clear and well defined",
        "documentation through and through",
        "high standards",
    ):
        assert phrase in flat, (
            f"missing operator §1g verbatim phrase {phrase!r}"
        )


# --- 6-kind catalog ---


def test_doc_kinds_catalog_defined():
    body = _read(DC_PY)
    assert "DOC_KINDS" in body, "missing DOC_KINDS catalog"
    for k in EXPECTED_KINDS:
        assert f'"{k}"' in body, f"DOC_KINDS missing {k!r}"


def test_each_kind_has_operator_named_field():
    body = _read(DC_PY)
    n = body.count('"operator_named":')
    assert n >= 6, (
        f"only {n} 'operator_named' fields (expected ≥6, one per kind)"
    )


def test_each_kind_has_path_field():
    body = _read(DC_PY)
    n = body.count('"path":')
    assert n >= 6, f"only {n} 'path' fields (expected ≥6)"


def test_each_kind_has_label_field():
    body = _read(DC_PY)
    n = body.count('"label":')
    assert n >= 6, f"only {n} 'label' fields (expected ≥6)"


# --- Module table ---


def test_modules_catalog_defined():
    body = _read(DC_PY)
    assert "MODULES" in body, "missing MODULES catalog"


def test_modules_include_recent_e11():
    body = _read(DC_PY)
    for m in ("auth-tier", "edge-firewall", "network-edge",
              "master-dashboard", "global-history", "bashrc",
              "surface-map"):
        assert f'"id": "{m}"' in body, (
            f"MODULES missing E11 module {m!r}"
        )


# --- CLI surface (5 verbs) ---


def test_supports_kinds_verb():
    body = _read(DC_PY)
    assert '"kinds"' in body


def test_supports_modules_verb():
    body = _read(DC_PY)
    assert '"modules"' in body


def test_supports_scan_verb():
    body = _read(DC_PY)
    assert '"scan"' in body


def test_supports_coverage_verb():
    body = _read(DC_PY)
    assert '"coverage"' in body


def test_supports_gaps_verb():
    body = _read(DC_PY)
    assert '"gaps"' in body


def test_supports_selfdef_verb():
    """R471: cross-repo selfdef DocManifest discovery
    (SD-R-DOC-MANIFEST-1)."""
    body = _read(DC_PY)
    assert '"selfdef"' in body, "missing selfdef verb"
    assert "SD-R-DOC-MANIFEST-1" in body, (
        "selfdef verb missing cross-repo binding ID"
    )


def test_selfdef_doc_dir_env_overridable():
    """R471: SOVEREIGN_OS_SELFDEF_DOC_DIR env-override."""
    body = _read(DC_PY)
    assert "SOVEREIGN_OS_SELFDEF_DOC_DIR" in body


def test_selfdef_default_dir_etc_selfdef():
    """R471: default path matches /etc/selfdef/doc-manifests."""
    body = _read(DC_PY)
    assert "/etc/selfdef/doc-manifests" in body


def test_selfdef_verb_smoke_with_fixture(tmp_path):
    """End-to-end: synthesize a fixture, run selfdef verb."""
    import json as _json
    import os as _os
    import subprocess as _sp
    d = tmp_path / "manifests"
    d.mkdir()
    (d / "agent-guard.toml").write_text(
        'schema_version = 1\n'
        '[module]\n'
        'id    = "agent-guard"\n'
        'label = "Agent Guard"\n'
        '[[docs]]\n'
        'kind  = "readme"\n'
        'state = "shipped"\n'
        'path  = "README.md"\n'
        '[[docs]]\n'
        'kind   = "sdd"\n'
        'state  = "waived"\n'
        'reason = "no SDD chapter needed for this module"\n',
        encoding="utf-8",
    )
    r = _sp.run(
        ["python3", str(DC_PY), "selfdef", "--json"],
        capture_output=True, text=True, timeout=15,
        env={**_os.environ,
             "SOVEREIGN_OS_SELFDEF_DOC_DIR": str(d)},
    )
    assert r.returncode == 0, r.stderr[:300]
    data = _json.loads(r.stdout)
    assert data["count"] == 1
    assert data["errors"] == []
    entry = data["discovered"][0]
    assert entry["module"] == "agent-guard"
    assert entry["shipped_count"] == 1
    assert entry["waived_count"] == 1


def test_selfdef_verb_rejects_unsupported_schema_version(tmp_path):
    """Defense-in-depth: schema_version != 1 surfaces as error."""
    import json as _json
    import os as _os
    import subprocess as _sp
    d = tmp_path / "manifests"
    d.mkdir()
    (d / "bad.toml").write_text(
        'schema_version = 99\n'
        '[module]\n'
        'id    = "x"\n'
        'label = "X"\n'
        '[[docs]]\n'
        'kind  = "readme"\n'
        'state = "shipped"\n'
        'path  = "README.md"\n',
        encoding="utf-8",
    )
    r = _sp.run(
        ["python3", str(DC_PY), "selfdef", "--json"],
        capture_output=True, text=True, timeout=15,
        env={**_os.environ,
             "SOVEREIGN_OS_SELFDEF_DOC_DIR": str(d)},
    )
    assert r.returncode == 0
    data = _json.loads(r.stdout)
    assert data["count"] == 0
    assert len(data["errors"]) == 1
    assert "schema_version" in data["errors"][0]["error"]


def test_json_and_human_format_flags():
    body = _read(DC_PY)
    assert "--json" in body and "--human" in body


def test_threshold_env_overridable():
    body = _read(DC_PY)
    assert "SOVEREIGN_OS_DOC_THRESHOLD" in body


# --- DRY-RUN ---


def test_supports_dry_run():
    body = _read(DC_PY)
    assert "SOVEREIGN_OS_DRY_RUN" in body


def test_supports_dedicated_dry_run_env():
    body = _read(DC_PY)
    assert "SOVEREIGN_OS_DOC_COVERAGE_DRY_RUN" in body


# --- Metric ---


def test_emits_layer_b_metric():
    body = _read(DC_PY)
    assert "sovereign_os_operator_doc_coverage_query_total" in body


# --- osctl integration ---


def test_osctl_dispatches_doc_coverage():
    body = _read(OSCTL)
    assert "doc-coverage)" in body, (
        "osctl missing doc-coverage) dispatcher"
    )
    assert "doc-coverage.py" in body, (
        "osctl dispatcher doesn't reference doc-coverage.py"
    )


def test_osctl_help_documents_doc_coverage_verbs():
    body = _read(OSCTL)
    for sub in (
        "doc-coverage kinds",
        "doc-coverage modules",
        "doc-coverage scan",
        "doc-coverage coverage",
        "doc-coverage gaps",
    ):
        assert sub in body, f"osctl help missing {sub!r}"


def test_osctl_help_references_e11_m1():
    body = _read(OSCTL)
    assert "E11.M1" in body


# --- Smoke tests ---


def test_kinds_verb_returns_six():
    """kinds --json MUST return exactly 6 operator-named doc surfaces."""
    result = subprocess.run(
        ["python3", str(DC_PY), "kinds", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, (
        f"kinds failed: stderr={result.stderr[:200]}"
    )
    data = json.loads(result.stdout)
    assert data["count"] == 6, (
        f"expected 6 doc kinds, got {data['count']}"
    )
    ids = [k["id"] for k in data["kinds"]]
    assert ids == EXPECTED_KINDS, (
        f"kind order drift: {ids} vs {EXPECTED_KINDS}"
    )


def test_modules_verb_runs():
    result = subprocess.run(
        ["python3", str(DC_PY), "modules", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["count"] >= 7  # at least 7 tracked modules


def test_scan_verb_finds_recent_modules_in_mandate():
    """scan MUST report mandate-row presence for recent E11 modules
    (auth-tier through doc-coverage are all in operator-mandate)."""
    result = subprocess.run(
        ["python3", str(DC_PY), "scan", "--module", "auth-tier",
         "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    auth_tier_scan = data["scan"][0]
    assert "mandate-row" in auth_tier_scan["present_in"], (
        f"auth-tier should be documented in mandate-row; got "
        f"{auth_tier_scan}"
    )
    assert "helptext" in auth_tier_scan["present_in"], (
        f"auth-tier should be documented in osctl helptext; got "
        f"{auth_tier_scan}"
    )


def test_coverage_verb_full_matrix():
    result = subprocess.run(
        ["python3", str(DC_PY), "coverage", "--module",
         "master-dashboard", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    rows = data["coverage"]
    assert len(rows) == 1
    cells = rows[0]["cells"]
    assert len(cells) == 6, f"expected 6 cells, got {len(cells)}"
    states = {c["state"] for c in cells}
    assert states <= {"shipped", "gap"}


def test_gaps_verb_low_threshold_clean():
    """gaps with threshold=0 returns empty."""
    result = subprocess.run(
        ["python3", str(DC_PY), "gaps", "--threshold", "0", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["count"] == 0


def test_gaps_verb_high_threshold_exits_2():
    """gaps with threshold=6 MUST exit 2 (no module has all 6)."""
    result = subprocess.run(
        ["python3", str(DC_PY), "gaps", "--threshold", "6", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 2


def test_scan_unknown_module_fails():
    result = subprocess.run(
        ["python3", str(DC_PY), "scan", "--module", "bogus"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode != 0
