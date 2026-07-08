"""control-systems registry completeness + integrity (SDD-045 §4).

config/control-systems.yaml is the single source of truth for the operator's
"everything can be turned on and off + tons of modes and profiles" controls —
the 11 real on/off + mode + profile systems mapped to the dashboards they
govern. The shared control-surface component renders the Profiles/Modes +
Features rail from it, so these locks keep it honest: all 11 present, every
field there, every change has a copy-command, and every applies_to slug is a
real dashboard in config/dashboard-catalog.yaml (no dead references).
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
REGISTRY = REPO / "config" / "control-systems.yaml"
CATALOG = REPO / "config" / "dashboard-catalog.yaml"

EXPECTED_IDS = {
    "os-profile", "runtime-mode", "flex-profile", "cpu-mode", "gpu-mode",
    "dashboard-toggle", "auth-tier", "selfdef", "perimeter",
    "inference-tier", "workload-knobs", "maintenance", "eval-run",
    "costs-export",
}
VALID_KINDS = {"profile", "mode", "toggle", "lifecycle"}
VALID_SCOPES = {"global", "scoped"}
REQUIRED_FIELDS = {
    "id", "kind", "scope", "label", "description",
    "options", "options_cli", "state_cli", "change_cli",
    "privileged", "applies_to",
}


def _registry() -> dict:
    return yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))


def _systems() -> list[dict]:
    return _registry()["systems"]


def _catalog_slugs() -> set[str]:
    cat = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    return {d["slug"] for d in cat["dashboards"]}


def test_registry_present_and_parses():
    assert REGISTRY.is_file(), f"missing {REGISTRY}"
    r = _registry()
    assert r.get("systems"), "registry has no systems"


def test_all_systems_present():
    ids = {s["id"] for s in _systems()}
    assert ids == EXPECTED_IDS, (
        f"registry systems drifted: missing={sorted(EXPECTED_IDS - ids)} "
        f"extra={sorted(ids - EXPECTED_IDS)}"
    )


def test_every_system_has_required_fields():
    for s in _systems():
        missing = sorted(REQUIRED_FIELDS - set(s))
        assert not missing, f"system {s.get('id')!r} missing fields: {missing}"


def test_kinds_and_scopes_valid():
    for s in _systems():
        assert s["kind"] in VALID_KINDS, f"{s['id']}: bad kind {s['kind']!r}"
        assert s["scope"] in VALID_SCOPES, f"{s['id']}: bad scope {s['scope']!r}"


def test_descriptions_are_substantive():
    for s in _systems():
        assert len((s.get("description") or "").strip()) >= 40, (
            f"system {s['id']!r} description too short (needs a real explanation)"
        )


def test_every_change_has_a_copy_command():
    """Web never mutates privileged state — every control must expose the
    exact CLI the operator runs."""
    for s in _systems():
        assert (s.get("change_cli") or "").startswith(("sovereign-osctl", "scripts/")), (
            f"system {s['id']!r} has no runnable change_cli"
        )


def test_options_non_empty():
    for s in _systems():
        assert isinstance(s.get("options"), list) and s["options"], (
            f"system {s['id']!r} has no options"
        )


def test_global_systems_render_on_every_header():
    """The global-scope systems are the per-panel header controls. There must
    be at least the profile picker; all global systems must be real."""
    globals_ = {s["id"] for s in _systems() if s["scope"] == "global"}
    assert "os-profile" in globals_, "the OS-profile picker must be a global header control"
    # every global system is a known system
    assert globals_ <= EXPECTED_IDS


def test_applies_to_slugs_exist_in_catalog():
    """No dead references — every dashboard a control system attaches to must
    be a real entry in the dashboard catalog."""
    slugs = _catalog_slugs()
    problems = []
    for s in _systems():
        for slug in s["applies_to"]:
            if slug not in slugs:
                problems.append(f"{s['id']} → unknown dashboard {slug!r}")
    assert not problems, "control systems reference non-existent dashboards: " + "; ".join(problems)


def test_every_dashboard_governed_or_catalog_only():
    """Sanity: the control-heavy dashboards (runtime-modes, trinity, d-09,
    auth-tier, master-dashboard) must each be governed by >=1 control system,
    proving the registry actually reaches the control surfaces."""
    governed: dict[str, int] = {}
    for s in _systems():
        for slug in s["applies_to"]:
            governed[slug] = governed.get(slug, 0) + 1
    for must in ("runtime-modes", "trinity", "d-09-hardware-pressure",
                 "auth-tier", "master-dashboard"):
        assert governed.get(must, 0) >= 1, (
            f"control-heavy dashboard {must!r} is governed by no control system"
        )
