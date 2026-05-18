"""R450 (E11.M7) — auth-tier verb contract lint.

Per operator §1g verbatim:
  "a mode of access from no auth at all by default to basic auth to
   advanced auth to social auth to enterprise auth and network level
   access and etc."

5th substantive feature of §1g/§1h Epic E11 arc:
  R446 — E11.M4 Nemotron 3 (partial)
  R447 — E11.M6 bashrc opt-in
  R448 — E11.M5 global-history
  R449 — E11.M8 network-edge
  R450 — E11.M7 auth-tier ladder
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AT_PY = REPO_ROOT / "scripts" / "operator" / "auth-tier.py"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"

# §1g operator-verbatim ladder (LOW → HIGH)
EXPECTED_TIERS = [
    "no-auth",
    "basic",
    "advanced",
    "social",
    "enterprise",
    "network-level",
]


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# --- Structural ---


def test_auth_tier_script_exists():
    assert AT_PY.is_file(), f"missing {AT_PY}"


def test_auth_tier_executable():
    assert os.access(AT_PY, os.X_OK), f"{AT_PY} not executable"


def test_python3_shebang():
    body = _read(AT_PY)
    assert body.startswith("#!/usr/bin/env python3")


def test_documents_e11_m7_origin():
    body = _read(AT_PY)
    assert "E11.M7" in body and "§1g" in body


def test_quotes_operator_verbatim_ladder():
    """§1g verbatim ladder phrases MUST appear."""
    body = _read(AT_PY)
    # Per-tier operator-named labels (§1g verbatim)
    for phrase in [
        "no auth at all by default",
        "basic auth",
        "advanced auth",
        "social auth",
        "enterprise auth",
        "network level access",
    ]:
        assert phrase in body, (
            f"missing operator §1g verbatim phrase {phrase!r}"
        )


# --- 6-tier ladder (operator-named, verbatim ordering) ---


def test_six_tiers_defined():
    body = _read(AT_PY)
    assert "AUTH_TIERS" in body, "missing AUTH_TIERS catalog constant"
    for t in EXPECTED_TIERS:
        # Each tier name appears at least once as a dict key/value
        assert f'"{t}"' in body, f"AUTH_TIERS missing tier {t!r}"


def test_tier_levels_strictly_monotonic():
    """The 6 tiers MUST have levels 0..5 in operator-named ORDER.
    Drift = ladder reordered + matrix nonsensical."""
    body = _read(AT_PY)
    # Per the source code, the catalog is a list of dicts with
    # "level" field; check that the literal "level": N values appear
    # in order
    for n in range(6):
        assert f'"level": {n}' in body, (
            f"AUTH_TIERS missing level={n}"
        )


def test_each_tier_has_warning_field():
    """Operator-discovery: each tier MUST have a `warning` field
    naming a typical failure mode at that tier."""
    body = _read(AT_PY)
    warning_count = body.count('"warning":')
    assert warning_count >= 6, (
        f"only {warning_count} 'warning' fields (expected ≥6, one per tier)"
    )


def test_each_tier_has_typical_use_field():
    body = _read(AT_PY)
    use_count = body.count('"typical_use":')
    assert use_count >= 6, (
        f"only {use_count} 'typical_use' fields (expected ≥6)"
    )


def test_each_tier_has_operator_named_field():
    body = _read(AT_PY)
    on_count = body.count('"operator_named":')
    assert on_count >= 6, (
        f"only {on_count} 'operator_named' fields (expected ≥6)"
    )


# --- Dashboard registry ---


def test_default_registry_exists():
    body = _read(AT_PY)
    assert "DEFAULT_REGISTRY" in body, "missing DEFAULT_REGISTRY"


def test_registry_includes_trinity_tiers():
    """Operator-named Trinity tiers (pulse/logic-engine/oracle-core)
    MUST be in the default registry."""
    body = _read(AT_PY)
    for name in ("trinity-pulse", "trinity-logic-engine",
                 "trinity-oracle-core"):
        assert name in body, (
            f"DEFAULT_REGISTRY missing operator-named Trinity dashboard "
            f"{name!r}"
        )


def test_registry_includes_router():
    body = _read(AT_PY)
    assert '"router"' in body or "'router'" in body, (
        "DEFAULT_REGISTRY missing router dashboard"
    )


def test_registry_each_entry_has_rationale():
    """Every default-registry entry MUST have rationale (operator-
    discoverable: why this tier?)."""
    body = _read(AT_PY)
    rationale_count = body.count('"rationale":')
    # DEFAULT_REGISTRY has 8 entries (sovereign-osctl-cli + metrics +
    # 3 Trinity tiers + router + grafana + future-master-dashboard)
    assert rationale_count >= 8, (
        f"only {rationale_count} 'rationale' fields (≥8 expected)"
    )


# --- CLI surface ---


def test_supports_list_tiers_verb():
    body = _read(AT_PY)
    assert '"list-tiers"' in body


def test_supports_registry_verb():
    body = _read(AT_PY)
    assert '"registry"' in body


def test_supports_show_verb():
    body = _read(AT_PY)
    assert '"show"' in body


def test_supports_matrix_verb():
    body = _read(AT_PY)
    assert '"matrix"' in body


def test_supports_set_verb():
    body = _read(AT_PY)
    assert '"set"' in body


def test_set_has_triple_gate():
    """`set` MUST require --apply + --confirm-tier-set (per
    sovereign-os triple-gate operator-mutation contract)."""
    body = _read(AT_PY)
    assert "--apply" in body, "set missing --apply gate"
    assert "--confirm-tier-set" in body, (
        "set missing --confirm-tier-set gate"
    )


def test_set_has_skip_tiers_gate():
    """Skipping ≥3 levels in one set requires --force-skip-tiers."""
    body = _read(AT_PY)
    assert "--force-skip-tiers" in body, (
        "set missing --force-skip-tiers gate"
    )


def test_json_and_human_format_flags():
    body = _read(AT_PY)
    assert "--json" in body and "--human" in body


# --- Operator-overlay config path ---


def test_default_config_path():
    body = _read(AT_PY)
    assert "/etc/sovereign-os/auth-tier.toml" in body, (
        "missing default /etc/sovereign-os/auth-tier.toml config path"
    )


def test_config_env_overridable():
    body = _read(AT_PY)
    assert "SOVEREIGN_OS_AUTH_TIER_CONFIG" in body, (
        "missing SOVEREIGN_OS_AUTH_TIER_CONFIG env override"
    )


def test_supports_dry_run():
    body = _read(AT_PY)
    assert "SOVEREIGN_OS_DRY_RUN" in body


# --- TOML load resilience (tomllib + tomli + graceful fallback) ---


def test_handles_missing_toml_lib():
    """Python 3.10 doesn't have tomllib; lint enforces fallback to
    tomli OR graceful degrade to defaults-only."""
    body = _read(AT_PY)
    assert "tomllib" in body, "missing tomllib reference (py3.11+)"
    has_fallback = (
        "tomli" in body
        or "ImportError" in body
    )
    assert has_fallback, (
        "missing tomli fallback OR ImportError handling for py3.10"
    )


# --- Metric ---


def test_emits_layer_b_metric():
    body = _read(AT_PY)
    assert "sovereign_os_operator_auth_tier_query_total" in body


# --- osctl integration ---


def test_osctl_dispatches_auth_tier():
    body = _read(OSCTL)
    assert "auth-tier)" in body, "osctl missing auth-tier) dispatcher"
    assert "auth-tier.py" in body, (
        "osctl dispatcher doesn't reference auth-tier.py"
    )


def test_osctl_help_documents_auth_tier_verbs():
    body = _read(OSCTL)
    for sub in ("auth-tier list-tiers", "auth-tier registry",
                "auth-tier show", "auth-tier matrix", "auth-tier set"):
        assert sub in body, f"osctl help missing {sub!r}"


def test_osctl_help_references_e11_m7():
    body = _read(OSCTL)
    assert "E11.M7" in body


# --- Smoke tests ---


def test_list_tiers_verb_runs():
    """list-tiers --json must return all 6 tiers in correct order."""
    result = subprocess.run(
        ["python3", str(AT_PY), "list-tiers", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, (
        f"list-tiers --json failed: stderr={result.stderr[:200]}"
    )
    import json as _json
    data = _json.loads(result.stdout)
    assert "tiers" in data
    tiers = data["tiers"]
    assert len(tiers) == 6, f"expected 6 tiers, got {len(tiers)}"
    actual_names = [t["tier"] for t in tiers]
    assert actual_names == EXPECTED_TIERS, (
        f"tier order drifted: {actual_names} vs {EXPECTED_TIERS}"
    )


def test_matrix_verb_runs():
    result = subprocess.run(
        ["python3", str(AT_PY), "matrix", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, (
        f"matrix --json failed: stderr={result.stderr[:200]}"
    )
    import json as _json
    data = _json.loads(result.stdout)
    assert "matrix" in data
    assert len(data["matrix"]) >= 5, (
        "matrix should have ≥5 registered dashboards"
    )


def test_set_preview_mode_runs_without_writing():
    """set without --apply MUST preview, NOT write."""
    result = subprocess.run(
        ["python3", str(AT_PY), "set", "router", "basic", "--json"],
        capture_output=True, text=True, timeout=10,
        env={**os.environ, "SOVEREIGN_OS_AUTH_TIER_CONFIG":
             "/tmp/auth-tier-test-noexist.toml"},
    )
    assert result.returncode == 0, (
        f"set preview failed: stderr={result.stderr[:200]}"
    )
    assert "preview" in result.stdout.lower() or "preview" in result.stderr.lower(), (
        "set without --apply should indicate preview mode"
    )
    # The config file MUST NOT exist after a preview
    assert not Path("/tmp/auth-tier-test-noexist.toml").exists(), (
        "set in preview mode wrote the config file (should not)"
    )


def test_set_unknown_tier_fails():
    """set with an unknown tier MUST exit non-zero."""
    result = subprocess.run(
        ["python3", str(AT_PY), "set", "router", "bogus-tier"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode != 0, (
        "set with unknown tier should fail"
    )


# --- R484 (E11.M7+) — Grafana dashboard surface ---


REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_JSON = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-auth-tier.json"
)


def test_dashboard_json_exists():
    """R484 — auth-tier Grafana dashboard surface (closes surface-map
    FUTURE waiver 'dashboard: FUTURE — Grafana panel for fleet auth-
    tier state')."""
    assert DASHBOARD_JSON.is_file(), (
        f"missing auth-tier dashboard: {DASHBOARD_JSON}"
    )


def test_dashboard_json_parseable():
    """The dashboard MUST be valid JSON (Grafana refuses invalid JSON
    on import)."""
    import json
    data = json.loads(DASHBOARD_JSON.read_text(encoding="utf-8"))
    assert "panels" in data, "dashboard missing panels"
    assert "title" in data and data["title"], "dashboard missing title"
    assert "uid" in data and data["uid"], "dashboard missing uid"


def test_dashboard_references_auth_tier_metric():
    """At least one panel MUST query sovereign_os_operator_auth_tier_
    query_total — otherwise the dashboard isn't visualizing the
    operator-§1g surface."""
    body = DASHBOARD_JSON.read_text(encoding="utf-8")
    assert "sovereign_os_operator_auth_tier_query_total" in body, (
        "auth-tier dashboard doesn't reference the Layer B metric"
    )


def test_dashboard_covers_six_tiers():
    """Per §1g 6-tier ladder verbatim, dashboard SHOULD reference all
    6 tier labels (no-auth / basic / advanced / social / enterprise /
    network-level)."""
    body = DASHBOARD_JSON.read_text(encoding="utf-8")
    for tier in ("no-auth", "basic", "advanced", "social",
                 "enterprise", "network-level"):
        assert tier in body, (
            f"auth-tier dashboard missing tier reference: {tier!r}"
        )


def test_dashboard_quotes_operator_1g_verbatim():
    """Dashboard MUST include the §1g verbatim ladder text — preserves
    operator-§1g source-of-truth on the visual surface."""
    body = DASHBOARD_JSON.read_text(encoding="utf-8")
    assert "no auth at all by default" in body, (
        "auth-tier dashboard missing §1g verbatim phrase"
    )
    assert "enterprise auth" in body, (
        "auth-tier dashboard missing §1g enterprise-auth ladder rung"
    )


def test_dashboard_listed_in_readme():
    """README.md MUST list the new dashboard (operator-discoverable
    inventory)."""
    readme = (DASHBOARD_JSON.parent / "README.md").read_text(encoding="utf-8")
    assert "sovereign-os-auth-tier.json" in readme, (
        "dashboards/README.md missing sovereign-os-auth-tier.json entry"
    )


def test_dashboard_tagged_sovereign_os():
    """Grafana 'sovereign-os' tag MUST be set — operator's dashboard
    folder filter depends on it."""
    import json
    data = json.loads(DASHBOARD_JSON.read_text(encoding="utf-8"))
    assert "sovereign-os" in (data.get("tags") or []), (
        "auth-tier dashboard missing sovereign-os tag"
    )
