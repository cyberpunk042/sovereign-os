"""R453 (E11.M3) — multi-surface delivery contract lint.

Per operator §1g verbatim:
  "Everything is not just core, not just cli, not just TUI, not just
   API, not just tool and MCP but also Dashboards and Web Apps and
   Services"

8th substantive feature of §1g/§1h Epic E11 arc:
  R446 — E11.M4 Nemotron 3 (partial)
  R447 — E11.M6 bashrc opt-in
  R448 — E11.M5 global-history
  R449 — E11.M8 network-edge
  R450 — E11.M7 auth-tier ladder
  R451 — E11.M9 edge-firewall alternative
  R452 — E11.M2 master-dashboard aggregator
  R453 — E11.M3 multi-surface delivery contract
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SM_PY = REPO_ROOT / "scripts" / "operator" / "surface-map.py"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"

# §1g verbatim 8-surface taxonomy (ORDER preserved)
EXPECTED_SURFACES = [
    "core",
    "cli",
    "tui",
    "api",
    "mcp",
    "dashboard",
    "webapp",
    "service",
]


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# --- Structural ---


def test_surface_map_script_exists():
    assert SM_PY.is_file(), f"missing {SM_PY}"


def test_surface_map_executable():
    assert os.access(SM_PY, os.X_OK), f"{SM_PY} not executable"


def test_python3_shebang():
    body = _read(SM_PY)
    assert body.startswith("#!/usr/bin/env python3")


def test_documents_e11_m3_origin():
    body = _read(SM_PY)
    assert "E11.M3" in body and "§1g" in body


def test_quotes_operator_verbatim_1g_phrase():
    """§1g verbatim 8-surface taxonomy phrases MUST appear."""
    body = _read(SM_PY)
    flat = re.sub(r"\s+", " ", body)
    for phrase in (
        "not just core",
        "not just cli",
        "not just TUI",
        "not just API",
        "not just tool and MCP",
        "Dashboards and Web Apps and Services",
    ):
        assert phrase in flat, (
            f"missing operator §1g verbatim phrase {phrase!r}"
        )


# --- 8-surface taxonomy ---


def test_surfaces_catalog_defined():
    body = _read(SM_PY)
    assert "SURFACES" in body, "missing SURFACES catalog"
    for s in EXPECTED_SURFACES:
        assert f'"{s}"' in body, f"SURFACES missing {s!r}"


def test_each_surface_has_operator_named_field():
    body = _read(SM_PY)
    n = body.count('"operator_named":')
    assert n >= 8, (
        f"only {n} 'operator_named' fields (expected ≥8, one per surface)"
    )


def test_each_surface_has_position_field():
    body = _read(SM_PY)
    # §1g_position field marks the order in the operator §1g sentence
    n = body.count("§1g_position")
    assert n >= 9, (  # 1 in docstring + 8 in entries
        f"only {n} '§1g_position' references (expected ≥9)"
    )


# --- Module coverage table ---


def test_module_coverage_table_defined():
    body = _read(SM_PY)
    assert "MODULE_COVERAGE" in body, "missing MODULE_COVERAGE table"


def test_coverage_includes_recent_e11_modules():
    """Recent E11.Mx modules MUST be tracked."""
    body = _read(SM_PY)
    for m in ("auth-tier", "edge-firewall", "network-edge",
              "master-dashboard", "global-history", "bashrc"):
        assert f'"{m}":' in body, (
            f"MODULE_COVERAGE missing E11 module {m!r}"
        )


def test_each_module_has_shipped_in_field():
    body = _read(SM_PY)
    n = body.count('"shipped_in":')
    assert n >= 8, f"only {n} 'shipped_in' fields (expected ≥8 modules)"


def test_each_module_has_waivers_field():
    body = _read(SM_PY)
    n = body.count('"waivers":')
    assert n >= 8, f"only {n} 'waivers' fields (expected ≥8 modules)"


# --- CLI surface (5 verbs) ---


def test_supports_surfaces_verb():
    body = _read(SM_PY)
    assert '"surfaces"' in body


def test_supports_modules_verb():
    body = _read(SM_PY)
    assert '"modules"' in body


def test_supports_coverage_verb():
    body = _read(SM_PY)
    assert '"coverage"' in body


def test_supports_gaps_verb():
    body = _read(SM_PY)
    assert '"gaps"' in body


def test_supports_waivers_verb():
    body = _read(SM_PY)
    assert '"waivers"' in body


def test_supports_selfdef_verb():
    """R462: cross-repo selfdef SurfaceManifest discovery verb."""
    body = _read(SM_PY)
    assert '"selfdef"' in body
    assert "SD-R-MULTI-SURFACE-AUDIT-1" in body


def test_selfdef_surface_dir_env_overridable():
    body = _read(SM_PY)
    assert "SOVEREIGN_OS_SELFDEF_SURFACE_DIR" in body


def test_selfdef_default_surface_dir():
    body = _read(SM_PY)
    assert "/etc/selfdef/surfaces" in body


def test_selfdef_verb_runs_with_fixtures():
    """R462: end-to-end smoke test consuming a real selfdef manifest."""
    import subprocess as _sp
    import tempfile as _tf
    with _tf.TemporaryDirectory() as td:
        Path(td, "agent-guard.toml").write_text(
            'schema_version = 1\n\n'
            '[module]\nid = "agent-guard"\nlabel = "Agent Guard"\n\n'
            '[[surfaces]]\nid = "core"\nstate = "shipped"\n\n'
            '[[surfaces]]\nid = "tui"\nstate = "waived"\n'
            'reason = "no interactive surface"\n'
        )
        result = _sp.run(
            ["python3", str(SM_PY), "selfdef", "--json"],
            capture_output=True, text=True, timeout=10,
            env={**os.environ,
                 "SOVEREIGN_OS_SELFDEF_SURFACE_DIR": td},
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["count"] == 1
        m = data["discovered"][0]
        assert m["module"] == "agent-guard"
        assert m["shipped_count"] == 1
        assert m["waived_count"] == 1
        assert m["source_repo"] == "selfdef"


def test_selfdef_verb_rejects_bad_schema():
    """R462: unsupported schema_version surfaces as an error entry."""
    import subprocess as _sp
    import tempfile as _tf
    with _tf.TemporaryDirectory() as td:
        Path(td, "bad.toml").write_text(
            'schema_version = 99\n[module]\nid = "x"\nlabel = "X"\n'
            '[[surfaces]]\nid = "core"\nstate = "shipped"\n'
        )
        result = _sp.run(
            ["python3", str(SM_PY), "selfdef", "--json"],
            capture_output=True, text=True, timeout=10,
            env={**os.environ,
                 "SOVEREIGN_OS_SELFDEF_SURFACE_DIR": td},
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["count"] == 0
        assert len(data["errors"]) == 1


def test_json_and_human_format_flags():
    body = _read(SM_PY)
    assert "--json" in body and "--human" in body


def test_threshold_env_overridable():
    body = _read(SM_PY)
    assert "SOVEREIGN_OS_SURFACE_THRESHOLD" in body


# --- DRY-RUN + env overlay ---


def test_supports_dry_run():
    body = _read(SM_PY)
    assert "SOVEREIGN_OS_DRY_RUN" in body


def test_supports_dedicated_dry_run_env():
    body = _read(SM_PY)
    assert "SOVEREIGN_OS_SURFACE_MAP_DRY_RUN" in body


# --- Metric ---


def test_emits_layer_b_metric():
    body = _read(SM_PY)
    assert "sovereign_os_operator_surface_map_query_total" in body


# --- osctl integration ---


def test_osctl_dispatches_surface_map():
    body = _read(OSCTL)
    assert "surface-map)" in body, (
        "osctl missing surface-map) dispatcher"
    )
    assert "surface-map.py" in body, (
        "osctl dispatcher doesn't reference surface-map.py"
    )


def test_osctl_help_documents_surface_map_verbs():
    body = _read(OSCTL)
    for sub in (
        "surface-map surfaces",
        "surface-map modules",
        "surface-map coverage",
        "surface-map gaps",
        "surface-map waivers",
    ):
        assert sub in body, f"osctl help missing {sub!r}"


def test_osctl_help_references_e11_m3():
    body = _read(OSCTL)
    assert "E11.M3" in body


# --- Smoke tests ---


def test_surfaces_verb_returns_eight():
    """surfaces --json MUST return exactly 8 operator-named surfaces
    in §1g verbatim order."""
    result = subprocess.run(
        ["python3", str(SM_PY), "surfaces", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, (
        f"surfaces failed: stderr={result.stderr[:200]}"
    )
    data = json.loads(result.stdout)
    assert data["count"] == 8, f"expected 8 surfaces, got {data['count']}"
    ids = [s["id"] for s in data["surfaces"]]
    assert ids == EXPECTED_SURFACES, (
        f"surface order drift: {ids} vs {EXPECTED_SURFACES}"
    )


def test_modules_verb_runs():
    result = subprocess.run(
        ["python3", str(SM_PY), "modules", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["count"] >= 6


def test_coverage_verb_full_matrix():
    """coverage on a known module MUST return an 8-row matrix."""
    result = subprocess.run(
        ["python3", str(SM_PY), "coverage", "--module", "auth-tier",
         "--json"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    rows = data["coverage"]
    assert len(rows) == 1
    matrix = rows[0]["matrix"]
    assert len(matrix) == 8, f"expected 8-row matrix, got {len(matrix)}"
    states = {e["state"] for e in matrix}
    assert states <= {"shipped", "waived", "gap"}, (
        f"unexpected states: {states}"
    )


def test_gaps_verb_with_threshold():
    result = subprocess.run(
        ["python3", str(SM_PY), "gaps", "--threshold", "1", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    # threshold=1 means no gaps (every tracked module ships ≥1)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["count"] == 0


def test_gaps_verb_exits_nonzero_when_below():
    """gaps with high threshold MUST exit 2 (operator-discoverable
    failure mode)."""
    result = subprocess.run(
        ["python3", str(SM_PY), "gaps", "--threshold", "8", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 2


def test_coverage_unknown_module_fails():
    result = subprocess.run(
        ["python3", str(SM_PY), "coverage", "--module", "bogus"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode != 0


def test_waivers_verb_runs():
    result = subprocess.run(
        ["python3", str(SM_PY), "waivers", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "waivers" in data
    assert data["count"] >= 10  # many waivers across modules


# --- R478 structural-ceiling classification ---


def test_waiver_classification_helper_present():
    """R478: surface-map MUST expose a waiver-rationale classifier
    that distinguishes 'structural' ceiling waivers ('not applicable
    — ...') from 'future' roadmap waivers ('FUTURE — ...'). The
    classifier is the basis for the structural-ceiling exclusion
    from the gaps verb (anti-min precision pass)."""
    body = SM_PY.read_text(encoding="utf-8")
    assert "_classify_waiver" in body, (
        "R478: missing _classify_waiver helper"
    )
    # Must distinguish the two operator-canonical rationale prefixes.
    assert '"structural"' in body or "'structural'" in body
    assert '"future"' in body or "'future'" in body


def test_coverage_reports_at_structural_ceiling_flag():
    """R478: coverage_for MUST surface an `at_structural_ceiling`
    boolean = True iff every unshipped surface carries a
    'not applicable'-prefixed waiver (NO FUTURE work tracked)."""
    result = subprocess.run(
        ["python3", str(SM_PY), "coverage", "--module", "bashrc", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    # `coverage` verb returns {"coverage": [<record>], "count": 1}.
    rec = data["coverage"][0] if "coverage" in data else data
    # bashrc ships [core, cli]; the other 6 are all "not applicable".
    assert rec.get("at_structural_ceiling") is True, (
        f"R478: bashrc must be at_structural_ceiling=True, got {rec!r}"
    )
    # The R478 fixture rotates as §1g modules drain their FUTURE
    # waivers. Prior fixtures (and their close-out rounds):
    #   - auth-tier        — reached ceiling in R503
    #   - edge-firewall    — reached ceiling in R506 (first §1g-named
    #                        module to hit a fully-shipped 8-surface
    #                        state with ZERO remaining waivers)
    #   - network-edge     — reached ceiling in R509 (second)
    #   - global-history   — reached ceiling in R512 (third — closed
    #                        the api/mcp/webapp trio across R510-R512)
    #   - trinity          — reached ceiling in R515 (fourth — closed
    #                        the tui/mcp/webapp trio across R513-R515)
    #   - router           — reached ceiling in R518 (fifth — closed
    #                        the tui/mcp/api/webapp quartet across
    #                        R516-R518; the tier-3 expansion arc
    #                        following the same shape as trinity's
    #                        R513-R515 triple, with the extra api
    #                        surface in the same R518 commit that
    #                        added webapp).
    #   - compliance       — reached ceiling in R521 (sixth — closed
    #                        the tui/mcp/api/webapp quartet across
    #                        R519-R521; R521 also REPLACED the prior
    #                        `service: not applicable` waiver with a
    #                        real systemd-managed read-only daemon,
    #                        same pattern R510/R515/R518 used for
    #                        global-history, trinity, and router).
    # The fixture now rotates to `anti-minimization-audit`, which
    # carries 4 FUTURE waivers (tui/api/mcp/webapp) and is the next
    # §1g instrument on the tier-3 expansion arc — same 4-surface
    # shape as the surface-map / doc-coverage / ux-design-audit
    # siblings (all 4 R458 instruments currently sit at the same
    # core+cli+dashboard tier waiting for the same tier-3 arc).
    result2 = subprocess.run(
        ["python3", str(SM_PY), "coverage", "--module",
         "anti-minimization-audit", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    data2 = json.loads(result2.stdout)
    rec2 = data2["coverage"][0] if "coverage" in data2 else data2
    assert rec2.get("at_structural_ceiling") is False, (
        f"R478: anti-minimization-audit must be "
        f"at_structural_ceiling=False, got {rec2!r}"
    )
    assert rec2.get("future_waiver_count", 0) >= 1, (
        f"R478 fixture: anti-minimization-audit must carry FUTURE "
        f"waivers; got {rec2!r}"
    )


def test_gaps_excludes_structural_ceiling_modules():
    """R478: `gaps` MUST exclude modules at structural ceiling — they
    are not minimization candidates, they are operator-fully-described
    at their ceiling. bashrc (2 shipped, 6 NA, 0 FUTURE) is the
    canonical structural-ceiling case.

    R484 update: as of R484, ALL FUTURE-roadmap modules have been
    drained out of below_threshold (R481/R482/R483/R484 closed the 4
    remaining shortfalls). The principle (gaps excludes ceiling
    modules) is still validated by the bashrc-absent assertion; the
    inverse FUTURE-stays-in check is necessarily vacuous and tested
    via `test_gaps_surfaces_structural_ceiling_modules_separately`
    which assets the `at_structural_ceiling` list mechanism keeps
    working regardless of below_threshold population.
    """
    result = subprocess.run(
        ["python3", str(SM_PY), "gaps", "--threshold", "3", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    data = json.loads(result.stdout)
    below_modules = {e["module"] for e in data.get("below_threshold", [])}
    assert "bashrc" not in below_modules, (
        "R478: bashrc is at structural ceiling — must be excluded "
        f"from gaps output, got {below_modules}"
    )


def test_gaps_surfaces_structural_ceiling_modules_separately():
    """R478: `gaps` JSON output MUST include an `at_structural_ceiling`
    list so the operator can SEE the modules that were excluded
    (transparency — not minimization-by-silence)."""
    result = subprocess.run(
        ["python3", str(SM_PY), "gaps", "--threshold", "3", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    data = json.loads(result.stdout)
    assert "at_structural_ceiling" in data, (
        "R478: gaps output must include at_structural_ceiling list "
        "(operator visibility)"
    )
    ceiling_modules = {e["module"] for e in data["at_structural_ceiling"]}
    assert "bashrc" in ceiling_modules


# --- R493 (R453+) — Grafana dashboard surface + first-class self-reference module registration ---


SM_DASHBOARD_JSON = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-surface-map.json"
)


def test_dashboard_json_exists():
    """R493 — surface-map Grafana dashboard surface registers surface-
    map as a first-class module IN ITS OWN MODULE_COVERAGE — closing
    the 4-instrument meta-coverage loop (R489 compliance + R490 anti-min
    + R491 doc-coverage + R492 ux-design-audit + R493 surface-map)."""
    assert SM_DASHBOARD_JSON.is_file(), (
        f"missing surface-map dashboard: {SM_DASHBOARD_JSON}"
    )


def test_dashboard_json_parseable():
    data = json.loads(SM_DASHBOARD_JSON.read_text(encoding="utf-8"))
    assert "panels" in data
    assert "title" in data and data["title"]
    assert "uid" in data and data["uid"]


def test_dashboard_references_surface_map_metric():
    body = SM_DASHBOARD_JSON.read_text(encoding="utf-8")
    assert "sovereign_os_operator_surface_map_query_total" in body, (
        "surface-map dashboard doesn't reference the Layer B metric"
    )


def test_dashboard_covers_eight_surfaces():
    """Per R453 8-surface suite, dashboard MUST reference all 8 §1g
    delivery surface labels verbatim."""
    body = SM_DASHBOARD_JSON.read_text(encoding="utf-8")
    for sfc in ("core", "cli", "tui", "api", "mcp",
                "dashboard", "webapp", "service"):
        assert sfc in body, (
            f"surface-map dashboard missing surface reference: {sfc!r}"
        )


def test_dashboard_covers_core_verbs():
    body = SM_DASHBOARD_JSON.read_text(encoding="utf-8")
    for verb in ("surfaces", "modules", "coverage", "gaps", "waivers"):
        assert verb in body, (
            f"surface-map dashboard missing verb reference: {verb!r}"
        )


def test_dashboard_quotes_operator_standing_rule_verbatim():
    body = SM_DASHBOARD_JSON.read_text(encoding="utf-8")
    assert "We do not minimize anything" in body, (
        "surface-map dashboard missing §1g verbatim standing rule"
    )


def test_dashboard_quotes_operator_eight_surface_rule():
    """The 8-surface §1g rationale MUST appear verbatim — this is the
    operator-named contract surface-map enforces."""
    body = SM_DASHBOARD_JSON.read_text(encoding="utf-8")
    assert "not just core" in body, (
        "surface-map dashboard missing 8-surface §1g rationale"
    )


def test_dashboard_listed_in_readme():
    readme = (SM_DASHBOARD_JSON.parent / "README.md").read_text(encoding="utf-8")
    assert "sovereign-os-surface-map.json" in readme, (
        "dashboards/README.md missing sovereign-os-surface-map.json entry"
    )


def test_dashboard_tagged_sovereign_os():
    data = json.loads(SM_DASHBOARD_JSON.read_text(encoding="utf-8"))
    assert "sovereign-os" in (data.get("tags") or []), (
        "surface-map dashboard missing sovereign-os tag"
    )


def test_surface_map_self_registered_in_module_coverage():
    """R493 registers surface-map in its own MODULE_COVERAGE at >=3
    surfaces. The inspector inspects the inspector — meta-coverage
    closed."""
    sm = SM_PY.read_text(encoding="utf-8")
    assert '"surface-map":' in sm, (
        "surface-map.py MODULE_COVERAGE missing 'surface-map' self-entry"
    )
    result = subprocess.run(
        ["python3", str(SM_PY), "coverage", "--module",
         "surface-map", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, (
        f"surface-map coverage surface-map failed: {result.stderr[:300]}"
    )
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    surface_count = entry.get("surface_count", 0)
    assert surface_count >= 3, (
        f"surface-map must be at threshold (>=3 surfaces); got {surface_count}"
    )
