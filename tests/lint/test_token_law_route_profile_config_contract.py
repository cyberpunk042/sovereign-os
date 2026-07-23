"""SDD-518 — operator-configurable route profiles contract (M00155 DEEPEN).

SDD-517 landed the route source but hard-coded the built-in doctrine at the
serving boundary. This lint pins the v2 that makes the per-role profile map
operator-configurable via env, the same impure-boundary way the token-law engine
resolves `SOVEREIGN_TOKEN_LAW_MASK_LAYERS`:

  * a `ROUTE_PROFILES_ENV` const + `RouteProfileMap::from_json` + `from_env_or_default`
    (unset / empty / parse-error all fall back to the doctrine);
  * gatewayd's `route_profile()` resolves through the env map, not `::default()`;
  * SDD-518 documents the tunable-doctrine framing.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ROUTE = REPO / "crates" / "sovereign-token-law-route" / "src" / "lib.rs"
ROUTE_TOML = REPO / "crates" / "sovereign-token-law-route" / "Cargo.toml"
GW = REPO / "crates" / "sovereign-gatewayd" / "src" / "lib.rs"
SDD = REPO / "docs" / "sdd" / "518-token-law-route-profile-config.md"


def test_route_crate_gains_the_operator_env_loader():
    src = ROUTE.read_text(encoding="utf-8")
    assert 'pub const ROUTE_PROFILES_ENV: &str = "SOVEREIGN_TOKEN_LAW_ROUTE_PROFILES";' in src
    assert "pub fn from_json(json: &str) -> Result<Self, String>" in src
    assert "pub fn from_env_or_default() -> Self" in src
    # Forgiving impure boundary: parse error falls back to the doctrine default.
    assert "unwrap_or_default()" in src
    # serde_json dep added; still dependency-light (no plane crates).
    deps = ROUTE_TOML.read_text(encoding="utf-8").split("[dependencies]", 1)[1]
    assert "serde_json" in deps
    assert "sovereign-token-law-fuse" not in deps and "sovereign-token-law-pii" not in deps


def test_gatewayd_resolves_the_operator_env_map():
    src = GW.read_text(encoding="utf-8")
    assert "RouteProfileMap::from_env_or_default()" in src
    assert "RouteProfileMap::default().resolve_directive" not in src, (
        "route_profile must resolve the operator env map, not the hard-coded doctrine"
    )


def test_sdd_518_documents_the_tunable_doctrine():
    assert SDD.is_file(), "SDD-518 must exist"
    text = SDD.read_text(encoding="utf-8")
    assert text.startswith("# SDD-518 —"), "H1 must be the canonical SDD-518 heading"
    low = text.lower()
    assert "operator" in low and "doctrine" in low
    assert "from_env_or_all" in low or "env" in low, "the env-config framing must be documented"
    assert "deepen" in low
