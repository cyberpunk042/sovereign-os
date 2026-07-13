"""ARCHITECTURE.md currency contract (F-2026-053 / SDD-965).

ARCHITECTURE.md was scaffold-era stale: it framed the profiles as "PR 5/6 stubs /
reserved slots" while all five exist as full bodies, and it had no mention of the
Stage-2 Rust intelligence layer (the gatewayd AI-backend daemon + generation stack).
SDD-965 refreshed the sovereign-os-surface sections (the info-hub-owned baseline is
left untouched).

This lint keeps the refresh from silently rotting back to scaffold-era:

  * every profile that exists under profiles/*.yaml must be named in ARCHITECTURE.md
    (so a realised profile can't be described as a reserved stub, and a new profile
    can't be omitted);
  * ARCHITECTURE.md must reference the intelligence layer — the `gatewayd` daemon and
    a link to the binaries map — so the doc can't regress to a foundation-only view
    that omits the box's own AI backend.

It deliberately does NOT assert prose wording or a specific date (fragile); it anchors
on the two facts that made the doc stale.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ARCH = REPO_ROOT / "ARCHITECTURE.md"
PROFILES = REPO_ROOT / "profiles"


def _profile_names() -> set[str]:
    return {p.stem for p in PROFILES.glob("*.yaml")}


def test_every_profile_is_named():
    body = ARCH.read_text(encoding="utf-8")
    missing = sorted(name for name in _profile_names() if name not in body)
    assert not missing, (
        f"ARCHITECTURE.md does not name existing profiles {missing} "
        "(a realised profile must not read as a reserved stub, and new profiles "
        "must be listed) — update the Profiles section"
    )


def test_references_the_intelligence_layer():
    body = ARCH.read_text(encoding="utf-8")
    assert "gatewayd" in body, (
        "ARCHITECTURE.md does not mention the gatewayd AI-backend daemon — the "
        "Stage-2 intelligence layer must be described (scaffold-era regression guard)"
    )
    assert "binaries.md" in body, (
        "ARCHITECTURE.md does not link docs/src/binaries.md — the runtime binary/daemon "
        "topology must be reachable from the architecture doc"
    )
