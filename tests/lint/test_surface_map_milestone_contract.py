"""R540 (E5++) — surface-map `milestone` verb contract lint.

R539 closed the §1g 8-surface delivery contract across the ENTIRE set
of §1g-named modules — TWELFTH §1g-named module (auditor) reached
ceiling with the auditor API + webapp surfaces. R540 codifies that
historic milestone as a FIRST-CLASS operator-visible observable via
the `surface-map milestone` verb (operator-§1g UX rule: 30-second
readable + the rollup is the regression-detection surface that flips
the moment a new module is added with a FUTURE waiver).

Per operator §1g verbatim (sacrosanct):
  "We do not minimize anything."

Per operator §1g 8-surface delivery contract (R453 anchor, verbatim):
  "everything is not just core, not just cli, not just TUI, not just
   API, not just tool and MCP but also Dashboards and Web Apps and
   Services"

The R540 milestone surface MUST report:
  - total_modules tracked
  - at_structural_ceiling_count (R478 classifier output)
  - full_8_surface_count (modules at full 8/8 §1g delivery)
  - future_carrying_count (regression detector — R539 invariant = 0)
  - at_full_8_surfaces list (operator-discoverable: which §1g modules)
  - at_ceiling_below_8_surfaces list (structural-ceiling but <8/8:
    bashrc, auth-tier, master-dashboard — these have STRUCTURAL
    waivers, not FUTURE work)
  - future_carrying_modules list (regression list — empty post-R539)
  - all_at_structural_ceiling boolean
  - all_g1g_named_at_full_8 boolean
  - zero_future_waivers boolean
  - historic_anchor (R539 anchor text)
  - standing_rule (R453 verbatim quote)
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SM_PY = REPO_ROOT / "scripts" / "operator" / "surface-map.py"

# The 12 §1g-named modules that closed the §1g 8-surface delivery
# contract — operator-named in shipped-order (each line is a round
# anchor):
EXPECTED_G1G_FULL_8 = {
    "edge-firewall",         # R506
    "network-edge",          # R509
    "global-history",        # R512
    "trinity",               # R515
    "router",                # R518
    "compliance",            # R521
    "anti-minimization-audit",  # R524
    "doc-coverage",          # R527
    "ux-design-audit",       # R530
    "surface-map",           # R533
    "weaver",                # R536
    "auditor",               # R539 — TWELFTH, closes the ladder
}

# Structural-ceiling-but-below-8 modules (carry "not applicable"
# structural waivers, NOT FUTURE work). M060 cross-repo mirror
# modules join the original 3: per "Respect the projects", each
# mirror is a READ-ONLY cross-repo consumer where TUI for the
# underlying IPS state lives in selfdef (not sovereign-os) and
# the webapp surface IS the dashboard (no separate Grafana panel).
EXPECTED_STRUCTURAL_BELOW_8 = {
    "bashrc",            # 2/8 — config installer, 6 structural waivers
    "auth-tier",         # 7/8 — tui n/a (config surface)
    "master-dashboard",  # 7/8 — dashboard self-referential
    "profile-mirror",    # 6/8 — tui n/a (selfdef-side) + dashboard self-referential (webapp IS the dashboard)
    "grants-mirror",     # 6/8 — same M060 cross-repo mirror pattern
    "capability-mirror", # 6/8 — same M060 cross-repo mirror pattern
    "sandbox-mirror",    # 6/8 — same M060 cross-repo mirror pattern
    "audit-mirror",      # 6/8 — same M060 cross-repo mirror pattern
    "quarantine-mirror", # 6/8 — same M060 cross-repo mirror pattern
    "trust-mirror",      # 6/8 — same M060 cross-repo mirror pattern
    "lm-status-operability",  # 4/8 — cockpit panel over the shared model-health core (cli/tui/dashboard/mcp n/a)
    "lm-orchestration",       # 4/8 — cockpit panel over model-health + runtime-modes cores (cli/tui/dashboard/mcp n/a)
    "models-catalog",         # 4/8 — cockpit panel over the shared load_catalog core (cli/tui/dashboard/mcp n/a)
    "cpu-features",           # 4/8 — cockpit panel over the shared avx512-advisor (cli/tui/dashboard/mcp n/a)
}


# ---------------------------------------------------------------- static


def test_milestone_verb_registered():
    body = SM_PY.read_text(encoding="utf-8")
    assert "milestone" in body
    assert "cmd_milestone" in body, (
        "R540: milestone verb must register a cmd_milestone handler"
    )
    assert "milestone_rollup" in body, (
        "R540: must expose milestone_rollup() helper for daemon reuse"
    )


def test_milestone_help_advertises_r540():
    """`--help` MUST surface the milestone verb so operators can
    discover it (operator-§1g UX rule: discoverable)."""
    result = subprocess.run(
        ["python3", str(SM_PY), "--help"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0
    assert "milestone" in result.stdout, (
        "top-level --help must advertise the milestone verb"
    )


def test_milestone_runs_human():
    result = subprocess.run(
        ["python3", str(SM_PY), "milestone"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr[:300]
    out = result.stdout
    # Human format MUST surface the rollup invariants and the §1g rule.
    assert "8-surface delivery contract" in out
    assert "total modules tracked" in out
    assert "at structural ceiling" in out
    assert "FUTURE waivers" in out
    assert "Dashboards and Web Apps and Services" in out, (
        "human output must carry the R453 standing rule verbatim"
    )
    assert "R539" in out


def test_milestone_runs_json_shape():
    """The JSON shape is the contract for the TUI/MCP/API/dashboard
    consumers — every field below is load-bearing."""
    result = subprocess.run(
        ["python3", str(SM_PY), "milestone", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr[:300]
    data = json.loads(result.stdout)
    # Required top-level keys.
    required_keys = {
        "module", "verb", "spec_ref",
        "total_modules", "at_structural_ceiling_count",
        "full_8_surface_count", "future_carrying_count",
        "at_full_8_surfaces", "at_ceiling_below_8_surfaces",
        "future_carrying_modules",
        "all_at_structural_ceiling",
        "all_g1g_named_at_full_8",
        "zero_future_waivers",
        "historic_anchor", "standing_rule",
    }
    missing = required_keys - set(data.keys())
    assert not missing, f"R540 JSON missing keys: {sorted(missing)}"
    assert data["module"] == "surface-map"
    assert data["verb"] == "milestone"


def test_milestone_records_r539_historic_state():
    """R539 invariant: ALL §1g modules at structural ceiling, ZERO
    FUTURE waivers across the entire codebase. The milestone verb
    MUST report these booleans True."""
    result = subprocess.run(
        ["python3", str(SM_PY), "milestone", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    data = json.loads(result.stdout)
    assert data["all_at_structural_ceiling"] is True, (
        f"R539 historic invariant: every module must be at structural "
        f"ceiling; got {data}"
    )
    assert data["zero_future_waivers"] is True, (
        f"R539 historic invariant: ZERO FUTURE waivers across the "
        f"codebase; got future_carrying_modules="
        f"{data['future_carrying_modules']}"
    )
    assert data["future_carrying_count"] == 0
    assert data["future_carrying_modules"] == []


def test_milestone_g1g_full_8_set_matches_expected():
    """The 12 §1g-named modules at full 8/8 MUST be the operator-
    named set in EXPECTED_G1G_FULL_8 — each one closed its tier-3
    arc in an explicit round (R506-R539). A new module here means
    the test catalog needs an explicit update + a fresh closure
    round anchor."""
    result = subprocess.run(
        ["python3", str(SM_PY), "milestone", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    data = json.loads(result.stdout)
    full_8 = set(data["at_full_8_surfaces"])
    assert full_8 == EXPECTED_G1G_FULL_8, (
        f"R540: full 8/8 set diverged from R539 closure catalog. "
        f"Expected {sorted(EXPECTED_G1G_FULL_8)}, got {sorted(full_8)}. "
        f"Missing: {sorted(EXPECTED_G1G_FULL_8 - full_8)}, "
        f"Extra: {sorted(full_8 - EXPECTED_G1G_FULL_8)}"
    )
    assert data["full_8_surface_count"] == 12
    assert data["all_g1g_named_at_full_8"] is True


def test_milestone_structural_below_8_set_matches_expected():
    """The 3 structural-ceiling-but-below-8 modules are the
    operator-named modules that carry structural ("not applicable —
    ...") waivers — bashrc (config installer, 2/8), auth-tier (config
    surface, 7/8 — tui n/a), master-dashboard (self-referential
    dashboard, 7/8). These are NOT minimization candidates; they're
    operator-fully-described at their ceiling."""
    result = subprocess.run(
        ["python3", str(SM_PY), "milestone", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    data = json.loads(result.stdout)
    structural = {
        rec["module"] for rec in data["at_ceiling_below_8_surfaces"]
    }
    assert structural == EXPECTED_STRUCTURAL_BELOW_8, (
        f"R540: structural-below-8 set diverged. Expected "
        f"{sorted(EXPECTED_STRUCTURAL_BELOW_8)}, got {sorted(structural)}"
    )
    # Each below-8 record MUST carry surface_count + structural_waiver_count.
    for rec in data["at_ceiling_below_8_surfaces"]:
        assert "surface_count" in rec
        assert "structural_waiver_count" in rec
        assert rec["surface_count"] < 8
        assert rec["structural_waiver_count"] >= 1


def test_milestone_historic_anchor_quotes_r539_and_g1g_lineage():
    """The historic_anchor MUST cite R539 verbatim AND name every
    single §1g-named round in the closure lineage (R506-R539). This
    is operator-§1g visibility: the milestone surface IS the place
    where the lineage gets named."""
    result = subprocess.run(
        ["python3", str(SM_PY), "milestone", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    data = json.loads(result.stdout)
    anchor = data["historic_anchor"]
    assert "R539" in anchor
    assert "TWELFTH" in anchor or "12" in anchor or "twelve" in anchor.lower()
    # Every closure round MUST be named in the anchor (regression
    # protection — if a new closure round is added, the anchor must
    # be expanded explicitly, not silently let-drift).
    for round_anchor in (
        "R506", "R509", "R512", "R515", "R518",
        "R521", "R524", "R527", "R530", "R533",
        "R536", "R539",
    ):
        assert round_anchor in anchor, (
            f"historic_anchor missing closure-round citation: "
            f"{round_anchor}"
        )


def test_milestone_standing_rule_is_r453_verbatim():
    """The R453 standing rule is sacrosanct — the milestone surface
    MUST quote it verbatim. Mirrors the SDD/CLI/dashboard pattern."""
    result = subprocess.run(
        ["python3", str(SM_PY), "milestone", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    data = json.loads(result.stdout)
    rule = data["standing_rule"]
    expected = (
        "everything is not just core, not just cli, not just TUI, "
        "not just API, not just tool and MCP but also Dashboards and "
        "Web Apps and Services."
    )
    assert rule == expected, (
        f"R540: standing_rule must quote R453 verbatim; got {rule!r}"
    )


def test_milestone_spec_ref_cites_r453_and_r539():
    result = subprocess.run(
        ["python3", str(SM_PY), "milestone", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    data = json.loads(result.stdout)
    spec = data["spec_ref"]
    assert "R453" in spec, f"spec_ref must cite R453; got {spec!r}"
    assert "R539" in spec, f"spec_ref must cite R539; got {spec!r}"
    assert "§1g" in spec or "1g" in spec, (
        f"spec_ref must cite operator §1g; got {spec!r}"
    )


def test_milestone_rollup_helper_is_importable():
    """The milestone_rollup() helper MUST be directly callable (no
    argparse) — daemon surfaces (API/TUI/dashboard) need to reuse
    the rollup without spawning subprocess. Mirrors the
    coverage_for() / load_selfdef_surface_manifests() pattern."""
    spec = importlib.util.spec_from_file_location("_r540_sm", SM_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "milestone_rollup"), (
        "R540 daemon-reuse: milestone_rollup() must be importable"
    )
    payload = mod.milestone_rollup()
    assert isinstance(payload, dict)
    assert payload["verb"] == "milestone"
    assert payload["all_at_structural_ceiling"] is True
    assert payload["zero_future_waivers"] is True


def test_milestone_count_self_consistency():
    """Cross-field invariants — operator-§1g visibility regression
    bait: if any of these go out of sync, an upstream invariant
    silently slipped."""
    result = subprocess.run(
        ["python3", str(SM_PY), "milestone", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    data = json.loads(result.stdout)
    assert data["total_modules"] == 26
    assert (
        data["at_structural_ceiling_count"]
        == len(data["at_full_8_surfaces"])
        + len(data["at_ceiling_below_8_surfaces"])
        + 0  # future_carrying are NOT at structural ceiling
    ), f"rollup invariant violated: {data}"
    assert data["future_carrying_count"] == len(
        data["future_carrying_modules"]
    )
    assert data["full_8_surface_count"] == len(
        data["at_full_8_surfaces"]
    )
