#!/usr/bin/env python3
"""
tests/lint/test_crate_graph_contract.py — the internal crate dependency-graph
contract (F-2026-009 / SDD-986).

The Phase-1 audit's orphan analysis was ad-hoc archaeology: a one-time discovery
that 413 of the 717 workspace crates (the whole `sovereign-cockpit-*` family) are
consumed by no other crate. This turns that discovery into a standing CI signal.

The graph is built by PARSING each `crates/*/Cargo.toml` directly (the repo's
established convention — see `test_workspace_hygiene_baseline.py` /
`test_workspace_metadata.py`; the pytest lint job has no `cargo`), not by shelling
`cargo metadata`. A crate is **reachable** if another workspace crate depends on it
(normal / build / dev deps) OR it is a binary (`[[bin]]` or `src/main.rs`). An
**orphan** is any crate that is neither.

The invariant (empirically true on `main` 2026-07-13): **every orphan is in the
`sovereign-cockpit-*` family** — 413 orphans, all cockpit, 0 non-cockpit. The
cockpit family is orphan-by-design: it is bridged to the webapp as wasm via
codegen (SDD-800 / F-2026-001), not via Cargo dependency edges, so it carries no
`crates/*` consumer. Every OTHER crate must be reachable (SDD-962 wired the last
non-cockpit orphans, closing F-2026-002).

So a NEW **non-cockpit** orphan — a crate wired into nothing and not a binary —
fails here, the instant it lands, instead of being found in the next audit.

Stdlib + pytest only (tomllib is stdlib on 3.11+).
"""
from __future__ import annotations

import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CRATES = REPO / "crates"

# The cockpit family is orphan-by-design (wasm-bridged via codegen, SDD-800).
COCKPIT_PREFIX = "sovereign-cockpit-"


def _graph():
    """Returns (all_names, reachable_names, orphans) from the crates/ tree."""
    metas = []
    names: set[str] = set()
    for d in sorted(CRATES.iterdir()):
        ct = d / "Cargo.toml"
        if not ct.is_file():
            continue
        try:
            m = tomllib.loads(ct.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as e:  # a malformed manifest is its own bug
            raise AssertionError(f"unparseable manifest {ct.relative_to(REPO)}: {e}")
        name = m.get("package", {}).get("name")
        if not name:
            continue
        has_bin = bool(m.get("bin")) or (d / "src" / "main.rs").is_file()
        names.add(name)
        metas.append((name, m, has_bin))

    consumed: set[str] = set()
    binaries: set[str] = set()
    for name, m, has_bin in metas:
        if has_bin:
            binaries.add(name)
        for section in ("dependencies", "build-dependencies", "dev-dependencies"):
            for dep in m.get(section, {}):
                if dep in names:  # a workspace-internal edge
                    consumed.add(dep)
    reachable = consumed | binaries
    orphans = names - reachable
    return names, reachable, orphans


def test_graph_is_nontrivial():
    """Sanity floor — the parse must actually see the workspace, so the
    real assertions below can't silently pass on an empty/failed walk."""
    names, reachable, orphans = _graph()
    assert len(names) > 500, f"only saw {len(names)} crates — did the walk fail?"
    assert reachable, "no reachable crates found — graph build is broken"


def test_no_orphan_outside_the_cockpit_family():
    """The contract: every graph-orphan must be a `sovereign-cockpit-*` crate
    (orphan-by-design, wasm-bridged via SDD-800). A NEW non-cockpit orphan — a
    crate consumed by nothing and not a binary — is a wiring regression."""
    _names, _reachable, orphans = _graph()
    stray = sorted(o for o in orphans if not o.startswith(COCKPIT_PREFIX))
    assert not stray, (
        f"{len(stray)} crate(s) are consumed by no other workspace crate and are "
        f"not a binary (orphans outside the cockpit wasm-bridge family):\n  "
        + "\n  ".join(stray)
        + "\n\nWire the crate into a consumer / binary, or — if it is a new "
        "UX-state crate bridged like the cockpit family — name it "
        f"`{COCKPIT_PREFIX}…`. (F-2026-009 / SDD-986; the cockpit family is the "
        "one sanctioned orphan set, per SDD-800.)"
    )
