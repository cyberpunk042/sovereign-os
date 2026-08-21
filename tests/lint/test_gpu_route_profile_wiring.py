"""SDD-903 Phase 1b wiring guard — 84-gpu-route derives tiers from the active
profile ONLY behind a default-off knob, and can NEVER blank the tier list.

84-gpu-route is the module whose tier misregistration caused the week-long
256-wedge total-inference outage. The profile-driven path is therefore opt-in
(IAC_GPU_ROUTE_FROM_PROFILE, default 0) with a hard fallback to the hardcoded
tiers. This lint pins those two safety properties so the wiring can't silently
become default-on or lose its empty-tiers guard.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE = REPO_ROOT / "scripts" / "iac" / "modules" / "84-gpu-route.sh"


def _body() -> str:
    return MODULE.read_text(encoding="utf-8")


def test_hardcoded_default_tiers_remain_the_fallback():
    """The gpu-logic + gpu-oracle defaults must stay — they are what the module
    falls back to when no profile is active (this box, and any box that doesn't
    opt in)."""
    b = _body()
    assert "gpu-logic" in b and "IAC_GPU_PROXY_DEVICE:-logic" in b, (
        "hardcoded gpu-logic default tier missing — the profile-off fallback"
    )
    assert "gpu-oracle" in b and "IAC_ORACLE_PORT:-8083" in b, (
        "hardcoded gpu-oracle default tier missing — the profile-off fallback"
    )


def test_profile_derivation_is_opt_in_default_off():
    b = _body()
    assert "IAC_GPU_ROUTE_FROM_PROFILE:-0" in b, (
        "the profile-derived path must be gated by IAC_GPU_ROUTE_FROM_PROFILE "
        "defaulting to 0 (off) — never default-on for the 256-wedge module"
    )
    assert "derive-gpu-tiers.py" in b and "--emit-shell" in b, (
        "84-gpu-route must derive via scripts/inference/derive-gpu-tiers.py "
        "--emit-shell when opted in"
    )


def test_empty_derivation_never_blanks_the_tiers():
    """The derived value replaces _TIERS ONLY when non-empty — an empty
    derivation must fall through to the hardcoded defaults, never leave _TIERS
    blank (empty tiers = the silent 1-tok/s 256-wedge fallback)."""
    b = _body()
    assert '[ -n "${_dt}" ]' in b, (
        "missing the non-empty guard before overriding _TIERS from the profile "
        "— an empty derivation must not blank the tier list"
    )
