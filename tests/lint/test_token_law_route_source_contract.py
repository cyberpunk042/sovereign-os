"""SDD-517 — the route token-law source contract (M00155 DEEPEN).

The route plane was parked because an SrpRole is a COMPUTE TIER, not a vocab
subset — no honest role->allow-bitset table. This lint pins the operator's chosen
resolution (config-driven profile binding): a dependency-light
`sovereign-token-law-route` crate that binds a routing decision (role + privacy /
safety axes) to a token-law PROFILE of forced-on guards, applied at the
`sovereign-gatewayd` serving boundary — complement, never replace.

  * the crate carries only flags (force_pii/force_entropy/force_safety_denylist)
    + the doctrine (Cloud|Public => force the egress guards), deps router-7axis
    + serde only (never the plane crates);
  * gatewayd's ServingTokenLaw applies the profile (forces guards on, never off);
  * SDD-517 documents the compute-tier gap + the profile-binding resolution.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ROUTE = REPO / "crates" / "sovereign-token-law-route" / "src" / "lib.rs"
ROUTE_TOML = REPO / "crates" / "sovereign-token-law-route" / "Cargo.toml"
GW = REPO / "crates" / "sovereign-gatewayd" / "src" / "lib.rs"
SDD = REPO / "docs" / "sdd" / "517-token-law-route-source.md"


def test_route_crate_binds_a_decision_to_a_profile_and_is_dependency_light():
    src = ROUTE.read_text(encoding="utf-8")
    assert "pub struct RouteProfile" in src
    assert "pub struct RouteDirective" in src
    assert "pub struct RouteProfileMap" in src
    for m in ("pub fn doctrine(", "pub fn resolve(", "pub fn resolve_directive("):
        assert m in src, f"route crate missing {m!r}"
    # The doctrine: data leaves the device (Cloud OR Public) => force the guards.
    assert "SrpRole::Cloud" in src and "Privacy::Public" in src
    assert "force_pii" in src and "force_entropy" in src
    # Dependency-light: router-7axis (axis types) + serde ONLY, never the plane crates.
    deps = ROUTE_TOML.read_text(encoding="utf-8").split("[dependencies]", 1)[1]
    assert 'path = "../sovereign-router-7axis"' in deps
    assert "sovereign-token-law-pii" not in deps, "the source stays plane-crate-free"
    assert "sovereign-token-law-entropy" not in deps
    assert "sovereign-token-law-fuse" not in deps


def test_gatewayd_applies_the_route_profile_forcing_guards_on_never_off():
    src = GW.read_text(encoding="utf-8")
    assert "pub route: Option<sovereign_token_law_route::RouteDirective>" in src
    assert "fn route_profile(&self)" in src
    assert "resolve_directive" in src
    # is_unconstrained accounts for a route forcing an egress guard on.
    assert "!p.force_pii" in src and "!p.force_entropy" in src
    # compile falls back to the plane defaults for a route-forced guard.
    assert "p.force_entropy" in src and "p.force_pii" in src
    # the load-bearing behavior tests.
    assert "route_to_cloud_forces_the_egress_guards_on_an_otherwise_empty_law" in src
    assert "route_never_deselects_an_explicit_guard" in src


def test_sdd_517_documents_the_gap_and_the_profile_binding_resolution():
    assert SDD.is_file(), "SDD-517 must exist"
    text = SDD.read_text(encoding="utf-8")
    assert text.startswith("# SDD-517 —"), "H1 must be the canonical SDD-517 heading"
    low = text.lower()
    assert "compute tier" in low, "the SrpRole-is-not-a-vocab-subset gap must be documented"
    assert "profile" in low and "doctrine" in low
    assert "complement" in low and "never" in low, "the complement-never-replace framing"
    assert "deepen" in low
